from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.services.ai_prompt import REASONING_SYSTEM_PROMPT, SCENE_EXTRACTION_SYSTEM_PROMPT, build_reasoning_prompt, build_scene_extraction_prompt
from app.services.openrouter_client import OCR_SYSTEM_PROMPT, _strip_json_fences, _strip_text_fences
from app.services.chat_response import extract_chat_message_content
from app.services.provider_logging import chat_message_input_chars, format_provider_error, log_ocr_summary, log_provider_parse, log_provider_request, log_provider_response, log_scene_summary


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
            log_scene_summary("openai_compat", scene_json, model=self.model)
            return scene_json
        except json.JSONDecodeError as error:
            log_provider_parse_error("openai_compat", "scene", self.model, f"invalid_json: {error.msg}", response_chars=len(content))
            raise RuntimeError(f"OpenAI-compatible trả về JSON không hợp lệ: {error.msg}") from error

    async def reason_about_problem(self, problem_text: str, grade: int | None = None, system_prompt: str | None = None) -> dict:
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
            log_provider_parse_error("openai_compat", "reasoning", self.model, f"invalid_json: {error.msg}", response_chars=len(content))
            raise RuntimeError(f"OpenAI-compatible reasoning JSON không hợp lệ: {error.msg}") from error

    async def check_connection(self) -> str:
        if not self.model:
            raise RuntimeError("Chưa chọn model OpenAI-compatible.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": "Reply with OK only."},
            ],
            "temperature": 0,
            "max_tokens": 16,
        }
        return await self._post_chat(payload, "check")

    async def ocr_image(self, image_data_url: str, model: str | None = None, system_prompt: str | None = None, user_text: str = "Trích xuất nguyên văn đề toán trong ảnh.") -> str:
        selected_model = model or self.model
        if not selected_model:
            raise RuntimeError("Chưa chọn model OpenAI-compatible cho OCR.")
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
        }
        content = await self._post_chat(payload, "ocr", image_chars=len(image_data_url))
        text = _strip_text_fences(content)
        log_ocr_summary("openai_compat", text, model=selected_model)
        return text

    async def _post_chat(self, payload: dict[str, Any], kind: str, **log_kwargs: Any) -> str:
        base_url = self.settings.openai_compat_base_url.rstrip("/")
        api_key = (self.settings.openai_compat_api_key or "").strip()
        if not api_key and _requires_api_key(base_url):
            raise RuntimeError(
                f"OpenAI-compatible endpoint ({base_url}) cần API key nhưng chưa được cấu hình. "
                "Hãy thêm OPENAI_COMPAT_API_KEY hoặc chọn provider khác."
            )
        url = f"{_normalize_openai_compat_base_url(base_url)}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        from app.services.http_pool import TIMEOUT_SCENE, get_client

        started_at = time.perf_counter()
        log_provider_request("openai_compat", kind, url, payload.get("model"), input_chars=chat_message_input_chars(payload.get("messages")), **log_kwargs)
        client = get_client(base_url, TIMEOUT_SCENE)
        response = await client.post(url, headers=headers, json=payload, timeout=TIMEOUT_SCENE)
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        log_provider_response("openai_compat", kind, response.status_code, elapsed_ms, len(response.text), model=payload.get("model"))
        if response.status_code >= 400:
            raise RuntimeError(format_provider_error("OpenAI-compatible", response))
        try:
            body = response.json()
        except ValueError as error:
            log_provider_parse_error("openai_compat", kind, payload.get("model"), "response_not_json", response_chars=len(response.text))
            raise RuntimeError("OpenAI-compatible response không phải JSON hợp lệ.") from error
        content = extract_chat_response_content(body)
        if not content.strip():
            shape = chat_response_shape(body)
            log_provider_parse_error("openai_compat", kind, payload.get("model"), {"empty_content_or_unknown_shape": shape}, response_chars=len(response.text))
            raise RuntimeError(f"OpenAI-compatible response không có nội dung assistant đọc được. shape={shape}")
        log_provider_parse("openai_compat", kind, payload.get("model"), len(content))
        return content


def _log_openai_compat_parse_error(kind: str, model: Any, message: Any, response_chars: int | None = None) -> None:
    """Log parse diagnostics without letting observability break fallback flow."""
    try:
        from app.services.provider_logging import log_provider_parse_error

        log_provider_parse_error("openai_compat", kind, model, message, response_chars=response_chars)
    except Exception as error:  # pragma: no cover - defensive logging guard
        logging.getLogger("app.services.ai_providers").warning(
            "AI provider parse error logging failed provider=openai_compat kind=%s model=%s error=%s",
            kind,
            model or "<unknown>",
            str(error) or error.__class__.__name__,
            extra={"provider": "openai_compat", "kind": kind, "model": model},
        )


def _normalize_openai_compat_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base.removesuffix("/chat/completions")
    if base.endswith("/completions"):
        return base.removesuffix("/completions")
    if not base.endswith("/v1"):
        return f"{base}/v1"
    return base


def _requires_api_key(base_url: str) -> bool:
    """Heuristic: remote (non-localhost) OpenAI-compatible endpoints typically
    require an API key.  Local servers (localhost / 127.0.0.1) are assumed open.
    """
    import re
    host = re.sub(r"^https?://", "", base_url).split("/")[0].split(":")[0].lower()
    return host not in {"localhost", "127.0.0.1", "0.0.0.0", ""}
