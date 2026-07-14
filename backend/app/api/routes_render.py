import asyncio
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.history import RenderHistoryRepository
from app.repositories.scene_workspaces import SceneWorkspaceRepository
from app.core.config import get_settings
from app.core.logging import get_request_id
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene_v3 import (
    CommittedSceneRefV3,
    SceneCommandRequest,
    SceneConfirmationRequestV3,
    SceneWorkspaceCreateRequest,
    SceneWorkspaceResponseV3,
)
from app.schemas.scene import RenderRequest
from app.schemas.nlp import InputEnvelope
from app.services.api_errors import api_error
from app.services.nlp_rollout import evaluate_configured_nlp_rollout
from app.services.ai_resolution import resolve_byok_ai_config
from app.services.user_ai_settings import UserAiSettingsError
from app.services.system_settings import load_feature_flags

router = APIRouter(prefix="/api", tags=["render"])
logger = logging.getLogger("app.services.ai_providers")

RENDER_TIMEOUT_SECONDS = 310
RENDER_AI_USAGE_EVENT_TYPES = ["algebra_ai", "problem_variants", "solver_ai"]


async def _run_render_nlp(
    request: RenderRequest,
    db: DatabaseClient,
    user: UserRecord | None,
    *,
    preserve_problem_text: bool = True,
) -> tuple[RenderRequest, dict | None]:
    """Run NLP preflight for render.

    Returns (request, nlp_hints). When preserve_problem_text is True (v3 default),
    problem_text is never rewritten; hints are for the LLM only.
    """
    from app.services.ai_prompt import nlp_hints_payload_from_candidate

    rollout = await evaluate_configured_nlp_rollout(
        db,
        InputEnvelope(
            text=request.problem_text,
            target="render",
            context={"tier": request.tier, "preferred_renderer": request.preferred_renderer},
        ),
        user_id=user.id if user else None,
        request_id=get_request_id(),
        legacy_status="accepted",
        legacy_canonical=request.problem_text,
    )
    hints = None
    if rollout is not None:
        hints = nlp_hints_payload_from_candidate(rollout.candidate, mode=rollout.mode)
    if preserve_problem_text or not rollout or not rollout.can_apply or not rollout.candidate:
        return request, hints
    canonical_text = rollout.candidate.canonical_text or rollout.response.normalized_text
    return request.model_copy(update={"problem_text": canonical_text}), hints


async def _apply_render_nlp_rollout(
    request: RenderRequest,
    db: DatabaseClient,
    user: UserRecord | None,
    *,
    preserve_problem_text: bool = False,
) -> RenderRequest:
    """Backward-compatible wrapper used by any residual callers."""
    updated, _hints = await _run_render_nlp(
        request, db, user, preserve_problem_text=preserve_problem_text
    )
    return updated


