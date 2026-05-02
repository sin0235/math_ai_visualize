from fastapi import APIRouter, HTTPException

from app.core.config import get_settings, merge_runtime_settings
from app.schemas.scene import OcrRequest, OcrResponse
from app.services.ocr import extract_text_from_image

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse)
async def ocr_image(request: OcrRequest) -> OcrResponse:
    settings = merge_runtime_settings(get_settings(), sanitize_public_runtime_settings(request.runtime_settings))
    try:
        result = await extract_text_from_image(
            request.image_data_url,
            settings,
            request.ocr_provider,
            request.ocr_model,
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return OcrResponse(text=result.text, provider=result.provider, model=result.model, warnings=result.warnings)


def sanitize_public_runtime_settings(runtime_settings: object):
    if runtime_settings is None or not hasattr(runtime_settings, "model_dump"):
        return None
    data = runtime_settings.model_dump(mode="json")
    return type(runtime_settings).model_validate(
        {
            "default_provider": data.get("default_provider"),
            "openrouter": {"model": (data.get("openrouter") or {}).get("model")},
            "nvidia": {"model": (data.get("nvidia") or {}).get("model")},
            "ollama": {"model": (data.get("ollama") or {}).get("model")},
            "router9": {"model": (data.get("router9") or {}).get("model")},
        }
    )
