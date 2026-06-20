from __future__ import annotations

import re

from app.services.ocr_pipeline.types import OcrTextLine


_MATH_SYMBOL_REPLACEMENTS = {
    "≤": r"\\le ",
    "≥": r"\\ge ",
    "≠": r"\\ne ",
    "∞": r"\\infty ",
    "√": r"\\sqrt",
    "∠": r"\\angle ",
    "⊥": r"\\perp ",
    "∥": r"\\parallel ",
}


def order_text_lines(lines: list[OcrTextLine]) -> list[OcrTextLine]:
    def key(line: OcrTextLine):
        if line.bbox is None:
            return (0, 0)
        left, top, _right, _bottom = line.bbox
        return (top, left)
    return sorted(lines, key=key)


def merge_text_lines(lines: list[OcrTextLine]) -> str:
    ordered = order_text_lines(lines)
    return "\n".join(line.text.strip() for line in ordered if line.text.strip())


def normalize_math_text(text: str) -> str:
    cleaned = text.replace("−", "-").replace("–", "-").replace("—", "-")
    for source, target in _MATH_SYMBOL_REPLACEMENTS.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r"(?<=\b[a-zA-Z])\s*\^\s*(\d+)", r"^\1", cleaned)
    cleaned = re.sub(r"\b([xy])\s*([²³])", lambda m: f"{m.group(1)}^{_superscript_digit(m.group(2))}", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def merge_formula_text(text: str, latex: str | None) -> str:
    if not latex:
        return text.strip()
    latex = latex.strip()
    if not latex:
        return text.strip()
    if latex in text:
        return text.strip()
    if text.strip():
        return f"{text.strip()}\n\n$${latex}$$"
    return f"$${latex}$$"


def _superscript_digit(value: str) -> str:
    return {"²": "2", "³": "3"}.get(value, value)
