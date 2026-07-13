import json
import time

import httpx

from app.core.config import Settings
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.chat_response import extract_chat_message_content
from app.services.openrouter_client import OCR_SYSTEM_PROMPT, _strip_text_fences
from app.services.provider_logging import chat_message_input_chars, log_ocr_summary, log_provider_request, log_provider_response, log_scene_summary


class OllamaClient:
    def __init__(self, settings: Settings, model: str | None = None, provider_id: str = "ollama") -> None:
        self.settings = settings
        self.model = model or settings.ollama_text_model
        self.provider_id = provider_id

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
            from app.services.http_pool import TIMEOUT_SCENE, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "scene", url, payload["model"], problem_chars=len(problem_text), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_SCENE)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_SCENE)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "scene", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama request lỗi: {message}") from error

        try:
            content = extract_chat_message_content(response.json()["message"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama response không đúng định dạng message.content") from error
        if not content.strip():
            raise RuntimeError("Ollama response message.content không có nội dung")
        scene_json = json.loads(_strip_json_fences(content))
        log_scene_summary(self.provider_id, scene_json)
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
            from app.services.http_pool import TIMEOUT_SCENE, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "scene", url, payload["model"], problem_chars=len(problem_text), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_SCENE)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_SCENE)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "scene", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama cloud request lỗi: {message}") from error

        try:
            content = extract_chat_message_content(response.json()["choices"][0]["message"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama cloud response không đúng định dạng choices[0].message.content") from error
        if not content.strip():
            raise RuntimeError("Ollama cloud response message.content không có nội dung")
        scene_json = json.loads(_strip_json_fences(content))
        log_scene_summary(self.provider_id, scene_json)
        return scene_json

    async def ocr_image(self, image_data_url: str, model: str | None = None, system_prompt: str | None = None, user_text: str = "Trích xuất nguyên văn đề toán trong ảnh.") -> str:
        selected_model = model or self.model
        if not selected_model:
            raise RuntimeError("Chưa chọn model Ollama cho OCR.")
        base_url = self.settings.ollama_base_url.rstrip("/")
        if _uses_openai_compatible_api(base_url):
            return await self._ocr_openai_compatible(base_url, image_data_url, selected_model, system_prompt, user_text)
        return await self._ocr_local(base_url, image_data_url, selected_model, system_prompt, user_text)

    async def _ocr_local(self, base_url: str, image_data_url: str, model: str, system_prompt: str | None, user_text: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"
        image_payload = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt or OCR_SYSTEM_PROMPT},
                {"role": "user", "content": user_text, "images": [image_payload]},
            ],
            "options": {"temperature": 0},
        }
        url = f"{base_url}/api/chat"
        try:
            from app.services.http_pool import TIMEOUT_OCR, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "ocr", url, payload["model"], image_chars=len(image_data_url), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_OCR)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_OCR)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "ocr", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama OCR request lỗi: {message}") from error
        try:
            content = extract_chat_message_content(response.json()["message"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama OCR response không đúng định dạng message.content") from error
        text = _strip_text_fences(content)
        log_ocr_summary(self.provider_id, text)
        return text

    async def _ocr_openai_compatible(self, base_url: str, image_data_url: str, model: str, system_prompt: str | None, user_text: str) -> str:
        if not self.settings.ollama_api_key:
            raise RuntimeError("OLLAMA_API_KEY chưa được cấu hình cho Ollama cloud.")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.settings.ollama_api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/chat/completions"
        try:
            from app.services.http_pool import TIMEOUT_OCR, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "ocr", url, payload["model"], image_chars=len(image_data_url), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_OCR)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_OCR)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "ocr", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama cloud OCR request lỗi: {message}") from error
        try:
            content = extract_chat_message_content(response.json()["choices"][0]["message"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("Ollama cloud OCR response không đúng định dạng choices[0].message.content") from error
        text = _strip_text_fences(content)
        log_ocr_summary(self.provider_id, text)
        return text

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
            from app.services.http_pool import TIMEOUT_REASONING, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "reasoning", url, payload["model"], problem_chars=len(problem_text), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_REASONING)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_REASONING)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "reasoning", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama reasoning request lỗi: {message}") from error

        try:
            content = extract_chat_message_content(response.json()["message"])
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
            from app.services.http_pool import TIMEOUT_REASONING, get_client

            started_at = time.perf_counter()
            log_provider_request(self.provider_id, "reasoning", url, payload["model"], problem_chars=len(problem_text), input_chars=chat_message_input_chars(payload.get("messages")))
            client = get_client(base_url, TIMEOUT_REASONING)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_REASONING)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response(self.provider_id, "reasoning", response.status_code, elapsed_ms, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"Ollama cloud reasoning request lỗi: {message}") from error

        try:
            content = extract_chat_message_content(response.json()["choices"][0]["message"])
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
