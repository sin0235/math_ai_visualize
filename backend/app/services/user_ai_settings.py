from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.db.session import DatabaseClient
from app.repositories.user_ai_settings import UserAiSettingsRepository, UserAiProviderSettingsRecord, UserAiModelRecord, UserAiTaskProfileRecord
from app.schemas.user_settings import (
    BYOK_TASKS,
    UserAiModelSettings,
    UserAiModelSettingsResponse,
    UserAiProviderSettingsResponse,
    UserAiProviderUpdateRequest,
    UserAiTaskProfileSettings,
    UserSettingsResponse,
)
from app.services.secret_crypto import SecretCryptoError, api_key_last4, decrypt_user_secret, encrypt_user_secret, ensure_user_secret_key_configured
from app.services.ssrf import UnsafeUrlError, validate_openai_compat_base_url


class UserAiSettingsError(ValueError):
    pass


@dataclass(frozen=True)
class ByokResolvedTask:
    user_id: str
    task: str
    base_url: str
    api_key: str
    model_id: str
    supports_vision: bool


async def load_user_settings(db: DatabaseClient, user_id: str) -> UserSettingsResponse:
    repo = UserAiSettingsRepository(db)
    provider = await repo.get_provider_settings(user_id)
    models = await repo.list_models(user_id)
    profiles = await repo.list_task_profiles(user_id)
    return build_user_settings_response(provider, models, profiles)


async def update_user_ai_provider(db: DatabaseClient, user_id: str, request: UserAiProviderUpdateRequest, settings: Settings) -> UserSettingsResponse:
    repo = UserAiSettingsRepository(db)
    existing = await repo.get_provider_settings(user_id)
    base_url = validate_openai_compat_base_url(request.base_url, settings) if request.base_url else ""
    update_api_key = request.clear_api_key or request.api_key is not None
    api_key_ciphertext = existing.api_key_ciphertext if existing else None
    last4 = existing.api_key_last4 if existing else None

    if request.clear_api_key:
        api_key_ciphertext = None
        last4 = None
    elif request.api_key is not None:
        try:
            api_key_ciphertext = encrypt_user_secret(request.api_key, settings.user_secret_encryption_key)
        except SecretCryptoError as error:
            raise UserAiSettingsError(str(error)) from error
        last4 = api_key_last4(request.api_key)

    if request.enabled:
        if not base_url:
            raise UserAiSettingsError("Cần cấu hình base URL trước khi bật BYOK.")
        if not api_key_ciphertext:
            raise UserAiSettingsError("Cần cấu hình API key trước khi bật BYOK.")
        try:
            ensure_user_secret_key_configured(settings.user_secret_encryption_key)
        except SecretCryptoError as error:
            raise UserAiSettingsError(str(error)) from error

    try:
        provider = await repo.upsert_provider_settings(
            user_id,
            enabled=request.enabled,
            base_url=base_url,
            api_key_ciphertext=api_key_ciphertext,
            api_key_last4=last4,
            update_api_key=update_api_key,
        )
    except UnsafeUrlError as error:
        raise UserAiSettingsError(str(error)) from error
    models = await repo.list_models(user_id)
    profiles = await repo.list_task_profiles(user_id)
    return build_user_settings_response(provider, models, profiles)


async def replace_user_ai_models(db: DatabaseClient, user_id: str, models: list[UserAiModelSettings]) -> UserSettingsResponse:
    repo = UserAiSettingsRepository(db)
    existing_profiles = await repo.list_task_profiles(user_id)
    validate_profiles_against_model_settings(models, existing_profiles)
    stored = await repo.replace_models(user_id, [model.model_dump() for model in models])
    provider = await repo.get_provider_settings(user_id)
    profiles = await repo.list_task_profiles(user_id)
    return build_user_settings_response(provider, stored, profiles)


async def replace_user_ai_task_profiles(db: DatabaseClient, user_id: str, profiles: list[UserAiTaskProfileSettings]) -> UserSettingsResponse:
    repo = UserAiSettingsRepository(db)
    models = await repo.list_models(user_id)
    validate_task_profiles(models, profiles)
    stored_profiles = await repo.replace_task_profiles(user_id, [profile.model_dump() for profile in profiles])
    provider = await repo.get_provider_settings(user_id)
    return build_user_settings_response(provider, models, stored_profiles)


