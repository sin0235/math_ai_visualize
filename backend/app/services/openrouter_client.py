import json

import httpx

from app.core.config import Settings
from app.services.ai_prompt import SCENE_EXTRACTION_SYSTEM_PROMPT, build_scene_extraction_prompt


OCR_SYSTEM_PROMPT = """
Bạn là bộ OCR đề toán tiếng Việt.
Chỉ trích xuất nội dung đề bài trong ảnh thành văn bản thuần.
Giữ nguyên ký hiệu toán, tên điểm, tọa độ, phân số, căn, mũ và xuống dòng khi có ý nghĩa.
Không giải bài, không thêm nhận xét, không markdown, không bọc code fence.
Nếu có công thức khó biểu diễn bằng Unicode, dùng LaTeX ngắn gọn trong text.
""".strip()


class OpenRouterClient:
    def __init__(self, settings: Settings, model: str | None = None, reasoning_enabled: bool | None = None) -> None:
        self.settings = settings
        self.model = model or settings.openrouter_text_model
        self.reasoning_enabled = settings.openrouter_reasoning_enabled if reasoning_enabled is None else reasoning_enabled

    async def extract_scene_json(self, problem_text: str, grade: int | None = None, reasoning_layer: str = "off") -> dict:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY chưa được cấu hình.")

        headers = _build_headers(self.settings)
        payload = {
            "model": _normalize_model_id(self.model),
            "messages": [
                {"role": "system", "content": SCENE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_scene_extraction_prompt(problem_text, grade, reasoning_layer)},
            ],
            "temperature": 0.1,
        }
        if self.reasoning_enabled:
            payload["reasoning"] = {"enabled": True}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
            if response.status_code >= 400:
                raise RuntimeError(_format_openrouter_error(response))

        message = _extract_message(response)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenRouter không trả về nội dung JSON trong choices[0].message.content.")
        try:
            return json.loads(_strip_json_fences(content))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"OpenRouter trả về JSON không hợp lệ: {error.msg}") from error

    async def ocr_image(self, image_data_url: str, model: str | None = None) -> str:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY chưa được cấu hình.")

        models = [model or self.settings.openrouter_vision_model]
        if model is None and self.settings.openrouter_vision_fallback_model not in models:
            models.append(self.settings.openrouter_vision_fallback_model)

        errors: list[str] = []
        for selected_model in models:
            payload = {
                "model": _normalize_model_id(selected_model),
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
                "reasoning": {"enabled": True},
            }

            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=_build_headers(self.settings), json=payload)
                    if response.status_code >= 400:
                        raise RuntimeError(_format_openrouter_error(response))

                message = _extract_message(response)
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("OpenRouter không trả về nội dung OCR trong choices[0].message.content.")
                return _strip_text_fences(content)
            except RuntimeError as error:
                errors.append(f"{selected_model}: {error}")

        raise RuntimeError("OCR OpenRouter thất bại qua tất cả model: " + " | ".join(errors))


def _build_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_x_title:
        headers["X-Title"] = settings.openrouter_x_title
    return headers


def _normalize_model_id(model: str) -> str:
    return model.removeprefix("openrouter/")


def _extract_message(response: httpx.Response) -> dict:
    try:
        body = response.json()
        return body["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("OpenRouter response không đúng định dạng choices[0].message.") from error


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


def _format_openrouter_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text[:500]
    return f"OpenRouter HTTP {response.status_code}: {body}"
