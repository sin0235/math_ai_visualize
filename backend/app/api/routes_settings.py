import json

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
    ai_settings = await load_system_ai_settings(db)
    return SettingsDefaultsResponse(
        app_name=settings.app_name,
        default_provider=ai_settings.default_provider or settings.ai_provider,
        openrouter=OpenRouterSettingsDefaults(
            api_key_configured=bool(settings.openrouter_api_key),
            base_url=ai_settings.openrouter.base_url or settings.openrouter_base_url,
            model=ai_settings.openrouter.model or settings.openrouter_text_model,
            vision_model=settings.openrouter_vision_model,
            http_referer=ai_settings.openrouter_http_referer or settings.openrouter_http_referer,
            x_title=ai_settings.openrouter_x_title or settings.openrouter_x_title,
            reasoning_enabled=ai_settings.openrouter_reasoning_enabled,
            scanned_models=ai_settings.openrouter.scanned_models,
            allowed_model_ids=ai_settings.openrouter.allowed_model_ids,
        ),
        nvidia=ProviderSettingsDefaults(
            api_key_configured=bool(settings.nvidia_api_key),
            base_url=ai_settings.nvidia.base_url or settings.nvidia_base_url,
            model=ai_settings.nvidia.model or settings.nvidia_text_model,
            scanned_models=ai_settings.nvidia.scanned_models,
            allowed_model_ids=ai_settings.nvidia.allowed_model_ids,
        ),
        ollama=ProviderSettingsDefaults(
            api_key_configured=bool(settings.ollama_api_key),
            base_url=ai_settings.ollama.base_url or settings.ollama_base_url,
            model=ai_settings.ollama.model or settings.ollama_text_model,
            scanned_models=ai_settings.ollama.scanned_models,
            allowed_model_ids=ai_settings.ollama.allowed_model_ids,
        ),
        router9=Router9SettingsDefaults(
            api_key_configured=bool(settings.router9_api_key),
            base_url=ai_settings.router9.base_url or settings.router9_base_url,
            model=ai_settings.router9.model or settings.router9_text_model,
            only_mode=ai_settings.router9.only_mode,
            allowed_model_ids=ai_settings.router9.allowed_model_ids,
            scanned_models=ai_settings.router9.scanned_models,
        ),
        ocr=OcrSettingsDefaults(
            provider=ai_settings.ocr.provider,
            model=ai_settings.ocr.model or (ai_settings.router9.model if ai_settings.ocr.provider == "router9" else settings.openrouter_vision_model),
            max_image_mb=ai_settings.ocr.max_image_mb,
        ),
    )


async def load_system_ai_settings(db: DatabaseClient) -> SystemAiSettings:
    row = await db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", ["ai_settings"])
    if row is None:
        return SystemAiSettings()
    try:
        value = json.loads(str(row["value_json"]))
        return SystemAiSettings.model_validate(value)
    except (json.JSONDecodeError, ValidationError):
        return SystemAiSettings()
