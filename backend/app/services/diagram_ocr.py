"""OCR hình vẽ tay/in → văn bản mô tả hình học (đầu vào cho extract_scene).

Khác với ``ocr.py`` (OCR đề bài thuần), service này dùng vision model với prompt
riêng để chuyển đổi *hình vẽ* thành mô tả hình học có cấu trúc:

    - Liệt kê các điểm và mối quan hệ (vuông góc, song song, trung điểm, v.v.).
    - Đoán độ dài/góc khi có ký hiệu.
    - Bỏ qua các ghi chú thừa, không giải bài.

Đầu ra là một đoạn văn tiếng Việt mô tả hình. Pipeline render sau đó dùng đoạn
văn này như đề bài để tái dựng MathScene qua ``extract_scene``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.services.ai_fallback import Attempt, format_attempts, openrouter_vision_candidates, router9_ocr_candidates
from app.services.ocr import validate_image_data_url
from app.services.openrouter_client import _build_headers, _extract_message, _format_openrouter_error, _normalize_model_id, _strip_text_fences
from app.services.provider_logging import log_provider_request, log_provider_response
from app.services.router9_client import Router9Client

DIAGRAM_OCR_SYSTEM_PROMPT = """
Bạn là trợ lý nhận diện hình hình học từ ảnh (vẽ tay hoặc in).
Hãy đọc kỹ hình và xuất ra MỘT đoạn văn tiếng Việt mô tả đầy đủ:
1. Loại hình (tam giác, tứ giác, hình chóp, lăng trụ, hình tròn, đồ thị, hệ trục…).
2. Tên và quan hệ vị trí của các điểm (đỉnh, trung điểm, chân đường cao, hình chiếu…).
3. Quan hệ đặc biệt nhìn thấy được: vuông góc, song song, bằng nhau (dấu gạch),
   góc đặc biệt (90°, 60°…), điểm chia đoạn theo tỉ lệ.
4. Số đo nếu có ghi trên hình (cạnh, góc, bán kính); nếu không ghi thì bỏ qua,
   KHÔNG được tự bịa số liệu.
5. Câu hỏi/yêu cầu nếu được viết trong hình (ví dụ "Tính thể tích…"); nếu không
   có thì kết thúc mô tả ở phần dữ kiện.
Yêu cầu định dạng:
- Một đoạn văn liên tục (không bullet, không markdown), dùng giọng văn đề toán
  Việt Nam ("Cho hình chóp S.ABCD …").
- Không suy luận, không giải bài, không thêm nhận xét cá nhân.
- Nếu không nhận diện được hình hình học rõ ràng, trả về duy nhất chuỗi
  "KHÔNG_NHẬN_DIỆN_ĐƯỢC".
""".strip()


@dataclass(frozen=True)
class DiagramOcrResult:
    description: str
    provider: str
    model: str


async def describe_diagram(
    image_data_url: str,
    settings: Settings,
    explicit_model: str | None = None,
) -> DiagramOcrResult:
    validate_image_data_url(image_data_url)
    attempts: list[Attempt] = []

    if settings.openrouter_api_key:
        for model in openrouter_vision_candidates(settings, explicit_model):
            try:
                description = await _call_openrouter_vision(image_data_url, settings, model)
                return DiagramOcrResult(description=description, provider="openrouter", model=model)
            except RuntimeError as error:
                attempts.append(Attempt("openrouter", model, "diagram_ocr", str(error)))

    if explicit_model is None and settings.router9_api_key:
        for model in router9_ocr_candidates(settings):
            try:
                client = Router9Client(settings, model=model)
                description = await client.ocr_image(image_data_url, model, system_prompt=DIAGRAM_OCR_SYSTEM_PROMPT, user_text="Hãy mô tả hình hình học trong ảnh thành một đoạn văn đề bài tiếng Việt.")
                return DiagramOcrResult(description=description, provider="router9", model=model)
            except RuntimeError as error:
                attempts.append(Attempt("router9", model, "diagram_ocr", str(error)))

    raise RuntimeError("OCR hình thất bại qua tất cả model. Đã thử: " + format_attempts(attempts))


async def _call_openrouter_vision(image_data_url: str, settings: Settings, model: str) -> str:
    payload = {
        "model": _normalize_model_id(model),
        "messages": [
            {"role": "system", "content": DIAGRAM_OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hãy mô tả hình hình học trong ảnh thành một đoạn văn đề bài tiếng Việt."},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        "temperature": 0,
    }
    from app.services.http_pool import TIMEOUT_OCR, get_client

    base_url = settings.openrouter_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    started_at = time.perf_counter()
    log_provider_request("openrouter", "diagram_ocr", url, payload["model"], image_chars=len(image_data_url))
    client = get_client(base_url, TIMEOUT_OCR)
    response = await client.post(url, headers=_build_headers(settings), json=payload, timeout=TIMEOUT_OCR)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    log_provider_response("openrouter", "diagram_ocr", response.status_code, elapsed_ms, len(response.text))
    if response.status_code >= 400:
        raise RuntimeError(_format_openrouter_error(response))

    message = _extract_message(response)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Vision model không trả về nội dung mô tả.")
    text = _strip_text_fences(content).strip()
    if text == "KHÔNG_NHẬN_DIỆN_ĐƯỢC":
        raise RuntimeError("Vision model không nhận diện được hình hình học trong ảnh.")
    if len(text) < 20:
        raise RuntimeError("Mô tả hình quá ngắn, có thể không phải hình hình học.")
    return text


__all__ = ["DiagramOcrResult", "describe_diagram", "DIAGRAM_OCR_SYSTEM_PROMPT"]
