import json

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt


class OllamaClient:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.ollama_text_model

    async def extract_scene_json(self, problem_text: str, grade: int | None = None, reasoning_layer: str = "off") -> dict:
        base_url = self.settings.ollama_base_url.rstrip("/")
        if _uses_openai_compatible_api(base_url):
            return await self._extract_scene_json_openai_compatible(base_url, problem_text, grade, reasoning_layer)
        return await self._extract_scene_json_local(base_url, problem_text, grade, reasoning_layer)

    async def _extract_scene_json_local(self, base_url: str, problem_text: str, grade: int | None, reasoning_layer: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer)},
            ],
            "options": {"temperature": 0.1},
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(f"{base_url}/api/chat", headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama request lỗi: {message}") from error

        try:
            content = response.json()["message"]["content"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama response không đúng định dạng message.content") from error
        if not isinstance(content, str):
            raise RuntimeError("Ollama response message.content không phải chuỗi")
        return json.loads(_strip_json_fences(content))

    async def _extract_scene_json_openai_compatible(self, base_url: str, problem_text: str, grade: int | None, reasoning_layer: str) -> dict:
        if not self.settings.ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY chưa được cấu hình cho Ollama cloud.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.ollama_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama cloud request lỗi: {message}") from error

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama cloud response không đúng định dạng choices[0].message.content") from error
        if not isinstance(content, str):
            raise RuntimeError("Ollama cloud response message.content không phải chuỗi")
        return json.loads(_strip_json_fences(content))


def _uses_openai_compatible_api(base_url: str) -> bool:
    return base_url.endswith("/v1") or "ollama.com" in base_url


def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").removesuffix("```").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").removesuffix("```").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text
