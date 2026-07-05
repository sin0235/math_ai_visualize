from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import html as html_lib
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.openrouter_client import openrouter_api_base_url

CAPABILITY_KEYS = (
    "capabilities",
    "supported_parameters",
    "architecture",
    "top_provider",
    "input_modalities",
    "output_modalities",
    "modalities",
    "per_request_limits",
)
OLLAMA_CAPABILITY_KEYS = ("details", "size", "digest", "modified_at")
THINKING_PARAMETERS = {"reasoning", "reasoning_effort", "thinking"}
NVIDIA_BUILD_BASE_URL = "https://build.nvidia.com"
NVIDIA_PREVIEW_MODELS_URL = f"{NVIDIA_BUILD_BASE_URL}/models?filters=nimType%3Anim_type_preview"


@dataclass(frozen=True)
class ModelListResult:
    models: list[AiModelInfo]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityResult:
    is_free_endpoint: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False
    supported_parameters: list[str] = field(default_factory=list)
    pricing: dict[str, Any] = field(default_factory=dict)
    endpoint_metadata: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    context_length: int | None = None
    warnings: list[str] = field(default_factory=list)


class ProviderAdapter:
    id = ""
    label = ""

    async def list_models(self, settings: Settings) -> ModelListResult:
        raise NotImplementedError

    async def ping(self, settings: Settings) -> None:
        return None

    def normalize_model_id(self, model_id: str) -> str:
        return model_id.strip()

    def is_free_endpoint_model(self, model_id: str, metadata: dict[str, Any], pricing: dict[str, Any]) -> tuple[bool, str | None]:
        if self.id == "openrouter" and model_id.endswith(":free"):
            return True, None
        if _explicit_free(metadata) or _pricing_is_free(pricing):
            return True, None
        if self.id == "nvidia":
            return False, f"NVIDIA model {model_id} chưa có metadata free endpoint rõ ràng."
        return False, None

    def detect_capabilities(self, model_id: str, metadata: dict[str, Any]) -> CapabilityResult:
        endpoint_metadata = _json_dict(metadata)
        pricing = _json_dict(metadata.get("pricing"))
        supported_parameters = _supported_parameters(metadata)
        is_free_endpoint, free_warning = self.is_free_endpoint_model(model_id, endpoint_metadata, pricing)
        capabilities = _extract_capabilities(metadata, CAPABILITY_KEYS)
        warnings = [free_warning] if free_warning else []
        return CapabilityResult(
            is_free_endpoint=is_free_endpoint,
            supports_thinking=_supports_thinking(metadata, supported_parameters),
            supports_vision=_supports_vision(metadata),
            supported_parameters=supported_parameters,
            pricing=pricing,
            endpoint_metadata=endpoint_metadata,
            capabilities=capabilities,
            context_length=_extract_context_length(metadata),
            warnings=warnings,
        )

    def build_chat_payload(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        request_thinking: bool = False,
        supports_thinking: bool | None = None,
        supported_parameters: list[str] | None = None,
        allow_unknown_thinking: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = {"model": self.normalize_model_id(model), "messages": messages, **kwargs}
        return self.apply_thinking_payload(
            payload,
            request_thinking=request_thinking,
            supports_thinking=supports_thinking,
            supported_parameters=supported_parameters,
            allow_unknown_thinking=allow_unknown_thinking,
        )

    def apply_thinking_payload(
        self,
        payload: dict[str, Any],
        *,
        request_thinking: bool,
        supports_thinking: bool | None = None,
        supported_parameters: list[str] | None = None,
        allow_unknown_thinking: bool = False,
    ) -> dict[str, Any]:
        if not should_send_thinking_payload(
            request_thinking=request_thinking,
            supports_thinking=supports_thinking,
            allow_unknown_thinking=allow_unknown_thinking,
        ):
            return payload
        self._add_thinking_payload(payload, supported_parameters or [])
        return payload

    def _add_thinking_payload(self, payload: dict[str, Any], supported_parameters: list[str]) -> None:
        return None


class OpenAIStyleAdapter(ProviderAdapter):
    api_key_required = False

    async def list_models(self, settings: Settings) -> ModelListResult:
        api_key, base_url = self._connection(settings)
        base = (base_url or "").strip()
        if not base:
            raise RuntimeError(f"{self.id} chưa có base URL hợp lệ.")
        if self.api_key_required and not (api_key or "").strip():
            raise RuntimeError("API key chưa được cấu hình cho provider này.")
        headers = self._headers(settings, api_key)
        models, warnings = await self._fetch_models(headers, _normalize_openai_base_url(base).rstrip("/"))
        return ModelListResult(models=models, warnings=warnings)

    def _connection(self, settings: Settings) -> tuple[str | None, str]:
        return getattr(settings, f"{self.id}_api_key", None), str(getattr(settings, f"{self.id}_base_url", "") or "")

    def _headers(self, settings: Settings, api_key: str | None) -> dict[str, str]:
        return _bearer_headers(api_key)

    async def _fetch_models(self, headers: dict[str, str], normalized_base: str) -> tuple[list[AiModelInfo], list[str]]:
        response = await _get_openai_models(self.id, headers, normalized_base)
        return self._parse_openai_style_models(response)

    def _parse_openai_style_models(self, response: httpx.Response) -> tuple[list[AiModelInfo], list[str]]:
        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError(f"{self.id} response không phải JSON hợp lệ.") from error

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise RuntimeError(f"{self.id} response không đúng định dạng data[].")

        models: list[AiModelInfo] = []
        warnings: list[str] = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            model_id = self.normalize_model_id(item["id"])
            detected = self.detect_capabilities(model_id, item)
            warnings.extend(detected.warnings)
            models.append(_model_info(self.id, model_id, item, detected))
        return sorted(models, key=lambda model: model.id.lower()), warnings


class OpenRouterAdapter(OpenAIStyleAdapter):
    id = "openrouter"
    label = "OpenRouter"
    api_key_required = True

    def normalize_model_id(self, model_id: str) -> str:
        return model_id.strip().removeprefix("openrouter/")

    def _add_thinking_payload(self, payload: dict[str, Any], supported_parameters: list[str]) -> None:
        payload["reasoning"] = {"enabled": True}

    def _connection(self, settings: Settings) -> tuple[str | None, str]:
        return settings.openrouter_api_key, openrouter_api_base_url(settings)

    def _headers(self, settings: Settings, api_key: str | None) -> dict[str, str]:
        headers = _bearer_headers(api_key)
        if settings.openrouter_http_referer:
            headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_x_title:
            headers["X-Title"] = settings.openrouter_x_title
        return headers


class NvidiaAdapter(OpenAIStyleAdapter):
    id = "nvidia"
    label = "NVIDIA"
    api_key_required = True

    def is_free_endpoint_model(self, model_id: str, metadata: dict[str, Any], pricing: dict[str, Any]) -> tuple[bool, str | None]:
        if _nvidia_is_preview_endpoint(metadata) or _explicit_free(metadata) or _pricing_is_free(pricing):
            return True, None
        return False, None

    async def _fetch_models(self, headers: dict[str, str], normalized_base: str) -> tuple[list[AiModelInfo], list[str]]:
        response = await _get_openai_models(self.id, headers, normalized_base)
        parsed, warnings = super()._parse_openai_style_models(response)
        preview_slugs, preview_warning = await _fetch_nvidia_preview_model_slugs()
        if preview_warning:
            warnings.append(preview_warning)
        models = _filter_nvidia_free_endpoint_models(parsed, preview_slugs)
        skipped = len(parsed) - len(models)
        if skipped > 0:
            source = NVIDIA_PREVIEW_MODELS_URL if preview_slugs else "metadata Free Endpoint/nim_type_preview"
            warnings.append(f"Đã bỏ {skipped} NVIDIA model không thuộc Free Endpoint. Nguồn lọc: {source}")
        return models, warnings

    def _add_thinking_payload(self, payload: dict[str, Any], supported_parameters: list[str]) -> None:
        chat_template_kwargs = dict(payload.get("chat_template_kwargs") or {})
        if "reasoning_effort" in supported_parameters:
            chat_template_kwargs["reasoning_effort"] = "medium"
        else:
            chat_template_kwargs["thinking"] = True
        payload["chat_template_kwargs"] = chat_template_kwargs

    def _connection(self, settings: Settings) -> tuple[str | None, str]:
        return settings.nvidia_api_key, settings.nvidia_base_url


class OpenAICompatAdapter(OpenAIStyleAdapter):
    id = "openai_compat"
    label = "OpenAI-compatible"

    def _connection(self, settings: Settings) -> tuple[str | None, str]:
        return settings.openai_compat_api_key, settings.openai_compat_base_url

    async def _fetch_models(self, headers: dict[str, str], normalized_base: str) -> tuple[list[AiModelInfo], list[str]]:
        last_error: RuntimeError | None = None
        for base in _dedupe_bases([normalized_base, _alternate_openai_compat_base(normalized_base)]):
            try:
                response = await _get_openai_models(self.id, headers, base)
                return self._parse_openai_style_models(response)
            except RuntimeError as error:
                last_error = error
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"{self.id} chưa có base URL hợp lệ.")


