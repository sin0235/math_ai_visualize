import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin_user, require_trusted_origin
from app.db.session import DatabaseClient, get_database
from app.schemas.scene import AiModelInfo, ModelScanRequest, ModelScanResponse, ProviderModelScanRequest, RuntimeSettings
from app.services.model_registry import resolve_effective_settings
from app.services.model_scan import list_provider_models_with_warnings
from app.services.provider_logging import redact_sensitive, truncate_text

router = APIRouter(prefix="/api/ai", tags=["ai-models"])
MODEL_SCAN_TIMEOUT_SECONDS = 110


@router.post("/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin), Depends(require_admin_user)])
async def scan_provider_models(
    request: ProviderModelScanRequest,
    db: DatabaseClient = Depends(get_database),
) -> ModelScanResponse:
    return await _scan_models(db, request.runtime_settings, request.provider)


@router.post("/router9/models/scan", response_model=ModelScanResponse, dependencies=[Depends(require_trusted_origin), Depends(require_admin_user)])
async def scan_router9_models(
    request: ModelScanRequest,
    db: DatabaseClient = Depends(get_database),
) -> ModelScanResponse:
    return await _scan_models(db, request.runtime_settings, "router9")


async def _scan_models(db: DatabaseClient, runtime_settings: RuntimeSettings | None, provider: str) -> ModelScanResponse:
    try:
        async with asyncio.timeout(MODEL_SCAN_TIMEOUT_SECONDS):
            effective_settings = await resolve_effective_settings(db, runtime_settings)
            result = await list_provider_models_with_warnings(effective_settings, provider)
    except TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "model_scan_timeout",
                "message": f"Quét model {provider} quá {MODEL_SCAN_TIMEOUT_SECONDS} giây. Provider hoặc gateway phản hồi quá chậm.",
            },
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        message = truncate_text(redact_sensitive(str(error) or error.__class__.__name__), 500)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "model_scan_failed", "message": f"Không thể quét model {provider}: {message}"},
        ) from error
    return ModelScanResponse(models=_unique_models(result.models, provider), warnings=result.warnings)


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
