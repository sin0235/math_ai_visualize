from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_optional_current_user, require_trusted_origin
from app.core.config import get_settings, merge_runtime_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import OcrRequest, OcrResponse
from app.services.extractor import _merge_admin_ai_settings
from app.services.ocr import extract_text_from_image
from app.services.system_settings import load_feature_flags, load_plan_settings

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse, dependencies=[Depends(require_trusted_origin)])
async def ocr_image(
    request: OcrRequest,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
) -> OcrResponse:
    await enforce_ocr_access(db, user)
    settings = await _merge_admin_ai_settings(get_settings(), db)
    settings = merge_runtime_settings(settings, request.runtime_settings)
    try:
        result = await extract_text_from_image(
            request.image_data_url,
            settings,
            request.ocr_provider,
            request.ocr_model,
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if user is not None:
        await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"provider": result.provider, "model": result.model})
    return OcrResponse(text=result.text, provider=result.provider, model=result.model, warnings=result.warnings)


async def enforce_ocr_access(db: DatabaseClient, user: UserRecord | None) -> None:
    flags = await load_feature_flags(db)
    enforce_enabled(flags)
    if user is None:
        return
    plan_settings = await load_plan_settings(db)
    quota = plan_settings.plans.get(user.plan) or plan_settings.plans.get("free")
    if quota is None or quota.daily_ocr_limit is None:
        return
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    used = await AdminRepository(db).count_user_usage_events_since(user.id, "ocr", since)
    if used >= quota.daily_ocr_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Bạn đã dùng hết hạn mức OCR hôm nay.")


def enforce_enabled(flags: SystemFeatureFlags) -> None:
    if flags.maintenance_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=flags.maintenance_message)
    if not flags.ocr_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tính năng OCR đang tạm tắt.")


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
