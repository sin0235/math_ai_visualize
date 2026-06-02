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


def chat_message_input_chars(messages: Any) -> int:
    """Return an approximate character count for text sent in chat messages.

    Counts plain string content plus text/image_url strings inside multimodal
    content arrays. This is intended for safe observability only; callers should
    continue logging domain-specific counts such as ``problem_chars`` when useful.
    """
    if not isinstance(messages, list):
        return 0
    return sum(_message_content_chars(message.get("content")) for message in messages if isinstance(message, dict))


def _message_content_chars(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    total += len(item["text"])
                image_url = item.get("image_url")
                if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                    total += len(image_url["url"])
                elif isinstance(image_url, str):
                    total += len(image_url)
            elif isinstance(item, str):
                total += len(item)
        return total
    return 0


def log_provider_request(provider: str, kind: str, url: str, model: Any, **metadata: Any) -> None:
    meta_text = _metadata_text(metadata)
    logger.info(
        "AI provider request provider=%s kind=%s model=%s url=%s%s",
        provider,
        kind,
        model or "<none>",
        url,
        meta_text,
        extra={"provider": provider, "kind": kind, "url": url, "model": model, **metadata},
    )


def log_provider_response(provider: str, kind: str, status_code: int, elapsed_ms: int, response_chars: int, model: Any = None) -> None:
    logger.info(
        "AI provider response provider=%s kind=%s model=%s status=%s elapsed_ms=%s response_chars=%s",
        provider,
        kind,
        model or "<unknown>",
        status_code,
        elapsed_ms,
        response_chars,
        extra={
            "provider": provider,
            "kind": kind,
            "model": model,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "response_chars": response_chars,
        },
    )


def log_provider_http_error(provider: str, kind: str, response: httpx.Response, model: Any = None, limit: int = 1200) -> None:
    logger.warning(
        "AI provider error provider=%s kind=%s model=%s status=%s body=%s",
        provider,
        kind,
        model or "<unknown>",
        response.status_code,
        format_provider_error(provider, response, limit),
        extra={
            "provider": provider,
            "kind": kind,
            "model": model,
            "status_code": response.status_code,
        },
    )


def log_scene_summary(provider: str, scene_json: dict[str, Any], model: Any = None) -> None:
    logger.info(
        "AI provider parse provider=%s kind=scene model=%s renderer=%s topic=%s objects=%s",
        provider,
        model or "<unknown>",
        scene_json.get("renderer"),
        scene_json.get("topic"),
        len(scene_json.get("objects", [])) if isinstance(scene_json.get("objects"), list) else None,
        extra={
            "provider": provider,
            "kind": "scene",
            "model": model,
            "renderer": scene_json.get("renderer"),
            "topic": scene_json.get("topic"),
            "objects_count": len(scene_json.get("objects", [])) if isinstance(scene_json.get("objects"), list) else None,
        },
    )


def log_ocr_summary(provider: str, text: str, model: Any = None) -> None:
    logger.info(
        "AI provider parse provider=%s kind=ocr model=%s result_chars=%s",
        provider,
        model or "<unknown>",
        len(text),
        extra={"provider": provider, "kind": "ocr", "model": model, "result_chars": len(text)},
    )


def log_provider_parse_error(provider: str, kind: str, model: Any, message: Any, response_chars: int | None = None, limit: int = 500) -> None:
    sanitized = truncate_text(redact_sensitive(message), limit)
    logger.warning(
        "AI provider parse error provider=%s kind=%s model=%s response_chars=%s error=%s",
        provider,
        kind,
        model or "<unknown>",
        response_chars if response_chars is not None else "<unknown>",
        sanitized,
        extra={
            "provider": provider,
            "kind": kind,
            "model": model,
            "response_chars": response_chars,
            "error": sanitized,
        },
    )


def log_provider_parse(provider: str, kind: str, model: Any, result_chars: int) -> None:
    logger.info(
        "AI provider parse provider=%s kind=%s model=%s result_chars=%s",
        provider,
        kind,
        model or "<unknown>",
        result_chars,
        extra={"provider": provider, "kind": kind, "model": model, "result_chars": result_chars},
    )


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


def _metadata_text(metadata: dict[str, Any]) -> str:
    if not metadata:
        return ""
    safe_items = []
    for key, value in metadata.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            continue
        safe_items.append(f"{key}={truncate_text(redact_sensitive(value), 120)}")
    return " " + " ".join(safe_items) if safe_items else ""
