import json
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.scene import AiModelInfo
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt
from app.services.openrouter_client import OCR_SYSTEM_PROMPT


class Router9Client:
    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self.settings = settings
        self.model = model or settings.router9_text_model

    async def list_models(self) -> list[AiModelInfo]:
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")

        headers = _build_headers(self.settings)
        url = f"{self.settings.router9_base_url.rstrip('/')}/models"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers)
                if response.status_code >= 400:
                    raise RuntimeError(_format_router9_error(response))
        except httpx.HTTPError as error:
            message = str(error) or error.__class__.__name__
            raise RuntimeError(f"9router models request lỗi: {message}") from error

        try:
            data = response.json()["data"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("9router response không đúng định dạng data[].") from error

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
        return sorted(models, key=lambda model: model.id.lower())

    async def extract_scene_json(self, problem_text: str, grade: int | None = None, reasoning_layer: str = "off") -> dict:
        if not self.settings.router9_api_key:
            raise RuntimeError("ROUTER9_API_KEY chưa được cấu hình.")
        if not self.model:
            raise RuntimeError("Chưa chọn model 9router.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer)},
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
            print(f"[AI API][9router][scene][parsed] {json.dumps(scene_json, ensure_ascii=False)[:2000]}")
            return scene_json
        except json.JSONDecodeError as error:
            raise RuntimeError(f"9router trả về JSON không hợp lệ: {error.msg}") from error

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
        print(f"[AI API][9router][ocr][result] {text[:1000]}")
        return text

    async def _post_chat(self, payload: dict) -> httpx.Response:
        headers = _build_headers(self.settings)
        url = f"{self.settings.router9_base_url.rstrip('/')}/chat/completions"
        try:
            started_at = time.perf_counter()
            kind = "ocr" if any(isinstance(message.get("content"), list) for message in payload.get("messages", []) if isinstance(message, dict)) else "scene"
            input_chars = sum(len(message.get("content", "")) for message in payload.get("messages", []) if isinstance(message, dict) and isinstance(message.get("content"), str))
            print(f"[AI API][9router][{kind}] POST {url} model={payload.get('model')} input_chars={input_chars}")
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                print(f"[AI API][9router][{kind}] HTTP {response.status_code} elapsed_ms={elapsed_ms} response_chars={len(response.text)}")
                if response.status_code >= 400:
                    print(f"[AI API][9router][{kind}][error] {_format_router9_error(response)}")
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
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text[:500]
    return f"9router HTTP {response.status_code}: {body}"