class OllamaAdapter(ProviderAdapter):
    id = "ollama"
    label = "Ollama"

    async def list_models(self, settings: Settings) -> ModelListResult:
        api_key = settings.ollama_api_key
        base = settings.ollama_base_url.strip().rstrip("/")
        if not base:
            raise RuntimeError("ollama chưa có base URL hợp lệ.")
        if _uses_openai_style_ollama(base):
            models, warnings = await OpenAIStyleOllamaAdapter()._fetch_models(_bearer_headers(api_key), _normalize_openai_base_url(base).rstrip("/"))
            return ModelListResult(models=models, warnings=warnings)
        response = await _get_ollama_tags(api_key, base)
        return self._parse_ollama_tags(response)

    def detect_capabilities(self, model_id: str, metadata: dict[str, Any]) -> CapabilityResult:
        detected = super().detect_capabilities(model_id, metadata)
        return CapabilityResult(**{**detected.__dict__, "capabilities": _extract_capabilities(metadata, OLLAMA_CAPABILITY_KEYS)})

    def _parse_ollama_tags(self, response: httpx.Response) -> ModelListResult:
        try:
            body = response.json()
        except ValueError as error:
            raise RuntimeError("ollama response không phải JSON hợp lệ.") from error
        raw = body.get("models") if isinstance(body, dict) else None
        if not isinstance(raw, list):
            raise RuntimeError("ollama response không đúng định dạng models[].")
        models: list[AiModelInfo] = []
        warnings: list[str] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            model_id = self.normalize_model_id(name)
            detected = self.detect_capabilities(model_id, item)
            warnings.extend(detected.warnings)
            models.append(_model_info(self.id, model_id, item, detected, label=model_id, owned_by=_ollama_owned_by(item)))
        return ModelListResult(models=sorted(models, key=lambda model: model.id.lower()), warnings=warnings)


