import json
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import DatabaseClient, get_database
from app.schemas.auth import SystemAiSettings
from app.services.model_registry import effective_provider_default_model, load_model_registry, provider_is_enabled, registry_from_settings, resolve_task_profile
from app.schemas.scene import (
    OpenRouterSettingsDefaults,
    ProviderSettingsDefaults,
    OcrSettingsDefaults,
    Router9SettingsDefaults,
    FeatureFlagsDefaults,
    SettingsDefaultsResponse,
)
from app.services.system_settings import load_feature_flags

router = APIRouter(prefix="/api/settings", tags=["settings"])
OCR_PROVIDERS = {"local", "openrouter", "router9", "nvidia", "ollama", "openai_compat"}


@router.get("/defaults", response_model=SettingsDefaultsResponse)
async def get_settings_defaults(db: DatabaseClient = Depends(get_database)) -> SettingsDefaultsResponse:
    settings = get_settings()
    registry = await load_model_registry(db, settings) if getattr(db, "backend", settings.database_backend) == settings.database_backend else registry_from_settings(settings)
    ocr_profile = resolve_task_profile(registry, "ocr")
    ocr_provider, ocr_model = registry_ocr_default(registry, settings, ocr_profile)
    feature_flags = await load_feature_flags(db)
    return SettingsDefaultsResponse(
        app_name=settings.app_name,
        default_provider=registry_default_provider(registry, settings.ai_provider),
        openrouter=OpenRouterSettingsDefaults(
            api_key_configured=registry_api_key_configured(registry, "openrouter", settings.openrouter_api_key),
            base_url=registry_provider_base_url(registry, "openrouter", settings.openrouter_base_url),
            model=registry_provider_model(registry, "openrouter", settings.openrouter_text_model),
            vision_model=ocr_profile.model_id if ocr_profile and ocr_profile.provider_id == "openrouter" and ocr_profile.model_id else settings.openrouter_vision_model,
            http_referer=settings.openrouter_http_referer,
            x_title=settings.openrouter_x_title,
            reasoning_enabled=bool(registry.settings.get("openrouter_reasoning_enabled", settings.openrouter_reasoning_enabled)),
            scanned_models=registry.scanned_model_infos("openrouter"),
            allowed_model_ids=registry.allowed_model_ids("openrouter"),
        ),
        nvidia=ProviderSettingsDefaults(
            api_key_configured=registry_api_key_configured(registry, "nvidia", settings.nvidia_api_key),
            base_url=registry_provider_base_url(registry, "nvidia", settings.nvidia_base_url),
            model=registry_provider_model(registry, "nvidia", settings.nvidia_text_model),
            scanned_models=registry.scanned_model_infos("nvidia"),
            allowed_model_ids=registry.allowed_model_ids("nvidia"),
        ),
        ollama=ProviderSettingsDefaults(
            api_key_configured=registry_api_key_configured(registry, "ollama", settings.ollama_api_key),
            base_url=registry_provider_base_url(registry, "ollama", settings.ollama_base_url),
            model=registry_provider_model(registry, "ollama", settings.ollama_text_model),
            scanned_models=registry.scanned_model_infos("ollama"),
            allowed_model_ids=registry.allowed_model_ids("ollama"),
        ),
        openai_compat=ProviderSettingsDefaults(
            api_key_configured=registry_api_key_configured(registry, "openai_compat", settings.openai_compat_api_key),
            base_url=registry_provider_base_url(registry, "openai_compat", settings.openai_compat_base_url),
            model=registry_provider_model(registry, "openai_compat", settings.openai_compat_text_model),
            scanned_models=registry.scanned_model_infos("openai_compat"),
            allowed_model_ids=registry.allowed_model_ids("openai_compat"),
        ),
        router9=Router9SettingsDefaults(
            api_key_configured=registry_api_key_configured(registry, "router9", settings.router9_api_key),
            base_url=registry_provider_base_url(registry, "router9", settings.router9_base_url),
            model=registry_provider_model(registry, "router9", settings.router9_text_model),
            only_mode=bool(registry.settings.get("router9_only", settings.router9_only)),
            allowed_model_ids=registry.allowed_model_ids("router9"),
            scanned_models=registry.scanned_model_infos("router9"),
        ),
        ocr=OcrSettingsDefaults(
            provider=ocr_provider,
            model=ocr_model,
            max_image_mb=int(registry.settings.get("ocr_max_image_mb", 5)),
        ),
        registry_providers=[provider.__dict__ for provider in registry.providers.values()],
        registry_models=[model.__dict__ for models in registry.models.values() for model in models],
        registry_task_profiles=[profile.__dict__ for profile in registry.task_profiles.values()],
        registry_legacy_ai_settings_present=registry.legacy_used,
        feature_flags=FeatureFlagsDefaults(
            maintenance_mode=feature_flags.maintenance_mode,
            maintenance_message=feature_flags.maintenance_message,
            google_oauth_enabled=feature_flags.google_oauth_enabled,
            ocr_enabled=feature_flags.ocr_enabled,
            render_enabled=feature_flags.render_enabled,
            turnstile_enabled=bool(feature_flags.turnstile_enabled and settings.turnstile_secret_key and settings.turnstile_site_key),
            turnstile_site_key=settings.turnstile_site_key if feature_flags.turnstile_enabled and settings.turnstile_secret_key and settings.turnstile_site_key else None,
        ),
    )


