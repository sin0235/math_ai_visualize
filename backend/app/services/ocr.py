import asyncio
import base64
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.scene import OcrMode, OcrProvider
from app.services.ai_fallback import openrouter_vision_candidates, provider_configured, router9_ocr_candidates
from app.services.model_provider import canonicalize_model_ref, explicit_provider_from_model, normalize_model_for_provider, resolve_ocr_provider
from app.services.nvidia_client import NvidiaClient
from app.services.ollama_client import OllamaClient
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import OpenRouterClient
from app.services.router9_client import Router9Client
from app.services.provider_logging import redact_sensitive

_IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
DIAGRAM_OCR_SYSTEM_PROMPT = """
Bạn là bộ mô tả hình vẽ toán học tiếng Việt.
Nhìn ảnh hình vẽ tay/in và chuyển thành đề bài hình học có thể dựng lại.
Nêu rõ điểm, đoạn, đường thẳng, mặt phẳng, góc vuông, song song, vuông góc, độ dài, tọa độ nếu thấy.
Không giải bài, không thêm markdown, không bọc code fence.
Nếu ảnh có cả đề bài và hình, kết hợp thành một mô tả đề bài ngắn gọn.
""".strip()
DIAGRAM_OCR_USER_TEXT = "Mô tả hình vẽ này thành đề bài hình học để dựng lại."
PROBLEM_OCR_USER_TEXT = "Trích xuất nguyên văn đề toán trong ảnh."


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
        raise ValueError("Ảnh OCR vượt quá giới hạn 5MB.")


async def extract_text_from_image(
    image_data_url: str,
    settings: Settings,
    provider: OcrProvider | None = None,
    model: str | None = None,
    mode: OcrMode = "problem",
    fallback_models: list[str] | None = None,
) -> OcrResult:
    validate_image_data_url(image_data_url)
    attempts: list[OcrAttempt] = []
    auto_selection = provider is None and model is None
    selected_provider = "router9" if auto_selection and settings.router9_only else resolve_ocr_provider(provider, model)
    selected_model = canonicalize_model_ref(selected_provider, model, strict=True, allow_auto=False).model_id if model else None
    selected_models = _ocr_models_for_provider(selected_provider, selected_model, fallback_models)
    has_cross_provider_fallbacks = _has_cross_provider_fallbacks(fallback_models, selected_provider)
    explicit_model = model is not None
    system_prompt = DIAGRAM_OCR_SYSTEM_PROMPT if mode == "diagram" else None
    user_text = DIAGRAM_OCR_USER_TEXT if mode == "diagram" else PROBLEM_OCR_USER_TEXT

    if settings.router9_only and selected_provider != "router9":
        raise RuntimeError("9router-only đang bật nên OCR không fallback sang provider khác. Hãy chọn OCR provider 9router hoặc tắt 9router-only.")

    should_try_local = (
        settings.local_ocr_enabled
        and selected_provider == "local"
        or (
            settings.local_ocr_enabled
            and auto_selection
            and not settings.router9_only
            and settings.local_ocr_prefer in {"auto", "always"}
            and (settings.local_ocr_prefer == "always" or not settings.router9_api_key)
        )
    )
    if should_try_local:
        result = await _try_local_ocr(image_data_url, settings, selected_models, attempts, mode)
        if result is not None:
            return result
        if selected_provider == "local" and not settings.local_ocr_fallback_to_llm:
            raise RuntimeError(_format_ocr_failure("Local OCR thất bại hoặc confidence thấp.", attempts, settings.router9_only))

    if selected_provider == "router9":
        result = await _try_router9_ocr(image_data_url, settings, selected_models, attempts, system_prompt, user_text)
        if result is not None:
            return result
        if settings.router9_only or (explicit_model and not has_cross_provider_fallbacks):
            raise RuntimeError(_format_ocr_failure("OCR 9router thất bại.", attempts, settings.router9_only))

    if auto_selection and selected_provider != "router9" and settings.router9_api_key:
        result = await _try_router9_ocr(image_data_url, settings, None, attempts, system_prompt, user_text)
        if result is not None:
            return result

    provider_order = _ocr_provider_order(settings, selected_provider, provider is None and model is None, fallback_models)
    for fallback_provider in provider_order:
        provider_models = _ocr_models_for_provider(
            fallback_provider,
            selected_model if selected_provider == fallback_provider else None,
            fallback_models,
        )
        if fallback_provider != selected_provider and not auto_selection and fallback_models and not provider_models:
            continue
        if fallback_provider == "openrouter":
            result = await _try_openrouter_ocr(image_data_url, settings, provider_models, attempts, system_prompt, user_text)
        elif fallback_provider == "nvidia":
            result = await _try_nvidia_ocr(image_data_url, settings, provider_models, attempts, system_prompt, user_text)
        elif fallback_provider == "ollama":
            result = await _try_ollama_ocr(image_data_url, settings, provider_models, attempts, system_prompt, user_text)
        elif fallback_provider == "openai_compat":
            result = await _try_openai_compat_ocr(image_data_url, settings, provider_models, attempts, system_prompt, user_text)
        else:
            continue
        if result is not None:
            return result
        if explicit_model and fallback_provider == selected_provider and not has_cross_provider_fallbacks:
            raise RuntimeError(_format_ocr_failure(f"OCR {fallback_provider} thất bại với model đã chọn.", attempts, settings.router9_only))

    raise RuntimeError(_format_ocr_failure("OCR thất bại qua tất cả provider fallback.", attempts, settings.router9_only))