class OpenAIStyleOllamaAdapter(OpenAIStyleAdapter):
    id = "ollama"
    label = "Ollama"


class Router9Adapter(OpenAIStyleAdapter):
    id = "router9"
    label = "9router"
    api_key_required = True

    def _connection(self, settings: Settings) -> tuple[str | None, str]:
        return settings.router9_api_key, settings.router9_base_url

    async def _fetch_models(self, headers: dict[str, str], normalized_base: str) -> tuple[list[AiModelInfo], list[str]]:
        url = f"{normalized_base}/models"
        models: list[AiModelInfo] = []
        warnings: list[str] = []
        params: dict[str, str] = {}
        seen_cursors: set[str] = set()
        while True:
            response = await _get_openai_models(self.id, headers, normalized_base, params=params or None, url=url)
            parsed, page_warnings = self._parse_openai_style_models(response)
            models.extend(parsed)
            warnings.extend(page_warnings)
            try:
                body = response.json()
            except ValueError as error:
                raise RuntimeError("9router response không phải JSON hợp lệ.") from error
            next_cursor = _next_models_cursor(body)
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            params = {"cursor": next_cursor}
        by_id = {model.id: model for model in models}
        return sorted(by_id.values(), key=lambda model: model.id.lower()), warnings


ADAPTERS: dict[str, ProviderAdapter] = {
    "openrouter": OpenRouterAdapter(),
    "nvidia": NvidiaAdapter(),
    "openai_compat": OpenAICompatAdapter(),
    "ollama": OllamaAdapter(),
    "router9": Router9Adapter(),
}


def get_provider_adapter(provider: str) -> ProviderAdapter:
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        raise RuntimeError(f"Provider không hỗ trợ scan: {provider}")
    return adapter


