from fastapi import APIRouter, HTTPException

from app.core.config import get_settings, merge_runtime_settings
from app.schemas.scene import ModelScanRequest, ModelScanResponse, ProviderModelScanRequest
from app.services.model_scan import list_provider_models
from app.services.router9_client import Router9Client

router = APIRouter(prefix="/api/ai", tags=["ai-models"])


@router.post("/models/scan", response_model=ModelScanResponse)
async def scan_provider_models(request: ProviderModelScanRequest) -> ModelScanResponse:
    settings = merge_runtime_settings(get_settings(), request.runtime_settings)
    try:
        models = await list_provider_models(settings, request.provider)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ModelScanResponse(models=models)


@router.post("/router9/models/scan", response_model=ModelScanResponse)
async def scan_router9_models(request: ModelScanRequest) -> ModelScanResponse:
    settings = merge_runtime_settings(get_settings(), request.runtime_settings)
    try:
        models = await Router9Client(settings).list_models()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ModelScanResponse(models=models)
