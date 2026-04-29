from fastapi import APIRouter, HTTPException

from app.core.config import get_settings, merge_runtime_settings
from app.schemas.scene import OcrRequest, OcrResponse
from app.services.ocr import extract_text_from_image

router = APIRouter(prefix="/api", tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse)
async def ocr_image(request: OcrRequest) -> OcrResponse:
    settings = merge_runtime_settings(get_settings(), request.runtime_settings)
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
