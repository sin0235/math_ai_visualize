import base64
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.scene import OcrProvider
from app.services.nvidia_client import NvidiaClient
from app.services.openrouter_client import OpenRouterClient
from app.services.router9_client import Router9Client
from app.services.provider_logging import redact_sensitive

_IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class OcrResult:
    text: str
    provider: OcrProvider
    model: str
    warnings: list[str]


@dataclass(frozen=True)
class OcrAttempt:
    provider: str
    model: str
    message: str

    def warning(self) -> str:
        return f"{self.provider}/{self.model}: {_short_error(self.message)}"


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
    attempts: list[OcrAttempt] = []
    selected_provider: OcrProvider = provider or "openrouter"

    if settings.router9_only and selected_provider != "router9":
        raise RuntimeError("9router-only đang bật nên OCR không fallback sang provider khác. Hãy chọn OCR provider 9router hoặc tắt 9router-only.")

    if selected_provider == "router9":
        result = await _try_router9_ocr(image_data_url, settings, model, attempts)
        if result is not None:
            return result
        if settings.router9_only or model is not None:
            raise RuntimeError(_format_ocr_failure("OCR 9router thất bại.", attempts, settings.router9_only))

    elif provider is None and model is None and settings.router9_api_key:
        result = await _try_router9_ocr(image_data_url, settings, None, attempts)
        if result is not None:
            return result

    if selected_provider == "openrouter" or selected_provider == "router9":
        result = await _try_openrouter_ocr(image_data_url, settings, model, attempts)
        if result is not None:
            return result
        if model is not None:
            raise RuntimeError(_format_ocr_failure("OCR OpenRouter thất bại với model đã chọn.", attempts, settings.router9_only))

    for nvidia_model in ("google/gemma-3n-e2b-it", "mistralai/mistral-large-3-675b-instruct-2512"):
        try:
            text = await NvidiaClient(settings, model=nvidia_model).ocr_image(image_data_url, nvidia_model)
            return OcrResult(text=text, provider="openrouter", model=f"nvidia:{nvidia_model}", warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("nvidia", nvidia_model, str(error)))

    raise RuntimeError(_format_ocr_failure("OCR thất bại qua tất cả provider fallback.", attempts, settings.router9_only))


async def _try_router9_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_model: str | None,
    attempts: list[OcrAttempt],
) -> OcrResult | None:
    selected_model = explicit_model or settings.router9_ocr_model or settings.router9_text_model
    if not selected_model:
        attempts.append(OcrAttempt("router9", "<none>", "Chưa chọn model OCR 9router."))
        return None
    try:
        text = await Router9Client(settings, model=selected_model).ocr_image(image_data_url, selected_model)
        return OcrResult(text=text, provider="router9", model=selected_model, warnings=_attempt_warnings(attempts))
    except RuntimeError as error:
        attempts.append(OcrAttempt("router9", selected_model, str(error)))
        return None


async def _try_openrouter_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_model: str | None,
    attempts: list[OcrAttempt],
) -> OcrResult | None:
    models = [explicit_model or settings.openrouter_vision_model]
    if explicit_model is None and settings.openrouter_vision_fallback_model not in models:
        models.append(settings.openrouter_vision_fallback_model)

    for selected_model in models:
        try:
            text = await OpenRouterClient(settings).ocr_image(image_data_url, selected_model)
            return OcrResult(text=text, provider="openrouter", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("openrouter", selected_model, str(error)))
    return None


def _attempt_warnings(attempts: list[OcrAttempt]) -> list[str]:
    return [f"OCR fallback: {attempt.warning()}" for attempt in attempts]


def _format_ocr_failure(message: str, attempts: list[OcrAttempt], router9_only: bool) -> str:
    details = " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"
    suggestions = "Hãy kiểm tra API key/quota, chọn model OCR khác hoặc quét lại model 9router."
    if router9_only:
        suggestions += " Nếu muốn dùng OpenRouter/NVIDIA fallback, hãy tắt 9router-only."
    return f"{message} Đã thử: {details}. {suggestions}"


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", redact_sensitive(message)).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")
