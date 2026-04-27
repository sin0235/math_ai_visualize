import json

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt


class NvidiaClient:
    def __init__(
        self,
        settings: Settings,
        model: str | None = None,
        reasoning_effort: str | None = None,
        thinking: bool = True,
    ) -> None:
        self.settings = settings
        self.model = model or settings.nvidia_text_model
        self.reasoning_effort = reasoning_effort
        self.thinking = thinking

    async def extract_scene_json(self, problem_text: str, grade: int | None = None) -> dict:
        if not self.settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình.")

        chat_template_kwargs: dict[str, str | bool] = {}
        if self.thinking:
            chat_template_kwargs["thinking"] = True
        if self.reasoning_effort:
            chat_template_kwargs["reasoning_effort"] = self.reasoning_effort

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade)},
            ],
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 16384,
        }
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        headers = {
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(_format_nvidia_error(response))

        message = _extract_message(response)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("NVIDIA không trả về nội dung JSON trong choices[0].message.content.")
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"NVIDIA trả về JSON không hợp lệ: {error.msg}") from error


def _extract_message(response: httpx.Response) -> dict:
    try:
        body = response.json()
        return body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("NVIDIA response không đúng định dạng choices[0].message.") from error


def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def _format_nvidia_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    return f"NVIDIA HTTP {response.status_code}: {body}"
