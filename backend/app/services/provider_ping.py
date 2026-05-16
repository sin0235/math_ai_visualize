from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.services.chat_response import extract_chat_message_content
from app.services.openrouter_client import openrouter_api_base_url
from app.services.provider_logging import format_provider_error, redact_sensitive

ADMIN_PING_PROVIDERS = ("openrouter", "nvidia", "ollama", "openai_compat", "router9")

_PROVIDER_ALIASES = {
    "ollama_gpt_oss": "ollama",
    "9router": "router9",
}

_PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "nvidia": "NVIDIA",
    "ollama": "Ollama",
    "openai_compat": "OpenAI-compatible",
    "router9": "9router",
}


@dataclass(frozen=True)
class ProviderPingResult:
    provider: str
    status: str
    message: str
    model: str | None = None
    latency_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def ping_provider(provider: str, settings: Settings) -> ProviderPingResult:
    normalized = normalize_ping_provider(provider)
    started_at = time.perf_counter()
    try:
        model = await check_provider_connection(normalized, settings)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        message = f"Kết nối tới {_PROVIDER_LABELS[normalized]} thành công."
        if model:
            message = f"{message} Model: {model}."
        return ProviderPingResult(normalized, "ok", message, model=model, latency_ms=elapsed_ms)
    except Exception as error:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        message = redact_sensitive(str(error) or error.__class__.__name__)
        return ProviderPingResult(normalized, "error", message, latency_ms=elapsed_ms)


async def check_provider_connection(provider: str, settings: Settings) -> str:
    normalized = normalize_ping_provider(provider)
    if normalized == "openrouter":
        model = _require_text(settings.openrouter_text_model, "Chưa chọn model OpenRouter.")
        api_key = _require_text(settings.openrouter_api_key, "OPENROUTER_API_KEY chưa được cấu hình.")
        await _ping_openai_compatible_chat(
            provider="openrouter",
            label="OpenRouter",
            base_url=openrouter_api_base_url(settings),
            model=model.removeprefix("openrouter/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                **({"HTTP-Referer": settings.openrouter_http_referer} if settings.openrouter_http_referer else {}),
                **({"X-Title": settings.openrouter_x_title} if settings.openrouter_x_title else {}),
            },
        )
        return model

    if normalized == "nvidia":
        model = _require_text(settings.nvidia_text_model, "Chưa chọn model NVIDIA.")
        api_key = _require_text(settings.nvidia_api_key, "NVIDIA_API_KEY chưa được cấu hình.")
        base_url = settings.nvidia_base_url.rstrip("/")
        await _ping_openai_compatible_chat(
            provider="nvidia",
            label="NVIDIA",
            base_url=base_url,
            model=model,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        return model

    if normalized == "openai_compat":
        model = _require_text(settings.openai_compat_text_model, "Chưa chọn model OpenAI-compatible.")
        base_url = settings.openai_compat_base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        api_key = (settings.openai_compat_api_key or "").strip()
        if not api_key and _is_remote_host(base_url):
            raise RuntimeError(
                f"OpenAI-compatible endpoint ({base_url}) cần API key nhưng chưa cấu hình OPENAI_COMPAT_API_KEY."
            )
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        await _ping_openai_compatible_chat(
            provider="openai_compat",
            label="OpenAI-compatible",
            base_url=base_url,
            model=model,
            headers=headers,
        )
        return model

    if normalized == "router9":
        model = _require_text(settings.router9_text_model, "Chưa chọn model 9router.")
        api_key = _require_text(settings.router9_api_key, "ROUTER9_API_KEY chưa được cấu hình.")
        base_url = settings.router9_base_url.rstrip("/")
        await _ping_openai_compatible_chat(
            provider="router9",
            label="9router",
            base_url=base_url,
            model=model,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        return model

    if normalized == "ollama":
        model = _require_text(settings.ollama_text_model, "Chưa chọn model Ollama.")
        await _ping_ollama(settings, model)
        return model

    raise RuntimeError(f"Provider không hỗ trợ ping: {provider}")


def normalize_ping_provider(provider: str) -> str:
    normalized = _PROVIDER_ALIASES.get(provider.strip(), provider.strip())
    if normalized not in ADMIN_PING_PROVIDERS:
        raise RuntimeError(f"Provider không hỗ trợ ping: {provider}")
    return normalized


async def _ping_openai_compatible_chat(
    *,
    provider: str,
    label: str,
    base_url: str,
    model: str,
    headers: dict[str, str],
) -> None:
    from app.services.http_pool import TIMEOUT_FAST, get_client

    payload = _chat_ping_payload(model)
    url = f"{base_url.rstrip('/')}/chat/completions"
    try:
        client = get_client(base_url, TIMEOUT_FAST)
        response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_FAST)
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"{label} ping lỗi: {message}") from error
    if response.status_code >= 400:
        raise RuntimeError(format_provider_error(label, response))
    _extract_openai_chat_content(response, label)


async def _ping_ollama(settings: Settings, model: str) -> None:
    base_url = settings.ollama_base_url.rstrip("/")
    if _uses_openai_compatible_api(base_url):
        api_key = _require_text(settings.ollama_api_key, "OLLAMA_API_KEY chưa được cấu hình cho Ollama cloud.")
        await _ping_openai_compatible_chat(
            provider="ollama",
            label="Ollama cloud",
            base_url=base_url,
            model=model,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        return

    from app.services.http_pool import TIMEOUT_FAST, get_client

    headers = {"Content-Type": "application/json"}
    if settings.ollama_api_key and settings.ollama_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.ollama_api_key.strip()}"
    payload = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "options": {"temperature": 0, "num_predict": 16},
    }
    url = f"{base_url}/api/chat"
    try:
        client = get_client(base_url, TIMEOUT_FAST)
        response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_FAST)
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"Ollama ping lỗi: {message}") from error
    if response.status_code >= 400:
        raise RuntimeError(f"Ollama ping lỗi HTTP {response.status_code}: {redact_sensitive(response.text[:500])}")
    try:
        content = extract_chat_message_content(response.json()["message"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Ollama ping response không đúng định dạng message.content.") from error
    if not content.strip():
        raise RuntimeError("Ollama ping không trả về nội dung.")


def _chat_ping_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }


def _extract_openai_chat_content(response: httpx.Response, label: str) -> str:
    try:
        content = extract_chat_message_content(response.json()["choices"][0]["message"])
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label} ping response không đúng định dạng choices[0].message.content.") from error
    if not content.strip():
        raise RuntimeError(f"{label} ping không trả về nội dung.")
    return content


def _require_text(value: str | None, message: str) -> str:
    text = (value or "").strip()
    if not text:
        raise RuntimeError(message)
    return text


def _uses_openai_compatible_api(base_url: str) -> bool:
    return base_url.endswith("/v1") or "ollama.com" in base_url


def _is_remote_host(base_url: str) -> bool:
    """Return True when the base_url points to a non-local host."""
    import re
    host = re.sub(r"^https?://", "", base_url).split("/")[0].split(":")[0].lower()
    return host not in {"localhost", "127.0.0.1", "0.0.0.0", ""}
