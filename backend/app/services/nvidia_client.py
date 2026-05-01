import json
import time

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt
from app.services.openrouter_client import OCR_SYSTEM_PROMPT
from app.services.provider_logging import format_provider_error, log_ocr_summary, log_provider_request, log_provider_response, log_scene_summary


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

    async def extract_scene_json(self, problem_text: str, grade: int | None = None, reasoning_layer: str = "off") -> dict:
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
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer)},
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

        try:
            started_at = time.perf_counter()
            log_provider_request("nvidia", "scene", url, payload["model"], problem_chars=len(problem_text), thinking=self.thinking)
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("nvidia", "scene", response.status_code, elapsed_ms, len(response.text))
                if response.status_code >= 400:
                    raise RuntimeError(_format_nvidia_error(response))
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"NVIDIA request lỗi: {message}") from error

        message = _extract_message(response)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("NVIDIA không trả về nội dung JSON trong choices[0].message.content.")
        try:
            scene_json = json.loads(_strip_json_fences(content))
            log_scene_summary("nvidia", scene_json)
            return scene_json
        except json.JSONDecodeError as error:
            raise RuntimeError(f"NVIDIA trả về JSON không hợp lệ: {error.msg}") from error

    async def ocr_image(self, image_data_url: str, model: str | None = None) -> str:
        if not self.settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY chưa được cấu hình.")

        selected_model = model or self.model
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Trích xuất nguyên văn đề toán trong ảnh."},
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
            "Authorization": f"Bearer {self.settings.nvidia_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.nvidia_base_url.rstrip('/')}/chat/completions"

        try:
            started_at = time.perf_counter()
            log_provider_request("nvidia", "ocr", url, payload["model"], image_chars=len(image_data_url))
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("nvidia", "ocr", response.status_code, elapsed_ms, len(response.text))
                if response.status_code >= 400:
                    raise RuntimeError(_format_nvidia_error(response))
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"NVIDIA OCR request lỗi: {message}") from error

        message = _extract_message(response)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
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
