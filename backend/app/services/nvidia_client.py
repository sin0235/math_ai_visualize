import json
import time

import httpx

from app.core.config import Settings
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.chat_response import extract_chat_message_content
from app.services.chat_stream import collect_openai_chat_stream
from app.services.openrouter_client import OCR_SYSTEM_PROMPT
from app.services.provider_logging import format_provider_error, log_ocr_summary, log_provider_http_error, log_provider_request, log_provider_response, log_scene_summary


class NvidiaClient:
    def __init__(
        self,
        settings: Settings,
        model: str | None = None,
        reasoning_effort: str | None = None,
        thinking: bool = False,
    ) -> None:
        self.settings = settings
        self.model = model or settings.nvidia_text_model
        self.reasoning_effort = reasoning_effort
        self.thinking = thinking

    async def extract_scene_json(
        self,
        problem_text: str,
        grade: int | None = None,
        reasoning_layer: str = "off",
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        if not _api_key(self.settings):
            raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình.")

        sys_prompt = system_prompt or SCENE_EXTRACTION_SYSTEM_PROMPT

        chat_template_kwargs: dict[str, str | bool] = {}
        if self.thinking:
            chat_template_kwargs["thinking"] = True
        if self.reasoning_effort:
            chat_template_kwargs["reasoning_effort"] = self.reasoning_effort

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan)},
            ],
            "temperature": 0.1,
            "top_p": 0.95,
            "max_tokens": 4096,
        }
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        headers = {
            "Authorization": f"Bearer {_api_key(self.settings)}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"

        try:
            from app.services.http_pool import TIMEOUT_SCENE, get_client

            started_at = time.perf_counter()
            log_provider_request("nvidia", "scene", url, payload["model"], problem_chars=len(problem_text), thinking=self.thinking)
            client = get_client(self.settings.nvidia_base_url.rstrip("/"), TIMEOUT_SCENE)
            content, response_chars = await collect_openai_chat_stream(client, url, headers=headers, payload=payload, timeout=TIMEOUT_SCENE)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("nvidia", "scene", 200, elapsed_ms, response_chars, payload["model"])
        except httpx.HTTPStatusError as error:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("nvidia", "scene", error.response.status_code, elapsed_ms, len(error.response.text), payload["model"])
            log_provider_http_error("nvidia", "scene", error.response, payload["model"])
            raise RuntimeError(_format_nvidia_error(error.response)) from error
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"NVIDIA request lỗi: {message}") from error

        if not content.strip():
            raise RuntimeError("NVIDIA không trả về nội dung JSON trong choices[0].message.content.")
        try:
            scene_json = json.loads(_strip_json_fences(content))
            log_scene_summary("nvidia", scene_json)
            return scene_json
        except json.JSONDecodeError as error:
            raise RuntimeError(f"NVIDIA trả về JSON không hợp lệ: {error.msg}") from error

    async def reason_about_problem(self, problem_text: str, grade: int | None = None, system_prompt: str | None = None) -> dict:
        """Task 1: Analyze the problem and return a structured reasoning plan."""
        if not _api_key(self.settings):
            raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình.")

        sys_prompt = system_prompt or REASONING_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_reasoning_prompt(problem_text, grade)},
            ],
            "temperature": 0.15,
            "top_p": 0.95,
            "max_tokens": 16384,
        }
        if self.thinking:
            payload["chat_template_kwargs"] = {"thinking": True}
        headers = {
            "Authorization": f"Bearer {_api_key(self.settings)}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"

        try:
            from app.services.http_pool import TIMEOUT_REASONING, get_client

            started_at = time.perf_counter()
            log_provider_request("nvidia", "reasoning", url, payload["model"], problem_chars=len(problem_text), thinking=self.thinking)
            client = get_client(self.settings.nvidia_base_url.rstrip("/"), TIMEOUT_REASONING)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_REASONING)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("nvidia", "reasoning", response.status_code, elapsed_ms, len(response.text), payload["model"])
            if response.status_code >= 400:
                log_provider_http_error("nvidia", "reasoning", response, payload["model"])
                raise RuntimeError(_format_nvidia_error(response))
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"NVIDIA reasoning request lỗi: {message}") from error

        message = _extract_message(response)
        content = extract_chat_message_content(message)
        if not content.strip():
            raise RuntimeError("NVIDIA không trả về reasoning content.")
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"NVIDIA reasoning JSON không hợp lệ: {error.msg}") from error

    async def ocr_image(self, image_data_url: str, model: str | None = None, system_prompt: str | None = None, user_text: str = "Trích xuất nguyên văn đề toán trong ảnh.") -> str:
        if not _api_key(self.settings):
            raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình.")

        selected_model = model or self.model
        payload = {
            "model": selected_model,
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
            "temperature": 0.2 if selected_model == "google/gemma-3n-e2b-it" else 0.15,
            "top_p": 0.7 if selected_model == "google/gemma-3n-e2b-it" else 1.0,
            "max_tokens": 512 if selected_model == "google/gemma-3n-e2b-it" else 2048,
            "frequency_penalty": 0,
            "presence_penalty": 0,
        }
        headers = {
            "Authorization": f"Bearer {_api_key(self.settings)}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"

        try:
            from app.services.http_pool import TIMEOUT_OCR, get_client

            started_at = time.perf_counter()
            log_provider_request("nvidia", "ocr", url, payload["model"], image_chars=len(image_data_url))
            client = get_client(self.settings.nvidia_base_url.rstrip("/"), TIMEOUT_OCR)
            response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_OCR)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("nvidia", "ocr", response.status_code, elapsed_ms, len(response.text), payload["model"])
            if response.status_code >= 400:
                log_provider_http_error("nvidia", "ocr", response, payload["model"])
                raise RuntimeError(_format_nvidia_error(response))
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"NVIDIA OCR request lỗi: {message}") from error

        message = _extract_message(response)
        content = extract_chat_message_content(message)
        if not content.strip():
            raise RuntimeError("NVIDIA không trả về nội dung OCR trong choices[0].message.content.")
        text = _strip_text_fences(content)
        log_ocr_summary("nvidia", text)
        return text


def _extract_message(response: httpx.Response) -> dict:
    try:
        body = response.json()
        return body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("NVIDIA response không đúng định dạng choices[0].message.") from error


def _api_key(settings: Settings) -> str:
    return (settings.nvidia_api_key or "").strip()


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


def _strip_text_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```json"):
        return text.removeprefix("```json").removesuffix("```").strip()
    if text.startswith("```"):
        return text.removeprefix("```").removesuffix("```").strip()
    return text


def _format_nvidia_error(response: httpx.Response) -> str:
    return format_provider_error("NVIDIA", response)
