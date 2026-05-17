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

    async with client.stream("POST", url, headers=headers, json=streamed_payload, timeout=timeout) as response:
        if response.status_code >= 400:
            body = await response.aread()
            response._content = body
            raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
        async for line in response.aiter_lines():
            if not line:
                continue
            response_chars += len(line)
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            content = _content_from_stream_event(event)
            if content:
                chunks.append(content)

    return "".join(chunks), response_chars


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
