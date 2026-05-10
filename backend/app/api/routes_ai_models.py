from fastapi import APIRouter, Depends

from app.api.deps import require_admin_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.schemas.scene import ModelScanRequest, ModelScanResponse, ProviderModelScanRequest
from app.services.model_registry import resolve_effective_settings
from app.services.model_scan import list_provider_models
from app.services.router9_client import Router9Client

router = APIRouter(prefix="/api/ai", tags=["ai-models"])


@router.post("/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_provider_models(
    request: ProviderModelScanRequest,
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ModelScanResponse:
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    models = await list_provider_models(effective_settings, request.provider)
    return ModelScanResponse(provider=request.provider, models=models)


@router.post("/router9/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_router9_models(
    request: ModelScanRequest,
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ModelScanResponse:
    effective_settings = await resolve_effective_settings(db, request.runtime_settings)
    models = await Router9Client(effective_settings).list_models()
    return ModelScanResponse(provider="router9", models=models)
