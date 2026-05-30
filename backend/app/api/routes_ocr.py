from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.core.config import get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import OcrRequest, OcrResponse
from app.services.api_errors import api_error, bad_request_from_error
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.ocr import extract_text_from_image
from app.services.system_settings import load_feature_flags

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse, dependencies=[Depends(require_trusted_origin)])
async def ocr_image(
    request: OcrRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> OcrResponse:
    await enforce_rate_limit(db, http_request, user, "ocr", 12 if user else 4, 60)
    await enforce_ocr_access(db, user)
    settings = await resolve_effective_settings(db, request.runtime_settings)
    registry = await load_model_registry(db, settings)
    raw_ocr_profile = registry.task_profiles.get("ocr")
    try:
        ocr_profile = resolve_task_profile(registry, "ocr", request.ocr_provider, request.ocr_model)
    except ValueError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    apply_profile = should_apply_ocr_profile(settings, raw_ocr_profile, ocr_profile, request.ocr_provider, request.ocr_model)
    profile_provider = ocr_profile.provider_id if apply_profile else request.ocr_provider
    profile_model = ocr_profile.model_id if apply_profile else request.ocr_model
    profile_fallbacks = ocr_profile.fallbacks if apply_profile else []
    try:
        result = await extract_text_from_image(
            request.image_data_url,
            settings,
            profile_provider,
            profile_model,
            request.mode,
            profile_fallbacks,
        )
    except (RuntimeError, ValueError) as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    if user is not None:
        await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"provider": result.provider, "model": result.model})
    return OcrResponse(text=result.text, provider=result.provider, model=result.model, warnings=result.warnings)


async def enforce_ocr_access(db: DatabaseClient, user: UserRecord | None) -> None:
    flags = await load_feature_flags(db)
    enforce_enabled(flags)
    if user is None:
        return
    repo = AdminRepository(db)
    plan = await repo.find_plan(user.plan) or await repo.find_plan("free")
    if plan is None or plan.daily_ocr_limit is None:
        return
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    used = await AdminRepository(db).count_user_usage_events_since(user.id, "ocr", since)
    if used >= plan.daily_ocr_limit:
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Bạn đã dùng hết hạn mức OCR hôm nay của gói hiện tại.",
            "PLAN_QUOTA_EXCEEDED",
            suggestions=["Chờ sang ngày mới để hạn mức được đặt lại.", "Nâng cấp gói hoặc liên hệ admin nếu cần thêm lượt OCR."],
        )


def enforce_enabled(flags: SystemFeatureFlags) -> None:
    if flags.maintenance_mode:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, flags.maintenance_message, "MAINTENANCE_MODE")
    if not flags.ocr_enabled:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tính năng OCR đang tạm tắt.", "OCR_DISABLED")


def should_apply_ocr_profile(_settings, raw_profile, profile, requested_provider, requested_model) -> bool:
    if raw_profile is None or profile is None or requested_provider or requested_model:
        return False
    if not (profile.provider_id and profile.provider_id != "auto" and profile.model_id):
        return False
    env_settings = get_settings()
    if raw_profile.model_id:
        if profile.provider_id == "openrouter" and profile.model_id == env_settings.openrouter_vision_model:
            return False
        if profile.provider_id == "router9" and profile.model_id in {env_settings.router9_ocr_model, env_settings.router9_text_model}:
            return False
        if profile.provider_id == "nvidia" and profile.model_id == env_settings.nvidia_text_model:
            return False
        if profile.provider_id == "ollama" and profile.model_id == env_settings.ollama_text_model:
            return False
        if profile.provider_id == "openai_compat" and profile.model_id == env_settings.openai_compat_text_model:
            return False
    return True


def sanitize_public_runtime_settings(runtime_settings: object):
    if runtime_settings is None or not hasattr(runtime_settings, "model_dump"):
        return None
    data = runtime_settings.model_dump(mode="json")
    return type(runtime_settings).model_validate(
        {
            "default_provider": data.get("default_provider"),
            "openrouter": {"model": (data.get("openrouter") or {}).get("model")},
            "nvidia": {"model": (data.get("nvidia") or {}).get("model")},
            "ollama": {"model": (data.get("ollama") or {}).get("model")},
            "router9": {"model": (data.get("router9") or {}).get("model")},
        }
    )
