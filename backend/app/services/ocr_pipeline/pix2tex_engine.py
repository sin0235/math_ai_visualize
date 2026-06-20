from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _latex_ocr_model():
    try:
        from pix2tex.cli import LatexOCR
    except ImportError as error:
        raise RuntimeError("Thiếu dependency pix2tex để chạy OCR công thức LaTeX.") from error
    return LatexOCR()


def extract_formula_latex(image) -> str | None:
    model = _latex_ocr_model()
    try:
        latex = str(model(image)).strip()
    except Exception as error:
        raise RuntimeError(f"pix2tex không đọc được công thức: {error}") from error
    if not _looks_like_latex(latex):
        return None
    return latex


def _looks_like_latex(value: str) -> bool:
    if not value or len(value) < 2 or len(value) > 2000:
        return False
    if value.count("{") != value.count("}"):
        return False
    math_markers = ("\\", "^", "_", "=", "+", "-", "\\frac", "\\sqrt", "\\int", "\\sum")
    return any(marker in value for marker in math_markers)
