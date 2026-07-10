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


def extract_token_usage(payload: Any) -> dict[str, int] | None:
    """Best-effort token usage from OpenAI-compatible provider payloads."""
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    result: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            result[key] = int(value)
    return result or None


def log_provider_response(
    provider: str,
    kind: str,
    status_code: int,
    elapsed_ms: int,
    response_chars: int,
    model: Any = None,
    *,
    usage: dict[str, int] | None = None,
    user_id: str | None = None,
    persist_metrics: bool = True,
) -> None:
    logger.info(
        "AI provider response provider=%s kind=%s model=%s status=%s elapsed_ms=%s response_chars=%s%s",
        provider,
        kind,
        model or "<unknown>",
        status_code,
        elapsed_ms,
        response_chars,
        f" tokens={usage.get('total_tokens')}" if usage and usage.get("total_tokens") is not None else "",
        extra={
            "provider": provider,
            "kind": kind,
            "model": model,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "response_chars": response_chars,
        },
    )
    if persist_metrics and status_code < 400:
        schedule_ai_call_metric(
            task=kind,
            provider=provider,
            model=str(model) if model is not None else None,
            user_id=user_id,
            success=True,
            elapsed_ms=elapsed_ms,
            usage=usage,
        )


def schedule_ai_call_metric(
    *,
    task: str,
    provider: str | None,
    model: str | None = None,
    user_id: str | None = None,
    success: bool = True,
    error_code: str | None = None,
    elapsed_ms: int | None = None,
    usage: dict[str, int] | None = None,
) -> None:
    """Best-effort persist of AI call metrics without blocking the request path."""
    import asyncio

    async def _run() -> None:
        try:
            from app.db.session import get_shared_database
            from app.repositories.ai_metrics import try_record_ai_call

            usage_map = usage or {}
            total = usage_map.get("total_tokens")
            if total is None and ("prompt_tokens" in usage_map or "completion_tokens" in usage_map):
                total = int(usage_map.get("prompt_tokens") or 0) + int(usage_map.get("completion_tokens") or 0)
            await try_record_ai_call(
                get_shared_database(),
                task=task,
                provider=provider,
                model=model,
                user_id=user_id,
                success=success,
                error_code=error_code,
                elapsed_ms=elapsed_ms,
                prompt_tokens=usage_map.get("prompt_tokens") or usage_map.get("input_tokens"),
                completion_tokens=usage_map.get("completion_tokens") or usage_map.get("output_tokens"),
                total_tokens=total,
            )
        except Exception:
            logger.debug("ai_call_metrics schedule failed", exc_info=True)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        return


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
