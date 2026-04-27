import json

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt


class OpenRouterClient:
    def __init__(self, settings: Settings, model: str | None = None, reasoning_enabled: bool | None = None) -> None:
        self.settings = settings
        self.model = model or settings.openrouter_text_model
        self.reasoning_enabled = settings.openrouter_reasoning_enabled if reasoning_enabled is None else reasoning_enabled

    async def extract_scene_json(self, problem_text: str, grade: int | None = None) -> dict:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY chưa được cấu hình.")

        headers = _build_headers(self.settings)
        payload = {
            "model": _normalize_model_id(self.model),
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade)},
            ],
            "temperature": 0.1,
        }
        if self.reasoning_enabled:
            payload["reasoning"] = {"enabled": True}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(_format_openrouter_error(response))

        message = _extract_message(response)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenRouter không trả về nội dung JSON trong choices[0].message.content.")
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"OpenRouter trả về JSON không hợp lệ: {error.msg}") from error


def _build_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_x_title:
        headers["X-Title"] = settings.openrouter_x_title
    return headers


def _normalize_model_id(model: str) -> str:
    return model.removeprefix("openrouter/")


def _extract_message(response: httpx.Response) -> dict:
    try:
        body = response.json()
        return body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("OpenRouter response không đúng định dạng choices[0].message.") from error


def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def _format_openrouter_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    return f"OpenRouter HTTP {response.status_code}: {body}"