async def build_problem_render_result_v3(
    request: RenderRequest,
    db: DatabaseClient,
    user: UserRecord | None = None,
    byok=None,
    nlp_hints: dict | None = None,
):
    """Native Scene v3: LLM → MathSceneV3 → pipeline → one repair → project.

    Does not call extractor v2 or migrate_scene_v2_dict.
    """
    from app.services.extractor_v3 import extract_scene_v3, parse_math_scene_v3, repair_scene_v3
    from app.services.scene_pipeline_v3 import PipelineIssueV3, run_scene_pipeline_v3

    settings = get_settings()
    original_text = request.problem_text
    if byok is None:
        try:
            byok = await resolve_byok_ai_config(db, user, "render", settings)
        except UserAiSettingsError as error:
            raise RuntimeError(f"Cấu hình BYOK không hợp lệ: {error}") from error

    provider: str | None = None
    model: str | None = None
    warnings: list[str] = []
    degraded = False

    byok_client = None
    if byok is not None and byok.client is not None:
        byok_client = byok.client
        provider = byok.provider
        model = byok.model_id
        try:
            from app.services.ai_prompt import SCENE_EXTRACTION_V3_SYSTEM_PROMPT
            from app.services.ai_prompt import _secure_system_prompt

            scene_json = await byok.client.extract_scene_json(
                request.problem_text,
                request.grade,
                request.advanced_settings.reasoning_layer,
                system_prompt=_secure_system_prompt(SCENE_EXTRACTION_V3_SYSTEM_PROMPT),
                nlp_hints=nlp_hints,
                schema_version="3.0",
            )
            scene = parse_math_scene_v3(scene_json, problem_text=original_text, grade=request.grade)
        except Exception as error:
            raise RuntimeError(f"Render BYOK Scene v3 thất bại: {error}") from error
    else:
        extraction = await extract_scene_v3(
            request.problem_text,
            request.grade,
            request.tier,
            request.advanced_settings,
            db=db,
            preferred_ai_provider=request.preferred_ai_provider,
            preferred_ai_model=request.preferred_ai_model,
            runtime_settings=request.runtime_settings,
            nlp_hints=nlp_hints,
        )
        scene = extraction.scene
        warnings = list(extraction.warnings)
        provider = extraction.provider
        model = extraction.model
        degraded = extraction.degraded

    # Always re-bind original user text and request overrides (NLP must not rewrite source).
    scene = _apply_render_request_overrides(scene, request, original_text=original_text)
    scene = _stamp_generator_audit(scene, provider, model)

    result = run_scene_pipeline_v3(scene)

    # One structured repair when deterministic pipeline rejects the scene.
    if not result.can_project and any(issue.severity == "error" for issue in result.issues):
        repaired = await repair_scene_v3(
            result.scene,
            result.issues,
            problem_text=original_text,
            grade=request.grade,
            tier=request.tier,
            advanced_settings=request.advanced_settings,
            db=db,
            runtime_settings=request.runtime_settings,
            provider=provider,
            model=model,
            byok_client=byok_client,
        )
        if repaired is not None:
            # Re-apply the same request overrides after repair (renderer, view, grade).
            repaired = _apply_render_request_overrides(repaired, request, original_text=original_text)
            repaired = _stamp_generator_audit(repaired, provider, model)
            result = run_scene_pipeline_v3(repaired)
            warnings.append("Đã chạy một lượt LLM repair Scene v3.")
        else:
            warnings.append("LLM repair Scene v3 không thành công.")

    # Final scene always carries generator identity for history/async completion.
    result = replace(result, scene=_stamp_generator_audit(result.scene, provider, model))

    # Mock/degraded: refuse unless ALLOW_RENDER_MOCK is intentionally on (internal tests).
    if degraded and not settings.allow_render_mock:
        raise RuntimeError(
            "Render Scene v3 ở chế độ mock/degraded bị từ chối. "
            "Bật ALLOW_RENDER_MOCK chỉ cho test nội bộ."
        )

    # Only real trust signals demote verified → needs_confirmation.
    # Telemetry (NLP attached, reasoning done, AI fallback notes) must stay info-only.
    confirmation_reasons = [
        message for message in dict.fromkeys(warnings) if _is_trust_confirmation_warning(message)
    ]
    if degraded and settings.allow_render_mock:
        confirmation_reasons.append("Hình mock (ALLOW_RENDER_MOCK); không dùng cho export/solve production.")
    if not confirmation_reasons:
        return result

    extra_issues = tuple(
        PipelineIssueV3(
            stage="repair",
            code="REPAIR_CONFIRMATION_REQUIRED",
            message=message,
            severity="warning",
        )
        for message in confirmation_reasons
    )
    return replace(
        result,
        issues=(*result.issues, *extra_issues),
        requires_user_confirmation=True,
        status="needs_confirmation" if result.status == "verified" else result.status,
    )


