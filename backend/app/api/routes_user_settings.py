from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.activity import try_log_user_activity
from app.schemas.user_settings import (
    UserAiModelsUpdateRequest,
    UserAiProviderCheckRequest,
    UserAiProviderCheckResponse,
    UserAiProviderUpdateRequest,
    UserAiTaskProfilesUpdateRequest,
    UserSettingsResponse,
)
from app.services.openai_compat_client import OpenAICompatClient
from app.services.user_ai_settings import (
    UserAiSettingsError,
    load_user_settings,
    replace_user_ai_models,
    replace_user_ai_task_profiles,
    resolve_user_ai_provider_check_api_key,
    update_user_ai_provider,
)
from app.services.ssrf import UnsafeUrlError, validate_openai_compat_base_url

router = APIRouter(prefix="/api/user/settings", tags=["user-settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_user_settings(
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> UserSettingsResponse:
    return await load_user_settings(db, user.id)


@router.put("/ai-provider", response_model=UserSettingsResponse, dependencies=[Depends(require_trusted_origin)])
async def put_user_ai_provider(
    request: UserAiProviderUpdateRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserSettingsResponse:
    await enforce_rate_limit(db, http_request, user, "user_ai_provider_update", 20, 60, settings)
    try:
        response = await update_user_ai_provider(db, user.id, request, settings)
    except (UserAiSettingsError, UnsafeUrlError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    await try_log_user_activity(
        db,
        user.id,
        "byok_provider.updated",
        target_type="user_ai_provider_settings",
        target_id=user.id,
        metadata={"enabled": request.enabled, "credential_changed": request.api_key is not None, "credential_cleared": request.clear_api_key},
    )
    return response


@router.put("/ai-models", response_model=UserSettingsResponse, dependencies=[Depends(require_trusted_origin)])
async def put_user_ai_models(
    request: UserAiModelsUpdateRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserSettingsResponse:
    await enforce_rate_limit(db, http_request, user, "user_ai_models_update", 20, 60, settings)
    try:
        response = await replace_user_ai_models(db, user.id, request.models)
    except UserAiSettingsError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    await try_log_user_activity(
        db,
        user.id,
        "byok_models.updated",
        target_type="user_ai_models",
        target_id=user.id,
        metadata={
            "model_count": len(request.models),
            "enabled_count": sum(1 for item in request.models if item.enabled),
        },
    )
    return response


@router.put("/ai-task-profiles", response_model=UserSettingsResponse, dependencies=[Depends(require_trusted_origin)])
async def put_user_ai_task_profiles(
    request: UserAiTaskProfilesUpdateRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserSettingsResponse:
    await enforce_rate_limit(db, http_request, user, "user_ai_task_profiles_update", 20, 60, settings)
    try:
        response = await replace_user_ai_task_profiles(db, user.id, request.task_profiles)
    except UserAiSettingsError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    await try_log_user_activity(
        db,
        user.id,
        "byok_task_profiles.updated",
        target_type="user_ai_task_profiles",
        target_id=user.id,
        metadata={
            "task_count": len(request.task_profiles),
            "enabled_count": sum(1 for item in request.task_profiles if item.enabled),
        },
    )
    return response


@router.post("/ai-provider/check", response_model=UserAiProviderCheckResponse, dependencies=[Depends(require_trusted_origin)])
async def check_user_ai_provider(
    request: UserAiProviderCheckRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserAiProviderCheckResponse:
    await enforce_rate_limit(db, http_request, user, "user_ai_provider_check", 6, 60, settings)
    try:
        base_url = validate_openai_compat_base_url(request.base_url, settings)
        api_key = await resolve_user_ai_provider_check_api_key(db, user.id, request.api_key, settings)
        client = OpenAICompatClient.from_connection(base_url=base_url, api_key=api_key, model=request.model)
        await client.check_connection()
    except Exception as error:
        await try_log_user_activity(
            db,
            user.id,
            "byok_provider.check_failed",
            target_type="user_ai_provider_settings",
            target_id=user.id,
            metadata={"inline_credential": bool(request.api_key)},
        )
        return UserAiProviderCheckResponse(ok=False, message=_safe_check_error(error))
    await try_log_user_activity(
        db,
        user.id,
        "byok_provider.check_succeeded",
        target_type="user_ai_provider_settings",
        target_id=user.id,
        metadata={"inline_credential": bool(request.api_key)},
    )
    return UserAiProviderCheckResponse(ok=True, message="Kết nối OpenAI-compatible thành công.")


def _safe_check_error(error: Exception) -> str:
    message = str(error) or error.__class__.__name__
    if isinstance(error, UnsafeUrlError):
        return f"Base URL không an toàn: {' '.join(message.split())[:180]}"
    return "Không kết nối được OpenAI-compatible endpoint. Kiểm tra base URL, API key và model rồi thử lại."
