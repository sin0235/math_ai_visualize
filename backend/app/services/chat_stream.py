import json
from typing import Any

import httpx

from app.services.chat_response import extract_chat_message_content


async def collect_openai_chat_stream(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: httpx.Timeout,
) -> tuple[str, int]:
    streamed_payload = dict(payload)
    streamed_payload["stream"] = True
    chunks: list[str] = []
    response_chars = 0
    event_type = "message"

    async with client.stream("POST", url, headers=headers, json=streamed_payload, timeout=timeout) as response:
        if response.status_code >= 400:
            body = await response.aread()
            response._content = body
            raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
        async for line in response.aiter_lines():
            if not line:
                continue
            response_chars += len(line)
            if line.startswith("event:"):
                event_type = line.removeprefix("event:").strip() or "message"
                continue
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data:
                continue
            if data == "[DONE]":
                event_type = "message"
                continue
            if event_type == "error":
                raise RuntimeError(_stream_error_message(data))
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                event_type = "message"
                continue
            content = _content_from_stream_event(event)
            if content:
                chunks.append(content)
            event_type = "message"

    return "".join(chunks), response_chars


def extract_openai_chat_stream_content(text: str) -> str:
    chunks: list[str] = []
    event_type = "message"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip() or "message"
            continue
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data:
            continue
        if data == "[DONE]":
            event_type = "message"
            continue
        if event_type == "error":
            raise RuntimeError(_stream_error_message(data))
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            event_type = "message"
            continue
        content = _content_from_stream_event(event)
        if content:
            chunks.append(content)
        event_type = "message"
    return "".join(chunks)


def _stream_error_message(data: str) -> str:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return f"Provider stream error: {data}"
    if isinstance(payload, dict):
        error = payload.get("error") or payload.get("message") or payload.get("detail")
        status = payload.get("status")
        if error:
            prefix = f"Provider stream error {status}: " if status else "Provider stream error: "
            return prefix + str(error)
    return "Provider stream error: " + json.dumps(payload, ensure_ascii=False)


def _content_from_stream_event(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""
    delta = choice.get("delta")
    if isinstance(delta, dict):
        content = extract_chat_message_content(delta)
        if content:
            return content
    message = choice.get("message")
    if isinstance(message, dict):
        return extract_chat_message_content(message)
    text = choice.get("text")
    return text if isinstance(text, str) else ""