def should_send_thinking_payload(*, request_thinking: bool, supports_thinking: bool | None, allow_unknown_thinking: bool = False) -> bool:
    if not request_thinking:
        return False
    if supports_thinking is False:
        return False
    if supports_thinking is True:
        return True
    return allow_unknown_thinking


async def _get_openai_models(provider: str, headers: dict[str, str], normalized_base: str, params: dict[str, str] | None = None, url: str | None = None) -> httpx.Response:
    from app.services.http_pool import TIMEOUT_MODELS, get_client

    request_url = url or f"{normalized_base}/models"
    try:
        client = get_client(normalized_base, TIMEOUT_MODELS)
        if params is None:
            response = await client.get(request_url, headers=headers, timeout=TIMEOUT_MODELS)
        else:
            response = await client.get(request_url, headers=headers, params=params, timeout=TIMEOUT_MODELS)
        if response.status_code >= 400:
            raise RuntimeError(_format_scan_error(provider, response))
        return response
    except httpx.TimeoutException as error:
        raise RuntimeError(f"{provider} models request quá chậm; gateway không trả trong 300 giây.") from error
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"{provider} models request lỗi: {message}") from error


async def _get_ollama_tags(api_key: str | None, normalized_base: str) -> httpx.Response:
    from app.services.http_pool import TIMEOUT_MODELS, get_client

    try:
        client = get_client(normalized_base, TIMEOUT_MODELS)
        response = await client.get(f"{normalized_base}/api/tags", headers=_bearer_headers(api_key), timeout=TIMEOUT_MODELS)
        if response.status_code >= 400:
            raise RuntimeError(_format_scan_error("ollama", response))
        return response
    except httpx.TimeoutException as error:
        raise RuntimeError("ollama models request quá chậm; gateway không trả trong 300 giây.") from error
    except httpx.HTTPError as error:
        message = str(error) or error.__class__.__name__
        raise RuntimeError(f"ollama models request lỗi: {message}") from error


async def _fetch_nvidia_preview_model_slugs() -> tuple[set[str], str | None]:
    from app.services.http_pool import TIMEOUT_MODELS, get_client

    client = get_client(NVIDIA_BUILD_BASE_URL, TIMEOUT_MODELS)
    urls = [f"{NVIDIA_PREVIEW_MODELS_URL}&page={page}" for page in range(1, 5)]
    responses = await asyncio.gather(*(client.get(url, timeout=TIMEOUT_MODELS) for url in urls), return_exceptions=True)
    slugs: set[str] = set()
    failures = 0
    for response in responses:
        if isinstance(response, Exception):
            failures += 1
            continue
        if response.status_code >= 400:
            failures += 1
            continue
        slugs.update(_parse_nvidia_preview_slugs(response.text))
    warning = None
    if failures and not slugs:
        warning = "Không đọc được NVIDIA Free Endpoint catalog; chỉ dùng metadata trong /v1/models để lọc."
    return slugs, warning


def _parse_nvidia_preview_slugs(html: str) -> set[str]:
    slugs: set[str] = set()
    for href in re.findall(r'href="/([^"/?#]+/[^"/?#]+)"', html):
        if href.startswith("explore/"):
            continue
        slugs.add(html_lib.unescape(href.rsplit("/", 1)[-1]).strip().lower())
    return slugs


def _filter_nvidia_free_endpoint_models(models: list[AiModelInfo], preview_slugs: set[str]) -> list[AiModelInfo]:
    filtered: list[AiModelInfo] = []
    for model in models:
        matches_catalog = bool(preview_slugs) and _nvidia_model_matches_preview_catalog(model.id, preview_slugs)
        if not model.is_free_endpoint and not matches_catalog:
            continue
        metadata = dict(model.endpoint_metadata)
        if matches_catalog:
            metadata["nvidia_free_endpoint_source"] = NVIDIA_PREVIEW_MODELS_URL
        filtered.append(model.model_copy(update={"is_free_endpoint": True, "endpoint_metadata": metadata}))
    return sorted(filtered, key=lambda item: item.id.lower())


def _nvidia_model_matches_preview_catalog(model_id: str, preview_slugs: set[str]) -> bool:
    normalized = model_id.strip().lower()
    tail = normalized.rsplit("/", 1)[-1]
    return tail in preview_slugs or normalized in preview_slugs


