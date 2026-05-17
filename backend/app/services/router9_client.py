import json
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.chat_response import extract_chat_message_content
from app.services.chat_stream import collect_openai_chat_stream
from app.services.openrouter_client import OCR_SYSTEM_PROMPT
from app.services.model_scan import CAPABILITY_KEYS, _extract_capabilities
from app.services.provider_logging import format_provider_error, log_ocr_summary, log_provider_http_error, log_provider_request, log_provider_response, log_scene_summary


class Router9Client:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.router9_text_model

    async def list_models(self) -> list[AiModelInfo]:
        if not _api_key(self.settings):
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")

        headers = _build_headers(self.settings)
        url = f"{self.settings.router9_base_url.rstrip('/')}/models"
        models: list[AiModelInfo] = []
        params: dict[str, str] = {}
        seen_cursors: set[str] = set()
        try:
            from app.services.http_pool import TIMEOUT_MODELS, get_client
            client = get_client(self.settings.router9_base_url.rstrip("/"), TIMEOUT_MODELS)
            while True:
                if params:
                    response = await client.get(url, headers=headers, params=params, timeout=TIMEOUT_MODELS)
                else:
                    response = await client.get(url, headers=headers, timeout=TIMEOUT_MODELS)
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
        if not _api_key(self.settings):
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
        if not _api_key(self.settings):
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
        from app.services.http_pool import TIMEOUT_REASONING
        response = await self._post_chat(payload, timeout=TIMEOUT_REASONING)

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

    async def ocr_image(self, image_data_url: str, model: str | None = None, system_prompt: str | None = None, user_text: str = "Trích xuất nguyên văn đề toán trong ảnh.") -> str:
        if not _api_key(self.settings):
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")
        selected_model = model or self.model
        if not selected_model:
            raise RuntimeError("Chưa chọn model OCR 9router.")

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
            "temperature": 0,
            "stream": False,
        }
        from app.services.http_pool import TIMEOUT_OCR
        response = await self._post_chat(payload, timeout=TIMEOUT_OCR)

        try:
            content = _extract_message_content(response)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("9router response không đúng định dạng choices[0].message.content") from error
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("9router không trả về nội dung OCR trong choices[0].message.content.")
        text = _strip_text_fences(content)
        log_ocr_summary("9router", text)
        return text

    async def _post_chat(self, payload: dict, timeout: httpx.Timeout | None = None) -> httpx.Response:
        from app.services.http_pool import TIMEOUT_SCENE, get_client

        headers = _build_headers(self.settings)
        base_url = self.settings.router9_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        try:
            started_at = time.perf_counter()
            kind = "ocr" if any(isinstance(message.get("content"), list) for message in payload.get("messages", []) if isinstance(message, dict)) else "scene"
            input_chars = sum(len(message.get("content", "")) for message in payload.get("messages", []) if isinstance(message, dict) and isinstance(message.get("content"), str))
            log_provider_request("9router", kind, url, payload.get("model"), input_chars=input_chars)
            client = get_client(base_url, timeout or TIMEOUT_SCENE)
            if kind == "scene":
                try:
                    content, response_chars = await collect_openai_chat_stream(client, url, headers=headers, payload=payload, timeout=timeout or TIMEOUT_SCENE)
                except RuntimeError as error:
                    response = await client.post(url, headers=headers, json=payload, timeout=timeout or TIMEOUT_SCENE)
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    log_provider_response("9router", kind, response.status_code, elapsed_ms, len(response.text), payload.get("model"))
                    if response.status_code >= 400:
                        log_provider_http_error("9router", kind, response, payload.get("model"))
                        raise RuntimeError(_format_router9_error(response)) from error
                    return response
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 400:
                        response = await client.post(url, headers=headers, json=payload, timeout=timeout or TIMEOUT_SCENE)
                        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                        log_provider_response("9router", kind, response.status_code, elapsed_ms, len(response.text), payload.get("model"))
                        if response.status_code >= 400:
                            log_provider_http_error("9router", kind, response, payload.get("model"))
                            raise RuntimeError(_format_router9_error(response)) from error
                        return response
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    log_provider_response("9router", kind, error.response.status_code, elapsed_ms, len(error.response.text), payload.get("model"))
                    log_provider_http_error("9router", kind, error.response, payload.get("model"))
                    raise RuntimeError(_format_router9_error(error.response)) from error
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                log_provider_response("9router", kind, 200, elapsed_ms, response_chars, payload.get("model"))
                return _stream_response(content)
            response = await client.post(url, headers=headers, json=payload, timeout=timeout or TIMEOUT_SCENE)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            log_provider_response("9router", kind, response.status_code, elapsed_ms, len(response.text), payload.get("model"))
            if response.status_code >= 400:
                log_provider_http_error("9router", kind, response, payload.get("model"))
                raise RuntimeError(_format_router9_error(response))
            return response
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"9router request lỗi: {message}") from error


def _stream_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _build_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key(settings)}",
        "Content-Type": "application/json",
    }


def _api_key(settings: Settings) -> str:
    return (settings.router9_api_key or "").strip()


def _extract_message_content(response: httpx.Response) -> str:
    message = response.json()["choices"][0]["message"]
    return extract_chat_message_content(message)


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
                capabilities=_extract_capabilities(item, CAPABILITY_KEYS),
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
