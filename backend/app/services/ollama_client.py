import json
import time

import httpx

from app.core.config import Settings
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.provider_logging import log_provider_request, log_provider_response, log_scene_summary


class OllamaClient:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.ollama_text_model

    async def extract_scene_json(
        self,
        problem_text: str,
        grade: int | None = None,
        reasoning_layer: str = "off",
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        base_url = self.settings.ollama_base_url.rstrip("/")
        if _uses_openai_compatible_api(base_url):
            return await self._extract_scene_json_openai_compatible(base_url, problem_text, grade, reasoning_layer, reasoning_plan, system_prompt=system_prompt)
        return await self._extract_scene_json_local(base_url, problem_text, grade, reasoning_layer, reasoning_plan, system_prompt=system_prompt)

    async def _extract_scene_json_local(
        self,
        base_url: str,
        problem_text: str,
        grade: int | None,
        reasoning_layer: str,
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        sys_prompt = system_prompt or SCENE_EXTRACTION_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan)},
            ],
            "options": {"temperature": 0.1},
        }

        url = f"{base_url}/api/chat"
        try:
            started_at = time.perf_counter()
            log_provider_request("ollama", "scene", url, payload["model"], problem_chars=len(problem_text))
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("ollama", "scene", response.status_code, elapsed_ms, len(response.text))
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
        scene_json = json.loads(_strip_json_fences(content))
        log_scene_summary("ollama", scene_json)
        return scene_json

    async def _extract_scene_json_openai_compatible(
        self,
        base_url: str,
        problem_text: str,
        grade: int | None,
        reasoning_layer: str,
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        if not self.settings.ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY chưa được cấu hình cho Ollama cloud.")

        sys_prompt = system_prompt or SCENE_EXTRACTION_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan)},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.ollama_api_key}",
            "Content-Type": "application/json",
        }

        url = f"{base_url}/chat/completions"
        try:
            started_at = time.perf_counter()
            log_provider_request("ollama_cloud", "scene", url, payload["model"], problem_chars=len(problem_text))
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("ollama_cloud", "scene", response.status_code, elapsed_ms, len(response.text))
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
        scene_json = json.loads(_strip_json_fences(content))
        log_scene_summary("ollama_cloud", scene_json)
        return scene_json

    async def reason_about_problem(self, problem_text: str, grade: int | None = None, system_prompt: str | None = None) -> dict:
        """Task 1: Analyze the problem and return a structured reasoning plan."""
        base_url = self.settings.ollama_base_url.rstrip("/")
        if _uses_openai_compatible_api(base_url):
            return await self._reason_openai_compatible(base_url, problem_text, grade, system_prompt=system_prompt)
        return await self._reason_local(base_url, problem_text, grade, system_prompt=system_prompt)

    async def _reason_local(self, base_url: str, problem_text: str, grade: int | None, system_prompt: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        sys_prompt = system_prompt or REASONING_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_reasoning_prompt(problem_text, grade)},
            ],
            "options": {"temperature": 0.15},
        }
        url = f"{base_url}/api/chat"
        try:
            started_at = time.perf_counter()
            log_provider_request("ollama", "reasoning", url, payload["model"], problem_chars=len(problem_text))
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("ollama", "reasoning", response.status_code, elapsed_ms, len(response.text))
                response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama reasoning request lỗi: {message}") from error

        try:
            content = response.json()["message"]["content"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama reasoning response không đúng định dạng") from error
        return json.loads(_strip_json_fences(content))

    async def _reason_openai_compatible(self, base_url: str, problem_text: str, grade: int | None, system_prompt: str | None = None) -> dict:
        if not self.settings.ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY chưa được cấu hình cho Ollama cloud.")

        sys_prompt = system_prompt or REASONING_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_reasoning_prompt(problem_text, grade)},
            ],
            "temperature": 0.15,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.ollama_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{base_url}/chat/completions"
        try:
            started_at = time.perf_counter()
            log_provider_request("ollama_cloud", "reasoning", url, payload["model"], problem_chars=len(problem_text))
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("ollama_cloud", "reasoning", response.status_code, elapsed_ms, len(response.text))
                response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama cloud reasoning request lỗi: {message}") from error

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama cloud reasoning response không đúng định dạng") from error
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
