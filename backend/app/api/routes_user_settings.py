import json

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.user_settings import UserSettingsRepository
from app.schemas.auth import UserSettingsRequest, UserSettingsResponse

router = APIRouter(prefix="/api/user/settings", tags=["user-settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> UserSettingsResponse:
    record = await UserSettingsRepository(db).get(user.id)
    if record is None:
        return UserSettingsResponse()
    return UserSettingsResponse(settings=json.loads(record.settings_json), updated_at=record.updated_at)


@router.put("", response_model=UserSettingsResponse)
async def put_user_settings(request: UserSettingsRequest, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> UserSettingsResponse:
    record = await UserSettingsRepository(db).upsert(user.id, json.dumps(request.settings, ensure_ascii=False))
    return UserSettingsResponse(settings=request.settings, updated_at=record.updated_at)
