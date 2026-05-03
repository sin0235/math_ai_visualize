import json
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import DatabaseClient, get_database
from app.schemas.auth import SystemAiSettings
from app.schemas.scene import (
    OpenRouterSettingsDefaults,
    ProviderSettingsDefaults,
    OcrSettingsDefaults,
    Router9SettingsDefaults,
    SettingsDefaultsResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/defaults", response_model=SettingsDefaultsResponse)
async def get_settings_defaults(db: DatabaseClient = Depends(get_database)) -> SettingsDefaultsResponse:
    settings = get_settings()
    loaded = await load_system_ai_settings(db)
    ai_settings = loaded.settings
    return SettingsDefaultsResponse(
        app_name=settings.app_name,
        default_provider=merge_text(ai_settings.default_provider, settings.ai_provider, loaded.raw, "default_provider"),
        openrouter=OpenRouterSettingsDefaults(
            api_key_configured=bool(settings.openrouter_api_key),
            base_url=merge_provider_text(ai_settings.openrouter.base_url, settings.openrouter_base_url, loaded.raw, "openrouter", "base_url"),
            model=merge_provider_text(ai_settings.openrouter.model, settings.openrouter_text_model, loaded.raw, "openrouter", "model"),
            vision_model=settings.openrouter_vision_model,
            http_referer=merge_text(ai_settings.openrouter_http_referer, settings.openrouter_http_referer, loaded.raw, "openrouter_http_referer"),
            x_title=merge_text(ai_settings.openrouter_x_title, settings.openrouter_x_title, loaded.raw, "openrouter_x_title"),
            reasoning_enabled=merge_bool(ai_settings.openrouter_reasoning_enabled, settings.openrouter_reasoning_enabled, loaded.raw, "openrouter_reasoning_enabled"),
            scanned_models=dump_scanned_models(ai_settings.openrouter.scanned_models),
            allowed_model_ids=merge_provider_list(ai_settings.openrouter.allowed_model_ids, [], loaded.raw, "openrouter", "allowed_model_ids"),
        ),
        nvidia=ProviderSettingsDefaults(
            api_key_configured=bool(settings.nvidia_api_key),
            base_url=merge_provider_text(ai_settings.nvidia.base_url, settings.nvidia_base_url, loaded.raw, "nvidia", "base_url"),
            model=merge_provider_text(ai_settings.nvidia.model, settings.nvidia_text_model, loaded.raw, "nvidia", "model"),
            scanned_models=dump_scanned_models(ai_settings.nvidia.scanned_models),
            allowed_model_ids=merge_provider_list(ai_settings.nvidia.allowed_model_ids, [], loaded.raw, "nvidia", "allowed_model_ids"),
        ),
        ollama=ProviderSettingsDefaults(
            api_key_configured=bool(settings.ollama_api_key),
            base_url=merge_provider_text(ai_settings.ollama.base_url, settings.ollama_base_url, loaded.raw, "ollama", "base_url"),
            model=merge_provider_text(ai_settings.ollama.model, settings.ollama_text_model, loaded.raw, "ollama", "model"),
            scanned_models=dump_scanned_models(ai_settings.ollama.scanned_models),
            allowed_model_ids=merge_provider_list(ai_settings.ollama.allowed_model_ids, [], loaded.raw, "ollama", "allowed_model_ids"),
        ),
        router9=Router9SettingsDefaults(
            api_key_configured=bool(settings.router9_api_key),
            base_url=merge_provider_text(ai_settings.router9.base_url, settings.router9_base_url, loaded.raw, "router9", "base_url"),
            model=merge_provider_text(ai_settings.router9.model, settings.router9_text_model, loaded.raw, "router9", "model"),
            only_mode=merge_provider_bool(ai_settings.router9.only_mode, settings.router9_only, loaded.raw, "router9", "only_mode"),
            allowed_model_ids=merge_provider_list(ai_settings.router9.allowed_model_ids, settings.router9_allowed_models, loaded.raw, "router9", "allowed_model_ids"),
            scanned_models=dump_scanned_models(ai_settings.router9.scanned_models),
        ),
        ocr=OcrSettingsDefaults(
            provider=ai_settings.ocr.provider,
            model=merge_provider_text(ai_settings.ocr.model, settings.router9_ocr_model or settings.router9_text_model if ai_settings.ocr.provider == "router9" else settings.openrouter_vision_model, loaded.raw, "ocr", "model"),
            max_image_mb=ai_settings.ocr.max_image_mb,
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


def dump_scanned_models(models: list[Any]) -> list[dict[str, Any]]:
    return [model.model_dump() if hasattr(model, "model_dump") else dict(model) for model in models]