def _apply_render_request_overrides(scene, request: RenderRequest, *, original_text: str):
    """Bind user problem text, grade, preferred renderer, and view flags onto a scene.

    Used both after initial extract and after one-shot LLM repair so repair cannot
    drop renderer/view overrides or reintroduce RENDERER_UNSUPPORTED.
    """
    updates: dict = {"problem_text": original_text}
    if request.grade is not None:
        updates["grade"] = request.grade
    if request.preferred_renderer is not None:
        updates["renderer"] = request.preferred_renderer
    scene = scene.model_copy(update=updates)

    view_updates: dict = {}
    if request.advanced_settings.show_coordinates is not None:
        view_updates["show_coordinates"] = request.advanced_settings.show_coordinates
    if request.advanced_settings.show_axes is not None:
        view_updates["show_axes"] = request.advanced_settings.show_axes
    if request.advanced_settings.show_grid is not None:
        view_updates["show_grid"] = request.advanced_settings.show_grid
    if view_updates:
        scene = scene.model_copy(update={"view": scene.view.model_copy(update=view_updates)})
    return scene


def _stamp_generator_audit(scene, provider: str | None, model: str | None):
    """Persist platform/BYOK generator identity onto scene.audit for history rows."""
    if not provider and not model:
        return scene
    audit_updates: dict = {}
    if provider:
        audit_updates["generator_provider"] = provider
    if model:
        audit_updates["generator_model"] = model
    return scene.model_copy(update={"audit": scene.audit.model_copy(update=audit_updates)})


def _is_trust_confirmation_warning(message: str) -> bool:
    """True only for warnings that should block trusted_for_downstream."""
    lower = (message or "").strip().lower()
    if not lower:
        return False
    # Explicit info / telemetry — never demote trust.
    # Successful one-shot LLM repair is telemetry only: pipeline already re-verified.
    info_markers = (
        "nlp hints được đính kèm",
        "đã hoàn thành tầng suy luận",
        "ai fallback:",
        "bỏ qua reasoning layer",
        "đã chạy một lượt llm repair",
    )
    if any(marker in lower for marker in info_markers):
        return False
    trust_markers = (
        "mock",
        "degraded",
        "allow_render_mock",
        "llm repair scene v3 không thành công",
        "giả định",
        "thiếu dữ kiện",
    )
    return any(marker in lower for marker in trust_markers)


