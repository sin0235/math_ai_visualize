import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.deps import get_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.user_settings import UserSettingsRepository
from app.schemas.auth import MAX_SETTINGS_JSON_CHARS, StoredRuntimeSettings, UserBasicSettings, UserSettingsRequest, UserSettingsResponse

router = APIRouter(prefix="/api/user/settings", tags=["user-settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> UserSettingsResponse:
    record = await UserSettingsRepository(db).get(user.id)
    if record is None:
        return UserSettingsResponse()
    try:
        settings = parse_user_settings(record.settings_json)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cấu hình đã lưu không còn hợp lệ.") from error
    return UserSettingsResponse(settings=settings, updated_at=record.updated_at)


@router.put("", response_model=UserSettingsResponse, dependencies=[Depends(require_trusted_origin)])
async def put_user_settings(request: UserSettingsRequest, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> UserSettingsResponse:
    settings_json = json.dumps(request.settings.model_dump(), ensure_ascii=False)
    if len(settings_json) > MAX_SETTINGS_JSON_CHARS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Cấu hình quá lớn để lưu.")
    record = await UserSettingsRepository(db).upsert(user.id, settings_json)
    return UserSettingsResponse(settings=request.settings, updated_at=record.updated_at)


def parse_user_settings(settings_json: str) -> UserBasicSettings:
    try:
        return UserBasicSettings.model_validate_json(settings_json)
    except ValidationError:
        legacy = StoredRuntimeSettings.model_validate_json(settings_json)
        return UserBasicSettings(
            default_provider=legacy.default_provider,
            default_model=legacy.router9.model or legacy.openrouter.model or legacy.nvidia.model or legacy.ollama.model,
            ocr=legacy.ocr,
        )
