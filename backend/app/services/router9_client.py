import json
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.openrouter_client import OCR_SYSTEM_PROMPT
from app.services.provider_logging import format_provider_error, log_ocr_summary, log_provider_request, log_provider_response, log_scene_summary


class Router9Client:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.router9_text_model

    async def list_models(self) -> list[AiModelInfo]:
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")

        headers = _build_headers(self.settings)
        url = f"{self.settings.router9_base_url.rstrip('/')}/models"
        models: list[AiModelInfo] = []
        params: dict[str, str] = {}
        seen_cursors: set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                while True:
                    response = await client.get(url, headers=headers, params=params or None)
                    if response.status_code >= 400:
                        raise RuntimeError(_format_router9_error(response))
                    body = response.json()
                    data = body.get("data") if isinstance(body, dict) else None
                    if not isinstance(data, list):
                        raise RuntimeError("9router response không đúng định dạng data[].")
                    models.extend(_parse_router9_models(data))
                    next_cursor = _next_models_cursor(body)
                    if not next_cursor or next_cursor in seen_cursors:
                        break
                    seen_cursors.add(next_cursor)
                    params = {"cursor": next_cursor}
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"9router models request lỗi: {message}") from error
        except ValueError as error:
            raise RuntimeError("9router response không phải JSON hợp lệ.") from error

        by_id = {model.id: model for model in models}
        return sorted(by_id.values(), key=lambda model: model.id.lower())

    async def extract_scene_json(
        self,
        problem_text: str,
        grade: int | None = None,
        reasoning_layer: str = "off",
        reasoning_plan: dict | None = None,
        system_prompt: str | None = None,
    ) -> dict:
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")
        if not self.model:
            raise RuntimeError("Chưa chọn model 9router.")

        sys_prompt = system_prompt or SCENE_EXTRACTION_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan)},
            ],
            "temperature": 0.1,
            "stream": False,
        }
        response = await self._post_chat(payload)

        try:
            content = _extract_message_content(response)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("9router response không đúng định dạng choices[0].message.content") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("9router không trả về nội dung JSON trong choices[0].message.content.")
        try:
            scene_json = json.loads(_strip_json_fences(content))
            log_scene_summary("9router", scene_json)
            return scene_json
        except json.JSONDecodeError as error:
            raise RuntimeError(f"9router trả về JSON không hợp lệ: {error.msg}") from error

    async def reason_about_problem(self, problem_text: str, grade: int | None = None, system_prompt: str | None = None) -> dict:
        """Task 1: Analyze the problem and return a structured reasoning plan."""
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")
        if not self.model:
            raise RuntimeError("Chưa chọn model 9router.")

        sys_prompt = system_prompt or REASONING_SYSTEM_PROMPT

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": build_reasoning_prompt(problem_text, grade)},
            ],
            "temperature": 0.15,
            "stream": False,
        }
        response = await self._post_chat(payload)

        try:
            content = _extract_message_content(response)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("9router reasoning response không đúng định dạng") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("9router không trả về nội dung reasoning.")
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"9router reasoning JSON không hợp lệ: {error.msg}") from error

    async def ocr_image(self, image_data_url: str, model: str | None = None) -> str:
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")
        selected_model = model or self.model
        if not selected_model:
            raise RuntimeError("Chưa chọn model OCR 9router.")

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
            "temperature": 0,
            "stream": False,
        }
        response = await self._post_chat(payload)

        try:
            content = _extract_message_content(response)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("9router response không đúng định dạng choices[0].message.content") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("9router không trả về nội dung OCR trong choices[0].message.content.")
        text = _strip_text_fences(content)
        log_ocr_summary("9router", text)
        return text

    async def _post_chat(self, payload: dict) -> httpx.Response:
        headers = _build_headers(self.settings)
        url = f"{self.settings.router9_base_url.rstrip('/')}/chat/completions"
        try:
            started_at = time.perf_counter()
            kind = "ocr" if any(isinstance(message.get("content"), list) for message in payload.get("messages", []) if isinstance(message, dict)) else "scene"
            input_chars = sum(len(message.get("content", "")) for message in payload.get("messages", []) if isinstance(message, dict) and isinstance(message.get("content"), str))
            log_provider_request("9router", kind, url, payload.get("model"), input_chars=input_chars)
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("9router", kind, response.status_code, elapsed_ms, len(response.text))
                if response.status_code >= 400:
                    raise RuntimeError(_format_router9_error(response))
                return response
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"9router request lỗi: {message}") from error


def _build_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.router9_api_key}",
        "Content-Type": "application/json",
    }


def _extract_message_content(response: httpx.Response) -> str:
    message = response.json()["choices"][0]["message"]
    content = message["content"]
    if isinstance(content, list):
        text_parts = [
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "".join(text_parts)
    return content


def _parse_router9_models(data: list[Any]) -> list[AiModelInfo]:
    models: list[AiModelInfo] = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        models.append(
            AiModelInfo(
                id=model_id,
                label=model_id,
                owned_by=_optional_str(item.get("owned_by")),
                created=_optional_int(item.get("created")),
                context_length=_extract_context_length(item),
            )
        )
    return models


def _next_models_cursor(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("next_cursor", "next", "cursor"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    meta = body.get("meta")
    if isinstance(meta, dict):
        for key in ("next_cursor", "next", "cursor"):
            value = meta.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _extract_context_length(item: dict[str, Any]) -> int | None:
    for key in ("context_length", "context_window", "max_context_length"):
        value = item.get(key)
        if isinstance(value, int):
            return value
    return None


def _strip_json_fences(content: str) -> str:
    text = _strip_text_fences(content)
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


def _format_router9_error(response: httpx.Response) -> str:
    return format_provider_error("9router", response)