@dataclass(frozen=True)
class LoadedAiSettings:
    settings: SystemAiSettings
    raw: dict[str, Any]


async def load_system_ai_settings(db: DatabaseClient) -> LoadedAiSettings:
    row = await db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", ["ai_settings"])
    if row is None:
        return LoadedAiSettings(SystemAiSettings(), {})
    try:
        value = json.loads(str(row["value_json"]))
        if not isinstance(value, dict):
            return LoadedAiSettings(SystemAiSettings(), {})
        return LoadedAiSettings(SystemAiSettings.model_validate(value), value)
    except (json.JSONDecodeError, ValidationError):
        return LoadedAiSettings(SystemAiSettings(), {})


def has_key(raw: dict[str, Any], key: str) -> bool:
    return key in raw


def has_provider_key(raw: dict[str, Any], provider: str, key: str) -> bool:
    value = raw.get(provider)
    return isinstance(value, dict) and key in value


def provider_api_key_configured(db_value: str | None, env_value: str | None) -> bool:
    return bool((db_value or "").strip() or (env_value or "").strip())


def registry_api_key_configured(registry: Any, provider_id: str, env_value: str | None) -> bool:
    provider = registry.providers.get(provider_id)
    return bool((env_value or "").strip() or (provider and provider.api_key_configured))


def registry_default_provider(registry: Any, fallback: str | None) -> str:
    value = registry.settings.get("default_provider")
    if isinstance(value, str) and value and value in {"auto", "mock"}:
        return value
    if isinstance(value, str) and value and provider_is_enabled(registry, value):
        return value
    return fallback if fallback in {"auto", "mock"} else "auto"


def registry_provider_base_url(registry: Any, provider_id: str, fallback: str | None) -> str:
    provider = registry.providers.get(provider_id)
    return (provider.base_url if provider and provider.base_url else fallback) or ""


def registry_provider_model(registry: Any, provider_id: str, fallback: str | None) -> str:
    provider = registry.providers.get(provider_id)
    default_model = provider.default_model_id if provider and provider.default_model_id else fallback or ""
    return effective_provider_default_model(registry, provider_id, default_model)



def merge_text(db_value: str | None, env_value: str | None, raw: dict[str, Any], key: str) -> str:
    if has_key(raw, key) and db_value:
        return db_value
    return env_value or ""


def merge_bool(db_value: bool, env_value: bool, raw: dict[str, Any], key: str) -> bool:
    if has_key(raw, key):
        return db_value
    return env_value


def merge_provider_text(db_value: str | None, env_value: str | None, raw: dict[str, Any], provider: str, key: str) -> str:
    if has_provider_key(raw, provider, key) and db_value:
        return db_value
    return env_value or ""


def merge_provider_bool(db_value: bool, env_value: bool, raw: dict[str, Any], provider: str, key: str) -> bool:
    if has_provider_key(raw, provider, key):
        return db_value
    return env_value


def merge_provider_list(db_value: list[str], env_value: list[str], raw: dict[str, Any], provider: str, key: str) -> list[str]:
    if has_provider_key(raw, provider, key):
        return db_value
    return env_value


def provider_default(registry: Any, provider_id: str, field: str, fallback: str | None, raw: dict[str, Any] | None = None) -> str:
    """If raw ai_settings includes the provider field, use merged fallback instead of ai_providers registry."""
    fb = fallback or ""
    if raw is not None and field in ("base_url", "model") and has_provider_key(raw, provider_id, field):
        if field == "model":
            return allowed_provider_default(registry, provider_id, fb)
        return fb
    provider = registry.providers.get(provider_id)
    if provider is None:
        return fb
    if field == "base_url":
        return (provider.base_url or "") or fb
    if field == "model":
        return allowed_provider_default(registry, provider_id, (provider.default_model_id or "") or fb)
    return fb


def allowed_provider_default(registry: Any, provider_id: str, default_model_id: str) -> str:
    allowed_model_ids = registry.allowed_model_ids(provider_id) if hasattr(registry, "allowed_model_ids") else []
    if allowed_model_ids and default_model_id not in allowed_model_ids:
        return allowed_model_ids[0]
    return default_model_id


def registry_ocr_default(registry: Any, settings: Any, ocr_profile: Any) -> tuple[str, str]:
    if ocr_profile and ocr_profile.provider_id in OCR_PROVIDERS and ocr_profile.model_id:
        return ocr_profile.provider_id, ocr_profile.model_id

    if getattr(settings, "local_ocr_enabled", False) and getattr(settings, "local_ocr_prefer", "auto") in {"auto", "always"}:
        return "local", getattr(settings, "local_ocr_model_name", "paddleocr+pix2tex")

    if settings.router9_ocr_model:
        return "router9", settings.router9_ocr_model

    openrouter_vision = getattr(settings, "openrouter_vision_model", "") or ""
    if openrouter_vision:
        return "openrouter", openrouter_vision

    for provider_id in ("router9", "openrouter", "nvidia", "ollama", "openai_compat"):
        provider = registry.providers.get(provider_id)
        default_model = effective_provider_default_model(registry, provider_id, provider.default_model_id if provider else "")
        if default_model:
            return provider_id, default_model

    return "openrouter", ""


def dump_scanned_models(models: list[Any]) -> list[dict[str, Any]]:
    return [model.model_dump() if hasattr(model, "model_dump") else dict(model) for model in models]