async def _try_local_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    mode: OcrMode,
) -> OcrResult | None:
    selected_model = (explicit_models or [settings.local_ocr_model_name])[0] or settings.local_ocr_model_name
    try:
        result = await _run_local_ocr(image_data_url, mode, settings)
    except RuntimeError as error:
        attempts.append(OcrAttempt("local", selected_model, str(error)))
        return None
    if result.confidence < settings.local_ocr_min_confidence:
        attempts.append(OcrAttempt("local", result.model, f"confidence thấp ({result.confidence:.2f} < {settings.local_ocr_min_confidence:.2f})"))
        return None
    warnings = [*result.warnings, *_attempt_warnings(attempts)]
    return OcrResult(text=result.text, provider="local", model=result.model, warnings=warnings)


async def _run_local_ocr(image_data_url: str, mode: OcrMode, settings: Settings):
    from app.services.ocr_pipeline.local_pipeline import run_local_ocr_sync

    timeout = max(1, int(settings.local_ocr_timeout_seconds))
    return await asyncio.wait_for(
        asyncio.to_thread(run_local_ocr_sync, image_data_url, mode, settings),
        timeout=timeout,
    )


async def _try_router9_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    system_prompt: str | None,
    user_text: str,
) -> OcrResult | None:
    models = explicit_models or _router9_ocr_model_candidates(settings, None)
    if not models:
        attempts.append(OcrAttempt("router9", "<none>", "Chưa chọn model OCR 9router."))
        return None
    for selected_model in models:
        try:
            client = Router9Client(settings, model=selected_model)
            if system_prompt is None and user_text == PROBLEM_OCR_USER_TEXT:
                text = await client.ocr_image(image_data_url, selected_model)
            else:
                text = await client.ocr_image(image_data_url, selected_model, system_prompt=system_prompt, user_text=user_text)
            return OcrResult(text=text, provider="router9", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("router9", selected_model, str(error)))
    return None


async def _try_openrouter_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    system_prompt: str | None,
    user_text: str,
) -> OcrResult | None:
    models = explicit_models or openrouter_vision_candidates(settings, None)

    for selected_model in models:
        try:
            client = OpenRouterClient(settings)
            if system_prompt is None and user_text == PROBLEM_OCR_USER_TEXT:
                text = await client.ocr_image(image_data_url, selected_model)
            else:
                text = await client.ocr_image(image_data_url, selected_model, system_prompt=system_prompt, user_text=user_text)
            return OcrResult(text=text, provider="openrouter", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("openrouter", selected_model, str(error)))
    return None


async def _try_nvidia_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    system_prompt: str | None,
    user_text: str,
) -> OcrResult | None:
    models = explicit_models or _dedupe([settings.nvidia_text_model, "google/gemma-3n-e2b-it", "mistralai/mistral-large-3-675b-instruct-2512"])
    for selected_model in models:
        try:
            client = NvidiaClient(settings, model=selected_model)
            if system_prompt is None and user_text == PROBLEM_OCR_USER_TEXT:
                text = await client.ocr_image(image_data_url, selected_model)
            else:
                text = await client.ocr_image(image_data_url, selected_model, system_prompt=system_prompt, user_text=user_text)
            return OcrResult(text=text, provider="nvidia", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("nvidia", selected_model, str(error)))
    return None


