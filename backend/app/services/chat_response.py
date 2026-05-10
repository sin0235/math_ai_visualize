from __future__ import annotations

from typing import Any


def extract_chat_message_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
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
        return "".join(text_parts)
    return ""
