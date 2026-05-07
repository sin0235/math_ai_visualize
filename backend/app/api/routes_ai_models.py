from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_admin_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.services.model_registry import resolve_effective_settings, save_provider_check, upsert_scanned_models
from app.schemas.scene import ModelScanRequest, ModelScanResponse, ProviderModelScanRequest
from app.services.model_scan import list_provider_models
from app.services.router9_client import Router9Client

router = APIRouter(prefix="/api/ai", tags=["ai-models"])


@router.post("/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_provider_models(request: ProviderModelScanRequest, _: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> ModelScanResponse:
    settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        models = await list_provider_models(settings, request.provider)
        await upsert_scanned_models(db, request.provider, models)
        await save_provider_check(db, request.provider, "ok", f"Đã quét {len(models)} model.")
    except RuntimeError as error:
        await save_provider_check(db, request.provider, "error", str(error))
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ModelScanResponse(models=models)


@router.post("/router9/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin)])
async def scan_router9_models(request: ModelScanRequest, _: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> ModelScanResponse:
    settings = await resolve_effective_settings(db, request.runtime_settings)
    try:
        models = await Router9Client(settings).list_models()
        await upsert_scanned_models(db, "router9", models)
        await save_provider_check(db, "router9", "ok", f"Đã quét {len(models)} model.")
    except RuntimeError as error:
        await save_provider_check(db, "router9", "error", str(error))
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ModelScanResponse(models=models)