async def _try_ollama_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    system_prompt: str | None,
    user_text: str,
) -> OcrResult | None:
    models = explicit_models or _dedupe([settings.ollama_text_model])
    for selected_model in models:
        try:
            client = OllamaClient(settings, model=selected_model)
            text = await client.ocr_image(image_data_url, selected_model, system_prompt=system_prompt, user_text=user_text)
            return OcrResult(text=text, provider="ollama", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("ollama", selected_model, str(error)))
    return None


async def _try_openai_compat_ocr(
    image_data_url: str,
    settings: Settings,
    explicit_models: list[str] | None,
    attempts: list[OcrAttempt],
    system_prompt: str | None,
    user_text: str,
) -> OcrResult | None:
    models = explicit_models or _dedupe([settings.openai_compat_text_model])
    for selected_model in models:
        try:
            client = OpenAICompatClient(settings, model=selected_model)
            text = await client.ocr_image(image_data_url, selected_model, system_prompt=system_prompt, user_text=user_text)
            return OcrResult(text=text, provider="openai_compat", model=selected_model, warnings=_attempt_warnings(attempts))
        except RuntimeError as error:
            attempts.append(OcrAttempt("openai_compat", selected_model, str(error)))
    return None


def _ocr_provider_order(settings: Settings, selected_provider: str, include_router9_auto: bool, fallback_models: list[str] | None = None) -> list[str]:
    providers: list[str] = []
    if include_router9_auto and provider_configured(settings.router9_api_key):
        providers.append("router9")
    providers.append(selected_provider)
    for fallback in fallback_models or []:
        fallback_provider = _ocr_fallback_provider_from_model(fallback)
        if fallback_provider:
            providers.append(fallback_provider)
    if provider_configured(settings.openrouter_api_key):
        providers.append("openrouter")
    if provider_configured(settings.nvidia_api_key):
        providers.append("nvidia")
    if settings.ollama_text_model:
        providers.append("ollama")
    if provider_configured(settings.openai_compat_api_key) and settings.openai_compat_text_model and selected_provider != "openai_compat":
        providers.append("openai_compat")
    return _dedupe(providers)


def _attempt_warnings(attempts: list[OcrAttempt]) -> list[str]:
    return [f"OCR fallback: {attempt.warning()}" for attempt in attempts]


def _has_cross_provider_fallbacks(fallback_models: list[str] | None, selected_provider: str) -> bool:
    return any(
        bool(fallback_provider and fallback_provider != selected_provider)
        for fallback_provider in (_ocr_fallback_provider_from_model(fallback) for fallback in fallback_models or [])
    )


def _ocr_fallback_provider_from_model(model: str | None) -> str | None:
    if not model:
        return None
    for provider_id in ("local", "openrouter", "router9", "nvidia", "ollama", "openai_compat"):
        if model.startswith(f"{provider_id}/"):
            return provider_id
    if model.startswith("openai-compat/"):
        return "openai_compat"
    return explicit_provider_from_model(model)


def _ocr_models_for_provider(selected_provider: str, selected_model: str | None, fallback_models: list[str] | None) -> list[str]:
    models: list[str] = []
    if selected_model:
        models.append(selected_model)
    for fallback in fallback_models or []:
        fallback_provider = _ocr_fallback_provider_from_model(fallback)
        if fallback_provider and fallback_provider != selected_provider:
            continue
        normalized = normalize_model_for_provider(selected_provider, fallback)
        if normalized:
            models.append(normalized)
    return _dedupe(models)


def _router9_ocr_model_candidates(settings: Settings, explicit_model: str | None) -> list[str]:
    return router9_ocr_candidates(settings, explicit_model)


def _dedupe(models: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def _format_ocr_failure(message: str, attempts: list[OcrAttempt], router9_only: bool) -> str:
    details = " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"
    suggestions = "Hãy kiểm tra API key/quota, chọn model OCR khác hoặc quét lại model 9router."
    if router9_only:
        suggestions += " Nếu muốn dùng OpenRouter/NVIDIA fallback, hãy tắt 9router-only."
    return f"{message} Đã thử: {details}. {suggestions}"


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", redact_sensitive(message)).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")
