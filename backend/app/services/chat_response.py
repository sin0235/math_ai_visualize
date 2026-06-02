from __future__ import annotations

from typing import Any


def extract_chat_message_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
                continue
            nested_text = part.get("content")
            if isinstance(nested_text, str):
                text_parts.append(nested_text)
        joined = "".join(text_parts)
        if joined:
            return joined
    for key in ("reasoning", "reasoning_content", "refusal"):
        fallback = message.get(key)
        if isinstance(fallback, str):
            return fallback
    return ""


def extract_chat_response_content(body: dict[str, Any]) -> str:
    """Extract assistant text from common OpenAI-compatible response shapes."""
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message") or first_choice.get("delta")
            if isinstance(message, dict):
                content = extract_chat_message_content(message)
                if content:
                    return content
            text = first_choice.get("text")
            if isinstance(text, str):
                return text

    output_text = body.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = body.get("output")
    if isinstance(output, list):
        text_parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            item_text = item.get("text")
            if isinstance(item_text, str):
                text_parts.append(item_text)
            content = item.get("content")
            if isinstance(content, list):
                text_parts.append(extract_chat_message_content({"content": content}))
            elif isinstance(content, str):
                text_parts.append(content)
        if text_parts:
            return "".join(text_parts)

    message = body.get("message")
    if isinstance(message, dict):
        return extract_chat_message_content(message)

    return ""


def chat_response_shape(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"type": type(body).__name__}
    shape: dict[str, Any] = {"keys": sorted(str(key) for key in body.keys())[:20]}
    choices = body.get("choices")
    if isinstance(choices, list):
        shape["choices_len"] = len(choices)
        if choices and isinstance(choices[0], dict):
            shape["choice_keys"] = sorted(str(key) for key in choices[0].keys())[:20]
            message = choices[0].get("message") or choices[0].get("delta")
            if isinstance(message, dict):
                shape["message_keys"] = sorted(str(key) for key in message.keys())[:20]
    output = body.get("output")
    if isinstance(output, list):
        shape["output_len"] = len(output)
        if output and isinstance(output[0], dict):
            shape["output_item_keys"] = sorted(str(key) for key in output[0].keys())[:20]
    return shape
