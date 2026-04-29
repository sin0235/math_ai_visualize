import base64
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.scene import OcrProvider
from app.services.openrouter_client import OpenRouterClient
from app.services.router9_client import Router9Client

_IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class OcrResult:
    text: str
    provider: OcrProvider
    model: str


def validate_image_data_url(image_data_url: str) -> None:
    match = _IMAGE_DATA_URL_RE.match(image_data_url.strip())
    if not match:
        raise ValueError("Ảnh OCR phải là data URL base64 dạng PNG/JPEG/WebP/GIF.")
    encoded = re.sub(r"\s+", "", match.group(2))
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("Dữ liệu ảnh OCR không phải base64 hợp lệ.") from error
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise ValueError("Ảnh OCR vượt quá giới hạn 8MB.")


async def extract_text_from_image(
    image_data_url: str,
    settings: Settings,
    provider: OcrProvider | None = None,
    model: str | None = None,
) -> OcrResult:
    validate_image_data_url(image_data_url)
    selected_provider: OcrProvider = provider or "openrouter"
    if selected_provider == "router9":
        selected_model = model or settings.router9_text_model
        if not selected_model:
            raise RuntimeError("Chưa chọn model OCR 9router.")
        text = await Router9Client(settings, model=selected_model).ocr_image(image_data_url, selected_model)
        return OcrResult(text=text, provider=selected_provider, model=selected_model)

    selected_model = model or settings.openrouter_vision_model
    text = await OpenRouterClient(settings).ocr_image(image_data_url, selected_model)
    return OcrResult(text=text, provider=selected_provider, model=selected_model)
