from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo, ModelScanProvider
from app.services.openrouter_client import openrouter_api_base_url


async def list_provider_models(settings: Settings, provider: ModelScanProvider) -> list[AiModelInfo]:
    api_key, base_url = _provider_connection(settings, provider)
    base = (base_url or "").strip()
    if not base:
        raise RuntimeError(f"{provider} chưa có base URL hợp lệ.")

    if provider == "ollama":
        if _uses_openai_style_ollama(base):
            headers = _bearer_headers(api_key)
            return await _fetch_openai_style_models("ollama", headers, _normalize_openai_base_url(base).rstrip("/"))
        return await _fetch_ollama_models(settings, api_key, base)

    _require_api_key_if_needed(provider, api_key)
    headers = _bearer_headers(api_key)
    if provider == "openrouter":
        headers = {**headers, **_openrouter_optional_headers(settings)}

    normalized_base = openrouter_api_base_url(settings) if provider == "openrouter" else _normalize_openai_base_url(base).rstrip("/")
    alternate_base = _alternate_openai_compat_base(normalized_base) if provider == "openai_compat" else None
    return await _fetch_openai_style_models(provider, headers, normalized_base, alternate_base)


def _provider_connection(settings: Settings, provider: ModelScanProvider) -> tuple[str | None, str]:
    if provider == "openrouter":
        return settings.openrouter_api_key, settings.openrouter_base_url
    if provider == "openai_compat":
        return settings.openai_compat_api_key, settings.openai_compat_base_url
    if provider == "nvidia":
        return settings.nvidia_api_key, settings.nvidia_base_url
    if provider == "ollama":
        return settings.ollama_api_key, settings.ollama_base_url
    raise AssertionError(f"unknown scan provider: {provider}")


async def _fetch_openai_style_models(provider: str, headers: dict[str, str], normalized_base: str, alternate_base: str | None = None) -> list[AiModelInfo]:
    last_error: RuntimeError | None = None
    for base in _dedupe_bases([normalized_base, alternate_base]):
        try:
            response = await _get_openai_models(provider, headers, base)
            return _parse_openai_style_models(provider, response)
        except RuntimeError as error:
            last_error = error
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{provider} chưa có base URL hợp lệ.")


async def _get_openai_models(provider: str, headers: dict[str, str], normalized_base: str) -> httpx.Response:
    from app.services.http_pool import TIMEOUT_MODELS, get_client

    url = f"{normalized_base}/models"
    try:
        client = get_client(normalized_base, TIMEOUT_MODELS)
        response = await client.get(url, headers=headers, timeout=TIMEOUT_MODELS)
        if response.status_code >= 400:
            raise RuntimeError(_format_scan_error(provider, response))
        return response
    except httpx.TimeoutException as error:
        raise RuntimeError(f"{provider} models request quá chậm; gateway không trả trong 20 giây.") from error
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"{provider} models request lỗi: {message}") from error


def _normalize_openai_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base.removesuffix("/chat/completions")
    if base.endswith("/completions"):
        return base.removesuffix("/completions")
    return base


def _alternate_openai_compat_base(normalized_base: str) -> str | None:
    if normalized_base.endswith("/v1"):
        return normalized_base.removesuffix("/v1")
    return f"{normalized_base}/v1"


def _dedupe_bases(bases: list[str | None]) -> list[str]:
    result: list[str] = []
    for base in bases:
        normalized = (base or "").rstrip("/")
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _uses_openai_style_ollama(base_url: str) -> bool:
    base = base_url.strip().rstrip("/").lower()
    return base.endswith("/v1") or "ollama.com" in base


def _require_api_key_if_needed(provider: ModelScanProvider, api_key: str | None) -> None:
    if provider in ("openrouter", "nvidia") and not (api_key or "").strip():
        raise RuntimeError("API key chưa được cấu hình cho provider này.")


def _bearer_headers(api_key: str | None) -> dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _openrouter_optional_headers(settings: Settings) -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_x_title:
        headers["X-Title"] = settings.openrouter_x_title
    return headers


async def _fetch_ollama_models(settings: Settings, api_key: str | None, base_url: str) -> list[AiModelInfo]:
    headers = _bearer_headers(api_key)
    from app.services.http_pool import TIMEOUT_MODELS, get_client

    normalized_base = base_url.rstrip("/")
    url = f"{normalized_base}/api/tags"
    try:
        client = get_client(normalized_base, TIMEOUT_MODELS)
        response = await client.get(url, headers=headers, timeout=TIMEOUT_MODELS)
        if response.status_code >= 400:
            raise RuntimeError(_format_scan_error("ollama", response))
    except httpx.TimeoutException as error:
        raise RuntimeError("ollama models request quá chậm; gateway không trả trong 20 giây.") from error
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"ollama models request lỗi: {message}") from error

    return _parse_ollama_tags(response)


def _parse_openai_style_models(provider: str, response: httpx.Response) -> list[AiModelInfo]:
    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError(f"{provider} response không phải JSON hợp lệ.") from error

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        raise RuntimeError(f"{provider} response không đúng định dạng data[].")

    models: list[AiModelInfo] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        models.append(
            AiModelInfo(
                id=model_id,
                label=model_id,
                provider=provider,
                owned_by=_optional_str(item.get("owned_by")),
                created=_optional_int(item.get("created")),
                context_length=_extract_context_length(item),
            )
        )
    return sorted(models, key=lambda model: model.id.lower())


def _parse_ollama_tags(response: httpx.Response) -> list[AiModelInfo]:
    try:
        body = response.json()
    except ValueError as error:
        raise RuntimeError("ollama response không phải JSON hợp lệ.") from error

    raw = body.get("models") if isinstance(body, dict) else None
    if not isinstance(raw, list):
        raise RuntimeError("ollama response không đúng định dạng models[].")

    models: list[AiModelInfo] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        details = item.get("details")
        owned_by = None
        if isinstance(details, dict):
            fam = details.get("family")
            if isinstance(fam, str):
                owned_by = fam
        modified = item.get("modified_at")
        created = _optional_int(modified) if isinstance(modified, int) else None
        models.append(
            AiModelInfo(
                id=name,
                label=name,
                provider="ollama",
                owned_by=owned_by,
                created=created,
                context_length=_extract_context_length(item),
            )
        )
    return sorted(models, key=lambda model: model.id.lower())


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _extract_context_length(item: dict[str, Any]) -> int | None:
    for key in ("context_length", "context_window", "max_context_length"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    details = item.get("details")
    if isinstance(details, dict):
        for key in ("context_length", "context_window", "max_context_length"):
            value = details.get(key)
            if isinstance(value, int):
                return value
    return None


def _format_scan_error(provider: str, response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:500]
    return f"{provider} HTTP {response.status_code}: {body}"
