from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.uploads import UploadRepository, UploadedFileRecord
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import OcrRequest, OcrResponse, OcrUploadResponse
from app.services.api_errors import api_error, bad_request_from_error
from app.services.ai_resolution import resolve_byok_ai_config
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.ocr import extract_text_from_image
from app.services.user_ai_settings import UserAiSettingsError
from app.services.system_settings import load_feature_flags
from app.services.upload_storage import StoredImage, load_upload_body_from_record, load_upload_image, save_upload_image

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/ocr/uploads", response_model=OcrUploadResponse, dependencies=[Depends(require_trusted_origin)])
async def upload_ocr_image(
    http_request: Request,
    file: UploadFile = File(...),
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> OcrUploadResponse:
    await enforce_rate_limit(db, http_request, user, "ocr_upload", 18, 60, settings)
    await enforce_ocr_access(db, user)
    try:
        stored = await save_upload_image(file, settings, db, user.id)
    except ValueError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    except RuntimeError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    return OcrUploadResponse(
        file_id=stored.file_id,
        filename=stored.filename,
        content_type=stored.content_type,
        size=stored.size,
        storage_provider=stored.storage_provider,
        public_url=stored.public_url,
    )


@router.get("/ocr/uploads/{upload_id}")
async def get_ocr_upload(
    upload_id: str,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    await enforce_rate_limit(db, http_request, user, "ocr_upload_read", 60, 60, settings)
    record = await load_authorized_upload_record(db, upload_id, user)
    try:
        body = await load_upload_body_from_record(record, settings)
    except RuntimeError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    headers = {
        "Cache-Control": "private, max-age=300",
        "Content-Disposition": content_disposition_inline(record.filename),
        "ETag": f'"{record.sha256}"',
    }
    return Response(content=body, media_type=record.content_type, headers=headers)


@router.post("/ocr", response_model=OcrResponse, dependencies=[Depends(require_trusted_origin)])
async def ocr_image(
    request: OcrRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> OcrResponse:
    await enforce_rate_limit(db, http_request, user, "ocr", 12 if user else 4, 60)
    await enforce_ocr_access(db, user)
    settings = await resolve_effective_settings(db, None)
    image_data_url = await resolve_ocr_image_data_url(request, db, settings, user)
    try:
        byok = await resolve_byok_ai_config(db, user, "ocr", settings)
    except UserAiSettingsError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    if byok is not None and byok.client is not None:
        try:
            text = await byok.client.ocr_image(image_data_url, byok.model_id)
        except RuntimeError as error:
            raise bad_request_from_error(error, "ocr_failed") from error
        return OcrResponse(text=text, provider="openai_compat", model=byok.model_id, warnings=["OCR sử dụng BYOK OpenAI-compatible."])
    registry = await load_model_registry(db, settings)
    raw_ocr_profile = registry.task_profiles.get("ocr")
    try:
        ocr_profile = resolve_task_profile(registry, "ocr")
    except ValueError as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    apply_profile = should_apply_ocr_profile(settings, raw_ocr_profile, ocr_profile, None, None)
    profile_provider = ocr_profile.provider_id if apply_profile else None
    profile_model = ocr_profile.model_id if apply_profile else None
    profile_fallbacks = ocr_profile.fallbacks if apply_profile else []
    try:
        result = await extract_text_from_image(
            image_data_url,
            settings,
            profile_provider,
            profile_model,
            "problem",
            profile_fallbacks,
        )
    except (RuntimeError, ValueError) as error:
        raise bad_request_from_error(error, "ocr_failed") from error
    if user is not None:
        await AdminRepository(db).record_user_usage_event(user.id, "ocr", {"provider": result.provider, "model": result.model})
    return OcrResponse(text=result.text, provider=result.provider, model=result.model, warnings=result.warnings)


async def resolve_ocr_image_data_url(request: OcrRequest, db: DatabaseClient, settings: Settings, user: UserRecord) -> str:
    return await resolve_image_source(request.image_data_url, request.upload_id, db, settings, user)


async def resolve_image_source(image_data_url: str | None, upload_id: str | None, db: DatabaseClient, settings: Settings, user: UserRecord) -> str:
    if image_data_url:
        return image_data_url
    if not upload_id:
        raise bad_request_from_error(ValueError("Cần gửi image_data_url hoặc upload_id."), "ocr_failed")
    stored = await load_owned_upload_image(db, upload_id, settings, user)
    return stored.data_url


async def load_owned_upload_image(db: DatabaseClient, upload_id: str, settings: Settings, user: UserRecord) -> StoredImage:
    await load_authorized_upload_record(db, upload_id, user, allow_admin=False)
    record = await load_upload_image(db, upload_id, settings)
    if record is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Không tìm thấy ảnh OCR đã upload.", "OCR_FAILED")
    return record


async def load_authorized_upload_record(
    db: DatabaseClient,
    upload_id: str,
    user: UserRecord,
    allow_admin: bool = True,
) -> UploadedFileRecord:
    record = await UploadRepository(db).load(upload_id)
    if record is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "Không tìm thấy ảnh OCR đã upload.", "OCR_FAILED")
    if record.user_id is not None and record.user_id != user.id and not (allow_admin and user.role == "admin"):
        raise api_error(status.HTTP_403_FORBIDDEN, "Bạn không có quyền dùng ảnh OCR này.", "OCR_FAILED")
    return record


def content_disposition_inline(filename: str) -> str:
    safe_name = safe_response_filename(filename)
    quoted = quote(safe_name, safe="")
    return f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{quoted}"


def safe_response_filename(filename: str) -> str:
    cleaned = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip() or "ocr-upload"
    return "".join(char if char.isalnum() or char in {".", "-", "_", " "} else "_" for char in cleaned)[:160] or "ocr-upload"


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
