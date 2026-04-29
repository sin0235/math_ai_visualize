from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo, ModelScanProvider


async def list_provider_models(settings: Settings, provider: ModelScanProvider) -> list[AiModelInfo]:
    if provider == "openrouter":
        api_key = settings.openrouter_api_key
        base_url = settings.openrouter_base_url
        headers = _headers(api_key)
    elif provider == "nvidia":
        api_key = settings.nvidia_api_key
        base_url = settings.nvidia_base_url
        headers = _headers(api_key)
    else:
        api_key = settings.ollama_api_key
        base_url = settings.ollama_base_url
        headers = _headers(api_key) if api_key else {}

    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(_format_scan_error(provider, response))
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"{provider} models request lỗi: {message}") from error

    return _parse_models(provider, response)


def _headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        raise RuntimeError("API key chưa được cấu hình cho provider này.")
    return {"Authorization": f"Bearer {api_key}"}


def _parse_models(provider: str, response: httpx.Response) -> list[AiModelInfo]:
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


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _extract_context_length(item: dict[str, Any]) -> int | None:
    for key in ("context_length", "context_window", "max_context_length"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    return None


def _format_scan_error(provider: str, response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:500]
    return f"{provider} HTTP {response.status_code}: {body}"