async def resolve_user_ai_provider_check_api_key(db: DatabaseClient, user_id: str, request_api_key: str | None, settings: Settings) -> str:
    if request_api_key:
        return request_api_key
    provider = await UserAiSettingsRepository(db).get_provider_settings(user_id)
    if provider is None or not provider.api_key_ciphertext:
        return ""
    try:
        return decrypt_user_secret(provider.api_key_ciphertext, settings.user_secret_encryption_key)
    except SecretCryptoError as error:
        raise UserAiSettingsError(str(error)) from error


async def resolve_byok_task(db: DatabaseClient, user_id: str, task: str, settings: Settings) -> ByokResolvedTask | None:
    if task not in BYOK_TASKS:
        raise UserAiSettingsError("Tác vụ BYOK không hợp lệ.")
    repo = UserAiSettingsRepository(db)
    provider = await repo.get_provider_settings(user_id)
    if provider is None or not provider.enabled:
        return None
    profile = next((item for item in await repo.list_task_profiles(user_id) if item.task == task and item.enabled), None)
    if profile is None:
        raise UserAiSettingsError(f"BYOK đang bật nhưng chưa chọn model cho tác vụ {task}.")
    model = next((item for item in await repo.list_models(user_id) if item.model_id == profile.model_id and item.enabled), None)
    if model is None:
        raise UserAiSettingsError("Model BYOK đã chọn không còn tồn tại hoặc đã bị tắt.")
    if task == "ocr" and not model.supports_vision:
        raise UserAiSettingsError("Model BYOK cho OCR cần được đánh dấu hỗ trợ vision.")
    if not provider.base_url or not provider.api_key_ciphertext:
        raise UserAiSettingsError("BYOK đang bật nhưng thiếu base URL hoặc API key.")
    try:
        base_url = validate_openai_compat_base_url(provider.base_url, settings)
        api_key = decrypt_user_secret(provider.api_key_ciphertext, settings.user_secret_encryption_key)
    except (UnsafeUrlError, SecretCryptoError) as error:
        raise UserAiSettingsError(str(error)) from error
    return ByokResolvedTask(user_id=user_id, task=task, base_url=base_url, api_key=api_key, model_id=model.model_id, supports_vision=model.supports_vision)


def validate_task_profiles(models: list[UserAiModelRecord], profiles: list[UserAiTaskProfileSettings]) -> None:
    enabled_models = {model.model_id: model for model in models if model.enabled}
    for profile in profiles:
        model = enabled_models.get(profile.model_id)
        if model is None:
            raise UserAiSettingsError(f"Model {profile.model_id} không tồn tại hoặc đã bị tắt.")
        if profile.task == "ocr" and not model.supports_vision:
            raise UserAiSettingsError("Model cho OCR cần hỗ trợ vision.")


def validate_profiles_against_model_settings(models: list[UserAiModelSettings], profiles: list[UserAiTaskProfileRecord]) -> None:
    enabled_models = {model.model_id: model for model in models if model.enabled}
    for profile in profiles:
        if not profile.enabled:
            continue
        model = enabled_models.get(profile.model_id)
        if model is None:
            raise UserAiSettingsError(f"Task {profile.task} đang dùng model {profile.model_id}; hãy đổi task profile trước khi xoá hoặc tắt model này.")
        if profile.task == "ocr" and not model.supports_vision:
            raise UserAiSettingsError("Model đang dùng cho OCR cần tiếp tục được đánh dấu hỗ trợ vision.")


def build_user_settings_response(
    provider: UserAiProviderSettingsRecord | None,
    models: list[UserAiModelRecord],
    profiles: list[UserAiTaskProfileRecord],
) -> UserSettingsResponse:
    provider_response = UserAiProviderSettingsResponse(
        enabled=provider.enabled if provider else False,
        base_url=provider.base_url if provider else "",
        api_key_configured=bool(provider and provider.api_key_ciphertext),
        api_key_last4=provider.api_key_last4 if provider else None,
        api_key_updated_at=provider.api_key_updated_at if provider else None,
        updated_at=provider.updated_at if provider else None,
    )
    return UserSettingsResponse(
        ai_provider=provider_response,
        models=[
            UserAiModelSettingsResponse(
                id=model.id,
                model_id=model.model_id,
                label=model.label,
                supports_vision=model.supports_vision,
                enabled=model.enabled,
            )
            for model in models
        ],
        task_profiles=[
            UserAiTaskProfileSettings(task=profile.task, model_id=profile.model_id, enabled=profile.enabled)  # type: ignore[arg-type]
            for profile in profiles
        ],
    )
