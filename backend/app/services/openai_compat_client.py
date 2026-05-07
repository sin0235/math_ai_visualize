from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.openrouter_client import _strip_json_fences
from app.services.provider_logging import format_provider_error, log_provider_request, log_provider_response, log_scene_summary


class OpenAICompatClient:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.openai_compat_text_model

    async def extract_scene_json(
        self,
        problem_text: str,
        grade: int | None = None,
        reasoning_layer: str = "off",
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        if not self.settings.openai_compat_api_key:
            raise RuntimeError("OPENAI_COMPAT_API_KEY chưa được cấu hình.")
        if not self.model:
            raise RuntimeError("Chưa chọn model OpenAI-compatible.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan)},
            ],
            "temperature": 0.1,
        }
        content = await self._post_chat(payload, "scene", problem_chars=len(problem_text))
        try:
            scene_json = json.loads(_strip_json_fences(content))
            log_scene_summary("openai_compat", scene_json)
            return scene_json
        except json.JSONDecodeError as error:
            raise RuntimeError(f"OpenAI-compatible trả về JSON không hợp lệ: {error.msg}") from error

    async def reason_about_problem(self, problem_text: str, grade: int | None = None, system_prompt: str | None = None) -> dict:
        if not self.settings.openai_compat_api_key:
            raise RuntimeError("OPENAI_COMPAT_API_KEY chưa được cấu hình.")
        if not self.model:
            raise RuntimeError("Chưa chọn model OpenAI-compatible.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": build_reasoning_prompt(problem_text, grade)},
            ],
            "temperature": 0.15,
        }
        content = await self._post_chat(payload, "reasoning", problem_chars=len(problem_text))
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"OpenAI-compatible reasoning JSON không hợp lệ: {error.msg}") from error

    async def _post_chat(self, payload: dict[str, Any], kind: str, **log_kwargs: Any) -> str:
        url = f"{self.settings.openai_compat_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_compat_api_key}",
            "Content-Type": "application/json",
        }
        started_at = time.perf_counter()
        log_provider_request("openai_compat", kind, url, payload.get("model"), **log_kwargs)
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=headers, json=payload)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("openai_compat", kind, response.status_code, elapsed_ms, len(response.text))
            if response.status_code >= 400:
                raise RuntimeError(format_provider_error("OpenAI-compatible", response))
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise RuntimeError("OpenAI-compatible response không đúng định dạng choices[0].message.content.") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenAI-compatible không trả về nội dung.")
        return content
