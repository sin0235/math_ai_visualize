import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("app.services.ai_providers")

_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret",
    "token",
    "key",
}
_DATA_IMAGE_RE = re.compile(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=\s]+")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_KEY_VALUE_RE = re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|token)=([^\s&]+)")


def log_provider_request(provider: str, kind: str, url: str, model: Any, **metadata: Any) -> None:
    logger.info(
        "AI provider request",
        extra={"provider": provider, "kind": kind, "url": url, "model": model, **metadata},
    )


def log_provider_response(provider: str, kind: str, status_code: int, elapsed_ms: int, response_chars: int) -> None:
    logger.info(
        "AI provider response",
        extra={
            "provider": provider,
            "kind": kind,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "response_chars": response_chars,
        },
    )


def log_scene_summary(provider: str, scene_json: dict[str, Any]) -> None:
    logger.info(
        "AI scene parsed",
        extra={
            "provider": provider,
            "renderer": scene_json.get("renderer"),
            "topic": scene_json.get("topic"),
            "objects_count": len(scene_json.get("objects", [])) if isinstance(scene_json.get("objects"), list) else None,
        },
    )


def log_ocr_summary(provider: str, text: str) -> None:
    logger.info("AI OCR parsed", extra={"provider": provider, "result_chars": len(text)})


def format_provider_error(provider: str, response: httpx.Response, limit: int = 500) -> str:
    message = _extract_error_message(response)
    sanitized = truncate_text(redact_sensitive(message), limit)
    return f"{provider} HTTP {response.status_code}: {sanitized}" if sanitized else f"{provider} HTTP {response.status_code}"


def redact_sensitive(value: Any) -> str:
    text = _stringify(_redact_value(value))
    text = _DATA_IMAGE_RE.sub("data:image/[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text


def truncate_text(value: str, limit: int = 500) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _extract_error_message(response: httpx.Response) -> Any:
    try:
        body: Any = response.json()
    except ValueError:
        return response.text
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            for key in ("message", "code", "type"):
                if isinstance(error.get(key), str):
                    return {key: error[key]}
        if isinstance(error, str):
            return {"error": error}
        for key in ("message", "detail"):
            if isinstance(body.get(key), str):
                return {key: body[key]}
    return body


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _DATA_IMAGE_RE.sub("data:image/[REDACTED]", value)
    return value


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)
