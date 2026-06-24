import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, create_database_client, get_database
from app.repositories.admin import AdminRepository
from app.repositories.history import RenderHistoryRepository
from app.core.config import get_settings
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import RenderRequest, RenderResponse, SceneRenderRequest
from app.services.api_errors import api_error
from app.services.ai_resolution import resolve_byok_ai_config
from app.services.user_ai_settings import UserAiSettingsError
from app.services.system_settings import load_feature_flags

router = APIRouter(prefix="/api", tags=["render"])
logger = logging.getLogger("app.services.ai_providers")

RENDER_TIMEOUT_SECONDS = 310
RENDER_AI_USAGE_EVENT_TYPES = ["algebra_ai", "problem_variants", "solver_ai"]


@router.post("/render", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_problem(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    settings = get_settings()
    try:
        byok = await resolve_byok_ai_config(db, user, "render", settings)
    except UserAiSettingsError as error:
        raise api_error(status.HTTP_400_BAD_REQUEST, f"Cấu hình BYOK không hợp lệ: {error}", "RENDER_FAILED") from error
    if byok is None:
        await enforce_render_access(db, user)
    try:
        response = await asyncio.wait_for(build_problem_render_response(request, db, user, byok=byok), timeout=RENDER_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise api_error(
            status.HTTP_504_GATEWAY_TIMEOUT,
            f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s.",
            "TIMEOUT",
            ["Thử lại sau hoặc chọn tier thấp hơn (tier1 nhanh hơn tier3)."],
        ) from error
    except (RuntimeError, ValueError, KeyError) as error:
        payload = render_error_payload(error)
        raise api_error(status.HTTP_400_BAD_REQUEST, payload["debug_message"], payload["code"], payload["suggestions"]) from error
    if user is not None:
        await RenderHistoryRepository(db).create(
            user.id,
            request.problem_text,
            request.preferred_ai_provider,
            request.preferred_ai_model,
            response,
            render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
            advanced_settings_json=request.advanced_settings.model_dump_json(),
            runtime_settings_json=None,
            source_type="problem",
            renderer=response.scene.renderer,
        )
    return response


async def build_problem_render_response(request: RenderRequest, db: DatabaseClient, user: UserRecord | None = None, byok=None) -> RenderResponse:
    from app.services.extractor import extract_scene
    from app.services.geometry_engine import normalize_scene
    from app.services.quality_advisory import build_render_advisory
    from app.services.renderer_router import build_render_payload

    settings = get_settings()
    ai_source = "admin"
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
            from app.services.extractor import build_scene_with_cas_fix

            scene, warnings = build_scene_with_cas_fix(scene_json, verify=request.advanced_settings.verify_scene)
            ai_source = "byok"
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
    scene = normalize_scene(scene, request.advanced_settings)
    payload = build_render_payload(scene, request.advanced_settings)
    if scene.topic == "unknown":
        warnings.append("Chưa nhận diện được dạng toán, hãy thử đề cụ thể hơn.")
    advisory = None
    if get_settings().advisory_enabled:
        advisory = build_render_advisory(request.problem_text, request.grade, scene, warnings, scene.cas_issues, payload)
    warning_degraded, warning_fallback_source = render_degradation_metadata(warnings)
    degraded = degraded or warning_degraded
    if fallback_source == "none":
        fallback_source = warning_fallback_source
    return RenderResponse(scene=scene, payload=payload, warnings=warnings, cas_issues=scene.cas_issues, advisory=advisory, degraded=degraded, fallback_source=fallback_source, ai_source=ai_source)


@router.post("/render/scene", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_scene(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
) -> RenderResponse:
    from app.services.geometry_engine import normalize_scene
    from app.services.quality_advisory import build_scene_advisory
    from app.services.renderer_router import build_render_payload

    db = optional_database_for_scene_render(user)
    if db is not None:
        await enforce_rate_limit(db, http_request, user, "render_scene", 40 if user else 12, 60)
        await enforce_render_access(db, user)
    scene = normalize_scene(request.scene, request.advanced_settings)
    payload = build_render_payload(scene, request.advanced_settings)
    warnings = []
    computed = (payload.three_scene or {}).get("computed") if payload.three_scene else None
    if isinstance(computed, dict):
        warnings = [warning for warning in computed.get("warnings", []) if isinstance(warning, str)]
    advisory = build_scene_advisory(scene, warnings, payload) if get_settings().advisory_enabled else None
    response = RenderResponse(scene=scene, payload=payload, warnings=warnings, cas_issues=scene.cas_issues, advisory=advisory, ai_source="none")
    if user is not None:
        await RenderHistoryRepository(db).create(
            user.id,
            scene.problem_text,
            None,
            None,
            response,
            render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
            advanced_settings_json=request.advanced_settings.model_dump_json(),
            runtime_settings_json=None,
            source_type="scene_edit",
            renderer=scene.renderer,
        )
    return response


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
    used = await repo.count_user_render_jobs_since(user.id, since, ai_source="admin")
    used += await repo.count_user_render_jobs_since(user.id, since, source_type="problem", ai_source="none")
    used += await repo.count_user_usage_events_since_any(user.id, RENDER_AI_USAGE_EVENT_TYPES, since)
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
    return {
        "code": "RENDER_FAILED",
        "message": "Không thể dựng hình từ đề bài này.",
        "debug_message": message,
        "suggestions": ["Kiểm tra đề bài và cấu hình tier model.", "Thử mức chất lượng khác hoặc viết đề bài rõ hơn."],
    }


def sanitize_request_dump(request: RenderRequest | SceneRenderRequest) -> dict:
    return request.model_dump(mode="json", exclude={"advanced_settings", "runtime_settings"})
