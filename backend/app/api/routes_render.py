import asyncio
import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, create_database_client, get_database
from app.repositories.activity import try_log_user_activity
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
from app.schemas.scene import (
    RenderJobCreateResponse,
    RenderJobStatusResponse,
    RenderRequest,
    RenderResponse,
    RenderSourceResponse,
    SceneRenderRequest,
)
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


def _bind_scene_request_fields(scene: MathScene, request: RenderRequest) -> MathScene:
    updates = {"problem_text": request.problem_text}
    if request.grade is not None:
        updates["grade"] = request.grade
    return scene.model_copy(update=updates)


async def _apply_render_nlp_rollout(
    request: RenderRequest,
    db: DatabaseClient,
    user: UserRecord | None,
) -> RenderRequest:
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
    if not rollout or not rollout.can_apply or not rollout.candidate:
        return request
    canonical_text = rollout.candidate.canonical_text or rollout.response.normalized_text
    return request.model_copy(update={"problem_text": canonical_text})


@router.post("/render/jobs", response_model=RenderJobCreateResponse, dependencies=[Depends(require_trusted_origin)])
async def create_render_job(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderJobCreateResponse:
    """Enqueue an async render job and return immediately."""
    from app.services.render_jobs import enqueue_render_job, spawn_inline_job

    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    request = await _apply_render_nlp_rollout(request, db, user)
    settings = get_settings()
    try:
        byok = await resolve_byok_ai_config(db, user, "render", settings)
    except UserAiSettingsError as error:
        raise api_error(status.HTTP_400_BAD_REQUEST, f"Cấu hình BYOK không hợp lệ: {error}", "RENDER_FAILED") from error
    if byok is None:
        await enforce_render_access(db, user)

    job_id = await enqueue_render_job(db, user.id, request)
    # Inline processing keeps single-container deploys working without a separate worker.
    spawn_inline_job(db, job_id)
    await try_log_user_activity(
        db,
        user.id,
        "render.queued",
        target_type="render_job",
        target_id=job_id,
        metadata={"tier": request.tier, "renderer": request.preferred_renderer, "byok": byok is not None},
    )
    return RenderJobCreateResponse(job_id=job_id, status="queued")


@router.get("/render/jobs/{job_id}", response_model=RenderJobStatusResponse)
async def get_render_job(
    job_id: str,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderJobStatusResponse:
    job = await RenderHistoryRepository(db).find_for_user(user.id, job_id)
    if job is None:
        # Pending jobs may not have history_items yet; fall back to raw job ownership.
        job = await RenderHistoryRepository(db).find_by_id(job_id)
        if job is None or job.user_id != user.id:
            raise api_error(status.HTTP_404_NOT_FOUND, "Không tìm thấy render job.", "RENDER_JOB_NOT_FOUND")
    status_value = job.status if job.status in {"queued", "running", "completed", "failed"} else "failed"
    response = None
    error = None
    if status_value == "completed" and job.response_json:
        try:
            response = RenderResponse.model_validate_json(job.response_json)
        except Exception:
            error = {"code": "RENDER_FAILED", "message": "Không đọc được kết quả render."}
            status_value = "failed"
    if status_value == "failed" and job.error_json:
        try:
            error = json.loads(job.error_json)
        except json.JSONDecodeError:
            error = {"code": "RENDER_FAILED", "message": job.error_json}
    return RenderJobStatusResponse(job_id=job.id, status=status_value, response=response, error=error)


@router.post("/render", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_problem(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    from app.services.load_gates import render_load_gate

    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    request = await _apply_render_nlp_rollout(request, db, user)
    settings = get_settings()
    try:
        byok = await resolve_byok_ai_config(db, user, "render", settings)
    except UserAiSettingsError as error:
        raise api_error(status.HTTP_400_BAD_REQUEST, f"Cấu hình BYOK không hợp lệ: {error}", "RENDER_FAILED") from error
    if byok is None:
        await enforce_render_access(db, user)

    slot = await render_load_gate.try_acquire(settings.render_max_concurrent)
    if slot is None:
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Hệ thống đang xử lý quá nhiều yêu cầu dựng hình. Vui lòng thử lại sau.",
            "RENDER_CONCURRENT_LIMIT",
            ["Chờ vài giây rồi thử lại.", "Giảm số tab/render song song."],
        )

    import time

    from app.repositories.errors import try_record_error_event

    started = time.perf_counter()
    try:
        try:
            response = await asyncio.wait_for(build_problem_render_response(request, db, user, byok=byok), timeout=RENDER_TIMEOUT_SECONDS)
        except TimeoutError as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                metadata={
                    "code": "TIMEOUT",
                    "tier": request.tier,
                    "renderer": request.preferred_renderer,
                    "byok": byok is not None,
                    "duration_ms": duration_ms,
                    "async": False,
                },
            )
            await try_record_error_event(
                db,
                message=f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.",
                source="server",
                request_id=get_request_id(),
                user_id=user.id,
                route="/api/render",
                method="POST",
                status_code=504,
                error_code="TIMEOUT",
                metadata={"duration_ms": duration_ms, "tier": request.tier},
            )
            raise api_error(
                status.HTTP_504_GATEWAY_TIMEOUT,
                f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.",
                "TIMEOUT",
                ["Thử lại sau hoặc chọn tier thấp hơn (tier1 nhanh hơn tier3)."],
            ) from error
        except (RuntimeError, ValueError, KeyError) as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            payload = render_error_payload(error)
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                metadata={
                    "code": payload["code"],
                    "tier": request.tier,
                    "renderer": request.preferred_renderer,
                    "byok": byok is not None,
                    "duration_ms": duration_ms,
                    "async": False,
                },
            )
            await try_record_error_event(
                db,
                message=payload.get("debug_message") or payload.get("message") or str(error),
                source="server",
                request_id=get_request_id(),
                user_id=user.id,
                route="/api/render",
                method="POST",
                status_code=400,
                error_code=payload.get("code") or "RENDER_FAILED",
                metadata={"duration_ms": duration_ms, "tier": request.tier},
            )
            raise api_error(status.HTTP_400_BAD_REQUEST, payload["debug_message"], payload["code"], payload["suggestions"]) from error
        duration_ms = int((time.perf_counter() - started) * 1000)
        if user is not None:
            job = await RenderHistoryRepository(db).create(
                user.id,
                request.problem_text,
                response.source.provider,
                response.source.model,
                response,
                render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
                advanced_settings_json=request.advanced_settings.model_dump_json(),
                runtime_settings_json=request.runtime_settings.model_dump_json(exclude_none=True) if request.runtime_settings is not None else None,
                source_type="problem",
                renderer=response.scene.renderer,
            )
            # Persist duration on completed history row when column exists.
            try:
                await db.execute("UPDATE render_jobs SET duration_ms = ? WHERE id = ?", [duration_ms, job.id])
            except Exception:
                pass
            await try_log_user_activity(
                db,
                user.id,
                "render.completed",
                target_type="render_job",
                target_id=job.id,
                metadata={
                    "tier": request.tier,
                    "renderer": response.scene.renderer,
                    "provider": response.source.provider,
                    "model": response.source.model,
                    "source_kind": response.source.kind,
                    "degraded": response.degraded,
                    "fallback_source": response.fallback_source,
                    "duration_ms": duration_ms,
                    "async": False,
                },
            )
        return response
    finally:
        slot.release()


async def build_problem_render_response(request: RenderRequest, db: DatabaseClient, user: UserRecord | None = None, byok=None) -> RenderResponse:
    from app.services.extractor import build_scene_with_cas_fix, extract_scene
    from app.services.scene_pipeline import validate_normalize_verify_scene

    settings = get_settings()
    source = RenderSourceResponse(kind="ai")
    degraded = False
    fallback_source = "none"
    if byok is None:
        try:
            byok = await resolve_byok_ai_config(db, user, "render", settings)
        except UserAiSettingsError as error:
            raise RuntimeError(f"Cấu hình BYOK không hợp lệ: {error}") from error
    if byok is not None and byok.client is not None:
        try:
            scene_json = await byok.client.extract_scene_json(
                request.problem_text,
                request.grade,
                request.advanced_settings.reasoning_layer,
            )
            scene, warnings = build_scene_with_cas_fix(scene_json, verify=request.advanced_settings.verify_scene)
            source = RenderSourceResponse(kind="byok")
        except Exception as error:
            raise RuntimeError(f"Render BYOK thất bại: {error}") from error
    else:
        extraction = await extract_scene(
            request.problem_text,
            request.grade,
            request.tier,
            request.advanced_settings,
            db=db,
            preferred_ai_provider=request.preferred_ai_provider,
            preferred_ai_model=request.preferred_ai_model,
            runtime_settings=request.runtime_settings,
        )
        scene, warnings, degraded, fallback_source = unpack_extraction_result(extraction)
        source = RenderSourceResponse(
            kind="mock" if fallback_source == "mock" else "ai",
            provider=getattr(extraction, "provider", None),
            model=getattr(extraction, "model", None),
            fallback_used=fallback_source != "none" or degraded,
            fallback_reason=fallback_source if fallback_source != "none" else None,
            candidate_attempts=[
                {"provider": attempt.provider, "model": attempt.model, "stage": "extract", "success": False, "message": attempt.message}
                for attempt in getattr(extraction, "attempts", [])
            ],
        )
    scene = _bind_scene_request_fields(scene, request)
    if request.preferred_renderer is not None:
        scene.renderer = request.preferred_renderer
    scene_data = scene.model_dump()
    if request.advanced_settings.show_coordinates is not None:
        scene_data["view"]["show_coordinates"] = request.advanced_settings.show_coordinates
    if request.advanced_settings.show_axes is not None:
        scene_data["view"]["show_axes"] = request.advanced_settings.show_axes
    if request.advanced_settings.show_grid is not None:
        scene_data["view"]["show_grid"] = request.advanced_settings.show_grid
    scene = scene.model_validate(scene_data)
    if scene.topic == "unknown":
        warnings.append("Chưa nhận diện được dạng toán, hãy thử đề cụ thể hơn.")
    response = validate_normalize_verify_scene(
        scene,
        request.advanced_settings,
        warnings=warnings,
        source=source,
        build_problem_advisory=True,
    ).response
    return response


async def build_problem_render_result_v3(request: RenderRequest, db: DatabaseClient, user: UserRecord | None = None, byok=None):
    from app.services.scene_pipeline_v3 import PipelineIssueV3, run_scene_pipeline_v3
    from app.services.scene_v3_adapter import migrate_scene_v2_dict

    # ponytail: extractor vẫn sinh v2; xóa bridge này khi prompt/parser phát MathSceneV3 trực tiếp.
    legacy_response = await build_problem_render_response(request, db, user, byok=byok)
    scene, report = migrate_scene_v2_dict(legacy_response.scene.model_dump(mode="json"))
    result = run_scene_pipeline_v3(scene)
    confirmation_reasons = [*report.warnings, *report.unresolved_references]
    if legacy_response.degraded or legacy_response.requires_user_confirmation:
        confirmation_reasons.append("Nguồn render fallback hoặc chưa được xác nhận.")
    if not confirmation_reasons:
        return result
    issues = (*result.issues, *(
        PipelineIssueV3(
            stage="repair",
            code="REPAIR_CONFIRMATION_REQUIRED",
            message=message,
            severity="warning",
        )
        for message in dict.fromkeys(confirmation_reasons)
    ))
    return replace(result, status="needs_confirmation", issues=issues, requires_user_confirmation=True)


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
    request = await _apply_render_nlp_rollout(request, db, user)
    settings = get_settings()
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
            result = await asyncio.wait_for(build_problem_render_result_v3(request, db, user, byok=byok), timeout=RENDER_TIMEOUT_SECONDS)
        except TimeoutError as error:
            raise api_error(status.HTTP_504_GATEWAY_TIMEOUT, f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.", "TIMEOUT") from error
        if not result.can_project:
            code = next((issue.code for issue in result.issues if issue.severity == "error"), "SCENE_SCHEMA_INVALID")
            raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Scene v3 không vượt qua pipeline.", code)
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


@router.post("/render/scene", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_scene(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
) -> RenderResponse:
    from app.services.scene_pipeline import validate_normalize_verify_scene

    db = optional_database_for_scene_render(user)
    if db is not None:
        await enforce_rate_limit(db, http_request, user, "render_scene", 40 if user else 12, 60)
        await enforce_render_access(db, user)
    assert_scene_edit_revision(request)
    response = validate_normalize_verify_scene(
        request.scene,
        request.advanced_settings,
        warnings=[],
        source=RenderSourceResponse(kind="scene_edit"),
        build_problem_advisory=False,
    ).response
    return response


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


def assert_scene_edit_revision(request: SceneRenderRequest) -> None:
    if request.response is None:
        return
    base = request.response.scene
    scene = request.scene
    if base.scene_id and scene.scene_id and base.scene_id != scene.scene_id:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "Scene đang sửa không khớp kết quả dựng hình hiện tại; hãy tải lại hoặc dựng lại hình.",
            "SCENE_EDIT_STALE",
        )
    expected_revision = (base.revision or 0) + 1
    if scene.revision != expected_revision:
        raise api_error(
            status.HTTP_409_CONFLICT,
            f"Revision chỉnh sửa không hợp lệ: cần {expected_revision}, nhận {scene.revision}.",
            "SCENE_EDIT_STALE",
        )


def optional_database_for_scene_render(user: UserRecord | None) -> DatabaseClient | None:
    try:
        return create_database_client(get_settings())
    except RuntimeError:
        if user is not None:
            raise
        return None


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


def unpack_extraction_result(extraction) -> tuple:
    if hasattr(extraction, "scene"):
        return extraction.scene, extraction.warnings, extraction.degraded, extraction.fallback_source
    scene, warnings = extraction
    return scene, warnings, False, "none"


def render_degradation_metadata(warnings: list[str]) -> tuple[bool, str]:
    for warning in warnings:
        lowered = warning.lower()
        if "mock" in lowered:
            return True, "mock"
        if "fallback" in lowered or "dự phòng" in lowered:
            return True, "provider_fallback"
    return False, "none"


def render_error_payload(error: Exception) -> dict:
    message = str(error) or error.__class__.__name__
    code = "RENDERER_INCOMPATIBLE" if "không tương thích" in message.lower() else "RENDER_EXTRACTION_FAILED"
    return {
        "code": code,
        "message": "Không thể dựng hình từ đề bài này.",
        "debug_message": message,
        "suggestions": ["Kiểm tra đề bài và cấu hình tier model.", "Thử mức chất lượng khác hoặc viết đề bài rõ hơn."],
    }


def sanitize_request_dump(request: RenderRequest | SceneRenderRequest) -> dict:
    return request.model_dump(mode="json", exclude={"advanced_settings", "runtime_settings"})