@router.post(
    "/render/v3",
    response_model=SceneWorkspaceResponseV3,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def render_problem_v3(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    from app.services.load_gates import render_load_gate

    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    settings = get_settings()
    from app.services.prompt_security import enforce_prompt_injection_gate

    enforce_prompt_injection_gate(request.problem_text, mode=settings.prompt_injection_gate_mode)
    # Native v3: keep original problem_text; NLP only as LLM hints.
    request, nlp_hints = await _run_render_nlp(request, db, user, preserve_problem_text=True)
    try:
        byok = await resolve_byok_ai_config(db, user, "render", settings)
    except UserAiSettingsError as error:
        raise api_error(status.HTTP_400_BAD_REQUEST, f"Cấu hình BYOK không hợp lệ: {error}", "RENDER_FAILED") from error
    if byok is None:
        await enforce_render_access(db, user)
    slot = await render_load_gate.try_acquire(settings.render_max_concurrent)
    if slot is None:
        raise api_error(status.HTTP_429_TOO_MANY_REQUESTS, "Hệ thống đang xử lý quá nhiều yêu cầu dựng hình.", "RENDER_CONCURRENT_LIMIT")
    try:
        try:
            result = await asyncio.wait_for(
                build_problem_render_result_v3(request, db, user, byok=byok, nlp_hints=nlp_hints),
                timeout=RENDER_TIMEOUT_SECONDS,
            )
        except TimeoutError as error:
            raise api_error(status.HTTP_504_GATEWAY_TIMEOUT, f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.", "TIMEOUT") from error
        except (RuntimeError, ValueError, KeyError) as error:
            message = str(error) or error.__class__.__name__
            code = "AI_PROVIDER_FAILED" if "provider" in message.lower() or "thất bại" in message.lower() else "RENDER_FAILED"
            raise api_error(
                status.HTTP_502_BAD_GATEWAY if code == "AI_PROVIDER_FAILED" else status.HTTP_400_BAD_REQUEST,
                message,
                code,
                ["Kiểm tra đề bài và cấu hình model.", "Thử tier khác hoặc viết đề rõ hơn."],
            ) from error
        if not result.can_project:
            error_issues = [issue for issue in result.issues if issue.severity == "error"]
            code = next((issue.code for issue in error_issues), "SCENE_SCHEMA_INVALID")
            detail_parts = [f"[{issue.code}] {issue.message}" for issue in error_issues[:5]]
            message = "Scene v3 không vượt qua pipeline."
            if detail_parts:
                message = f"{message} {'; '.join(detail_parts)}"
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                message,
                code,
                [
                    "Kiểm tra quan hệ dùng segment/line/plane id, không dùng shorthand AB.",
                    "Sửa tọa độ hoặc quan hệ mâu thuẫn trong đề, rồi dựng lại.",
                ],
            )
        # Fail-closed trust: only fully verified scenes are auto-trusted for solve/export.
        response = workspace_response_v3(result, trusted_for_downstream=result.status == "verified")
        try:
            await RenderHistoryRepository(db).create_v3_workspace(
                user.id,
                response,
                render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
            )
        except IntegrityError as error:
            raise api_error(status.HTTP_409_CONFLICT, "Scene workspace đã tồn tại.", "SCENE_WORKSPACE_EXISTS") from error
        return response
    finally:
        slot.release()


@router.post(
    "/render/v3/workspaces",
    response_model=SceneWorkspaceResponseV3,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
async def create_scene_workspace_v3(
    request: SceneWorkspaceCreateRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    from app.services.scene_pipeline_v3 import run_scene_pipeline_v3

    await enforce_rate_limit(db, http_request, user, "scene_command", 120, 60)
    result = run_scene_pipeline_v3(request.scene)
    if not result.can_project:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Scene không đạt topology validation.", "SCENE_SCHEMA_INVALID")
    try:
        await SceneWorkspaceRepository(db).create(user.id, result)
    except IntegrityError as error:
        raise api_error(status.HTTP_409_CONFLICT, "Scene workspace đã tồn tại.", "SCENE_WORKSPACE_EXISTS") from error
    return workspace_response_v3(result, trusted_for_downstream=result.status == "verified")


@router.get("/render/v3/workspaces/{scene_id}", response_model=SceneWorkspaceResponseV3)
async def get_scene_workspace_v3(
    scene_id: str,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    from app.services.scene_pipeline_v3 import run_scene_pipeline_v3

    workspace = await SceneWorkspaceRepository(db).find_for_user(user.id, scene_id)
    if workspace is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Không tìm thấy scene workspace.", "SCENE_WORKSPACE_NOT_FOUND")
    result = run_scene_pipeline_v3(workspace.scene)
    return workspace_response_v3(
        result,
        confirmed_revision=workspace.confirmed_revision,
        trusted_for_downstream=(
            result.status == "verified"
            or (result.status == "needs_confirmation" and workspace.confirmed_revision == workspace.scene.revision)
        ),
    )


@router.post(
    "/render/v3/workspaces/{scene_id}/confirm",
    response_model=SceneWorkspaceResponseV3,
    dependencies=[Depends(require_trusted_origin)],
)
async def confirm_scene_workspace_v3(
    scene_id: str,
    request: SceneConfirmationRequestV3,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    from app.services.committed_scene_v3 import CommittedSceneError, confirm_committed_scene_v3

    await enforce_rate_limit(db, http_request, user, "scene_command", 120, 60)
    try:
        committed = await confirm_committed_scene_v3(
            db,
            user.id,
            CommittedSceneRefV3(scene_id=scene_id, revision=request.revision),
        )
    except CommittedSceneError as error:
        raise api_error(error.status_code, str(error), error.code) from error
    return workspace_response_v3(
        committed.result,
        confirmed_revision=committed.workspace.confirmed_revision,
        trusted_for_downstream=committed.trusted_for_downstream,
    )


@router.post(
    "/render/v3/commands",
    response_model=SceneWorkspaceResponseV3,
    dependencies=[Depends(require_trusted_origin)],
)
async def apply_scene_command_v3(
    request: SceneCommandRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    from app.services.scene_commands_v3 import SceneCommandError, apply_scene_command
    from app.services.scene_pipeline_v3 import run_scene_pipeline_v3

    await enforce_rate_limit(db, http_request, user, "scene_command", 120, 60)
    repository = SceneWorkspaceRepository(db)
    workspace = await repository.find_for_user(user.id, request.command.scene_id)
    if workspace is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Không tìm thấy scene workspace.", "SCENE_WORKSPACE_NOT_FOUND")
    try:
        applied = apply_scene_command(workspace.scene, request.command)
    except SceneCommandError as error:
        status_code = status.HTTP_409_CONFLICT if error.code == "SCENE_EDIT_STALE" else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise api_error(status_code, str(error), error.code) from error

    result = run_scene_pipeline_v3(applied.scene)
    if not result.can_project:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Command tạo scene không hợp lệ.", "SCENE_SCHEMA_INVALID")
    failed_impacted = {
        item.relation_id
        for item in result.verification
        if item.status in {"failed", "error"} and item.relation_id in applied.affected_relation_ids
    }
    if failed_impacted:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Command làm hỏng ràng buộc: {sorted(failed_impacted)}.",
            "CONSTRAINT_FAILED",
        )
    try:
        await repository.commit_command(user.id, request.command, applied, result, workspace.history_item_id)
    except IntegrityError as error:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "Scene đã có revision mới; tải lại trước khi chỉnh tiếp.",
            "SCENE_EDIT_STALE",
        ) from error
    return workspace_response_v3(
        result,
        inverse_command=applied.inverse,
        changed_object_ids=sorted(applied.changed_object_ids),
        affected_relation_ids=sorted(applied.affected_relation_ids),
        trusted_for_downstream=result.status == "verified",
    )


def workspace_response_v3(
    result,
    *,
    inverse_command=None,
    changed_object_ids: list[str] | None = None,
    affected_relation_ids: list[str] | None = None,
    confirmed_revision: int | None = None,
    trusted_for_downstream: bool = False,
) -> SceneWorkspaceResponseV3:
    from app.services.renderer_router import build_render_payload_v3

    if result.projection is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Scene không tạo được render projection.", "RENDERER_UNSUPPORTED")
    return SceneWorkspaceResponseV3.model_validate({
        "status": result.status,
        "scene": result.scene,
        "projection": result.projection,
        "payload": build_render_payload_v3(result.projection),
        "verification": list(result.verification),
        "issues": [
            {
                "stage": issue.stage,
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
                "target_id": issue.target_id,
            }
            for issue in result.issues
        ],
        "requires_user_confirmation": result.requires_user_confirmation,
        "confirmed_revision": confirmed_revision,
        "trusted_for_downstream": trusted_for_downstream,
        "inverse_command": inverse_command,
        "changed_object_ids": changed_object_ids or [],
        "affected_relation_ids": affected_relation_ids or [],
    })


async def enforce_render_access(db: DatabaseClient, user: UserRecord | None) -> None:
    flags = await load_feature_flags(db)
    enforce_enabled(flags)
    if user is None:
        return
    repo = AdminRepository(db)
    plan = await repo.find_plan(user.plan) or await repo.find_plan("free")
    if plan is None or plan.daily_render_limit is None:
        return
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    used = await repo.count_user_render_quota_since(user.id, since, RENDER_AI_USAGE_EVENT_TYPES)
    if used >= plan.daily_render_limit:
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Bạn đã dùng hết hạn mức render hôm nay của gói hiện tại.",
            "PLAN_QUOTA_EXCEEDED",
            suggestions=["Chờ sang ngày mới để hạn mức được đặt lại.", "Nâng cấp gói hoặc liên hệ admin nếu cần thêm lượt render."],
        )


def enforce_enabled(flags: SystemFeatureFlags) -> None:
    if flags.maintenance_mode:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, flags.maintenance_message, "MAINTENANCE_MODE")
    if not flags.render_enabled:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tính năng render đang tạm tắt.", "RENDER_DISABLED")


def sanitize_request_dump(request: RenderRequest) -> dict:
    return request.model_dump(mode="json", exclude={"advanced_settings", "runtime_settings"})
