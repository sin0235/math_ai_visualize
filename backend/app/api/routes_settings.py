from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.scene import (
    OpenRouterSettingsDefaults,
    ProviderSettingsDefaults,
    Router9SettingsDefaults,
    SettingsDefaultsResponse,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/defaults", response_model=SettingsDefaultsResponse)
def get_settings_defaults() -> SettingsDefaultsResponse:
    settings = get_settings()
    return SettingsDefaultsResponse(
        app_name=settings.app_name,
        default_provider=settings.ai_provider,
        openrouter=OpenRouterSettingsDefaults(
            api_key_configured=bool(settings.openrouter_api_key),
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_text_model,
            vision_model=settings.openrouter_vision_model,
            http_referer=settings.openrouter_http_referer,
            x_title=settings.openrouter_x_title,
            reasoning_enabled=settings.openrouter_reasoning_enabled,
        ),
        nvidia=ProviderSettingsDefaults(
            api_key_configured=bool(settings.nvidia_api_key),
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_text_model,
        ),
        ollama=ProviderSettingsDefaults(
            api_key_configured=bool(settings.ollama_api_key),
            base_url=settings.ollama_base_url,
            model=settings.ollama_text_model,
        ),
        router9=Router9SettingsDefaults(
            api_key_configured=bool(settings.router9_api_key),
            base_url=settings.router9_base_url,
            model=settings.router9_text_model,
            only_mode=settings.router9_only,
            allowed_model_ids=settings.router9_allowed_models,
        ),
    )