def _model_info(provider: str, model_id: str, item: dict[str, Any], detected: CapabilityResult, label: str | None = None, owned_by: str | None = None) -> AiModelInfo:
    return AiModelInfo(
        id=model_id,
        label=label or model_id,
        provider=provider,
        owned_by=owned_by if owned_by is not None else _optional_str(item.get("owned_by")),
        created=_optional_int(item.get("created")),
        context_length=detected.context_length,
        capabilities=detected.capabilities,
        is_free_endpoint=detected.is_free_endpoint,
        supports_thinking=detected.supports_thinking,
        supports_vision=detected.supports_vision,
        supported_parameters=detected.supported_parameters,
        pricing=detected.pricing,
        endpoint_metadata=detected.endpoint_metadata,
    )


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


def _bearer_headers(api_key: str | None) -> dict[str, str]:
    key = (api_key or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _uses_openai_style_ollama(base_url: str) -> bool:
    base = base_url.strip().rstrip("/").lower()
    return base.endswith("/v1") or "ollama.com" in base


def _extract_capabilities(item: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value for key in keys if (value := item.get(key)) is not None and _is_json_compatible(value)}


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) and _is_json_compatible(value) else {}


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_compatible(item) for key, item in value.items())
    return False


def _supported_parameters(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("supported_parameters")
    if isinstance(raw, list):
        return sorted({item for item in raw if isinstance(item, str) and item})
    if isinstance(raw, dict):
        return sorted({key for key, value in raw.items() if isinstance(key, str) and value})
    return []


def _supports_thinking(metadata: dict[str, Any], supported_parameters: list[str]) -> bool:
    if THINKING_PARAMETERS & set(supported_parameters):
        return True
    return _truthy_capability(metadata, ("reasoning", "thinking", "supports_reasoning", "supports_thinking"))


def _supports_vision(metadata: dict[str, Any]) -> bool:
    if _truthy_capability(metadata, ("vision", "supports_vision", "image_input", "multimodal")):
        return True
    for value in _walk_values(metadata):
        if isinstance(value, str) and value.lower() in {"image", "vision", "image_url"}:
            return True
    return False


def _truthy_capability(value: Any, keys: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower()
            if normalized in keys and item is True:
                return True
            if normalized in {"capabilities", "architecture", "top_provider"} and _truthy_capability(item, keys):
                return True
            if isinstance(item, dict | list) and _truthy_capability(item, keys):
                return True
    if isinstance(value, list):
        return any(_truthy_capability(item, keys) for item in value)
    return False


def _walk_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


def _explicit_free(metadata: dict[str, Any]) -> bool:
    return _truthy_capability(metadata, ("free", "is_free", "free_endpoint", "is_free_endpoint"))


def _nvidia_is_preview_endpoint(metadata: dict[str, Any]) -> bool:
    for value in _walk_values(metadata):
        if isinstance(value, str) and value.strip().lower() == "nim_type_preview":
            return True
    return False


def _pricing_is_free(pricing: dict[str, Any]) -> bool:
    values = [value for value in _walk_values(pricing) if isinstance(value, str | int | float)]
    return bool(values) and all(_price_is_zero(value) for value in values)


def _price_is_zero(value: str | int | float) -> bool:
    if isinstance(value, int | float):
        return float(value) == 0
    text = value.strip().lower().replace("$", "")
    if text in {"free", "0", "0.0", "0.00", "0.0000"}:
        return True
    try:
        return float(text) == 0
    except ValueError:
        return False


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _extract_context_length(item: dict[str, Any]) -> int | None:
    for key in ("context_length", "context_window", "max_context_length"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    top_provider = item.get("top_provider")
    if isinstance(top_provider, dict):
        value = top_provider.get("context_length") or top_provider.get("max_context_length")
        if isinstance(value, int):
            return value
    return None


def _ollama_owned_by(item: dict[str, Any]) -> str | None:
    details = item.get("details")
    if isinstance(details, dict) and isinstance(details.get("family"), str):
        return details["family"]
    return None


def _next_models_cursor(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("next_cursor", "next", "cursor"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    meta = body.get("meta")
    if isinstance(meta, dict):
        for key in ("next_cursor", "next", "cursor"):
            value = meta.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _format_scan_error(provider: str, response: httpx.Response) -> str:
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:500]
    return f"{provider} models request lỗi HTTP {response.status_code}: {detail}"