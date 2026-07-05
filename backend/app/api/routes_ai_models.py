from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.deps import require_admin_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.model_registry import ModelRegistryRepository
from app.schemas.scene import ModelScanRequest, ModelScanResponse, ProviderModelScanRequest
from app.schemas.scene import AiModelInfo
from app.services.ai_fallback import provider_configured
from app.services.ai_providers import get_provider_adapter
from app.services.model_registry import resolve_effective_settings, save_provider_config, upsert_scanned_models
from app.services.model_scan import list_provider_models_with_warnings

router = APIRouter(prefix="/api/ai", tags=["ai-models"])


@router.post("/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_provider_models(
    request: ProviderModelScanRequest,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ModelScanResponse:
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    result = await list_provider_models_with_warnings(effective_settings, request.provider)
    models = _unique_models(result.models, request.provider)
    await _persist_scan(db, admin.id, effective_settings, request.provider, models, result.warnings)
    return ModelScanResponse(models=models, warnings=result.warnings)


@router.post("/router9/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_router9_models(
    request: ModelScanRequest,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ModelScanResponse:
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    result = await get_provider_adapter("router9").list_models(effective_settings)
    models = _unique_models(result.models, "router9")
    await _persist_scan(db, admin.id, effective_settings, "router9", models, result.warnings)
    return ModelScanResponse(models=models, warnings=result.warnings)


async def _persist_scan(db: DatabaseClient, user_id: str, settings: Settings, provider: str, models: list[AiModelInfo], warnings: list[str]) -> None:
    model_ids = [model.id for model in models]
    default_model = _provider_default_model(settings, provider, model_ids)
    await save_provider_config(
        db,
        provider,
        _provider_base_url(settings, provider),
        default_model,
        api_key_configured=provider_configured(_provider_api_key(settings, provider)),
    )
    await upsert_scanned_models(db, provider, models)
    await ModelRegistryRepository(db).record_model_scan_job(
        str(uuid4()),
        user_id,
        provider,
        _provider_base_url(settings, provider),
        _safe_runtime_snapshot(settings, provider),
        models,
        warnings,
    )


def _unique_models(models: list[AiModelInfo], provider: str) -> list[AiModelInfo]:
    seen: set[str] = set()
    unique: list[AiModelInfo] = []
    for model in models:
        model_id = model.id.strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        unique.append(model.model_copy(update={"id": model_id, "provider": provider}))
    return unique


def _provider_base_url(settings: Settings, provider: str) -> str:
    return str(getattr(settings, f"{provider}_base_url", "") or "")


def _provider_api_key(settings: Settings, provider: str) -> str | None:
    return getattr(settings, f"{provider}_api_key", None)


def _provider_default_model(settings: Settings, provider: str, model_ids: list[str]) -> str:
    field = "router9_text_model" if provider == "router9" else f"{provider}_text_model"
    configured = str(getattr(settings, field, "") or "").strip()
    if configured and (not model_ids or configured in model_ids):
        return configured
    return model_ids[0] if model_ids else configured


def _safe_runtime_snapshot(settings: Settings, provider: str) -> dict[str, str]:
    field = "router9_text_model" if provider == "router9" else f"{provider}_text_model"
    return {
        "provider": provider,
        "base_url": _provider_base_url(settings, provider),
        "model": str(getattr(settings, field, "") or ""),
    }
