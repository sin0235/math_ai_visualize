from __future__ import annotations

from app.core.config import Settings
from app.schemas.scene import OcrMode
from app.services.ocr_pipeline.image import load_pil_image
from app.services.ocr_pipeline.paddle_engine import extract_text_lines
from app.services.ocr_pipeline.pix2tex_engine import extract_formula_latex
from app.services.ocr_pipeline.postprocess import merge_formula_text, merge_text_lines, normalize_math_text
from app.services.ocr_pipeline.preprocess import preprocess_for_ocr
from app.services.ocr_pipeline.types import LocalOcrResult, OcrFormulaCandidate


def run_local_ocr_sync(image_data_url: str, mode: OcrMode, settings: Settings) -> LocalOcrResult:
    image = load_pil_image(image_data_url)
    processed = preprocess_for_ocr(image)
    warnings: list[str] = []

    lines = extract_text_lines(processed, lang=settings.local_ocr_paddle_lang)
    raw_text = merge_text_lines(lines)
    normalized_text = normalize_math_text(raw_text)
    confidence = _mean_confidence([line.confidence for line in lines])

    latex = None
    used_formula_ocr = False
    if settings.local_ocr_use_pix2tex and _should_try_formula(normalized_text, confidence, mode):
        try:
            latex = extract_formula_latex(image)
            used_formula_ocr = bool(latex)
        except RuntimeError as error:
            warnings.append(str(error))
    formula_candidates = [OcrFormulaCandidate(latex=latex)] if latex else []
    text = merge_formula_text(normalized_text, latex)
    if not text.strip():
        raise RuntimeError("Local OCR không trích xuất được văn bản từ ảnh.")

    if mode == "diagram" and confidence < max(settings.local_ocr_min_confidence, 0.75):
        warnings.append("Local OCR chỉ đọc được nhãn/chữ trong hình, chưa đủ tự tin để mô tả quan hệ hình học.")

    formula_bonus = 0.1 if used_formula_ocr else 0.0
    return LocalOcrResult(
        text=text,
        model=settings.local_ocr_model_name,
        confidence=min(1.0, confidence + formula_bonus),
        warnings=warnings,
        used_formula_ocr=used_formula_ocr,
        raw_text=raw_text,
        normalized_text=normalized_text,
        lines=lines,
        formula_candidates=formula_candidates,
    )


def _mean_confidence(values: list[float]) -> float:
    cleaned = [value for value in values if 0 <= value <= 1]
    if not cleaned:
        return 0.0
    return sum(cleaned) / len(cleaned)


def _should_try_formula(text: str, confidence: float, mode: OcrMode) -> bool:
    if mode == "diagram":
        return True
    markers = ("=", "^", "sqrt", "\\", "frac", "lim", "int", "∫", "√")
    return confidence < 0.82 or any(marker in text for marker in markers)
