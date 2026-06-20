from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.ocr_pipeline.types import OcrTextLine


@lru_cache(maxsize=4)
def _paddle_ocr(lang: str):
    try:
        from paddleocr import PaddleOCR
    except ImportError as error:
        raise RuntimeError("Thiếu dependency paddleocr để chạy local OCR.") from error
    return PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)


def extract_text_lines(image, *, lang: str) -> list[OcrTextLine]:
    ocr = _paddle_ocr(lang)
    result = ocr.ocr(image, cls=True)
    lines: list[OcrTextLine] = []
    for page in result or []:
        for item in page or []:
            parsed = _parse_item(item)
            if parsed is not None:
                lines.append(parsed)
    return lines


def _parse_item(item: Any) -> OcrTextLine | None:
    try:
        box = item[0]
        text, confidence = item[1]
        xs = [int(point[0]) for point in box]
        ys = [int(point[1]) for point in box]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        text = str(text).strip()
        if not text:
            return None
        return OcrTextLine(text=text, confidence=float(confidence), bbox=bbox)
    except Exception:
        return None
