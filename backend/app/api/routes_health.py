from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ai/status")
def ai_status() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "provider": settings.ai_provider,
        "openrouter_configured": bool(settings.openrouter_api_key),
        "openrouter_text_model": settings.openrouter_text_model,
        "nvidia_configured": bool(settings.nvidia_api_key),
        "nvidia_text_model": settings.nvidia_text_model,
    }
