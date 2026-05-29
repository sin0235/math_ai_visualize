from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.schemas.auth import UserSettingsResponse

router = APIRouter(prefix="/api/user/settings", tags=["user-settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(_: UserRecord = Depends(get_current_user)) -> UserSettingsResponse:
    return UserSettingsResponse()


@router.put("", response_model=UserSettingsResponse, dependencies=[Depends(require_trusted_origin)])
async def put_user_settings(_: UserRecord = Depends(get_current_user)) -> UserSettingsResponse:
    return UserSettingsResponse()
