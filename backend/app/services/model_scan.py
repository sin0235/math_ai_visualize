from app.core.config import Settings
from app.schemas.scene import AiModelInfo, ModelScanProvider
from app.services.ai_providers import CAPABILITY_KEYS, OLLAMA_CAPABILITY_KEYS, ModelListResult, get_provider_adapter, _extract_capabilities


async def list_provider_models(settings: Settings, provider: ModelScanProvider) -> list[AiModelInfo]:
    return (await list_provider_models_with_warnings(settings, provider)).models


async def list_provider_models_with_warnings(settings: Settings, provider: str) -> ModelListResult:
    return await get_provider_adapter(provider).list_models(settings)