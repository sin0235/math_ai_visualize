from app.core.config import Settings
from app.services.ocr_pipeline import local_pipeline
from app.services.ocr_pipeline.postprocess import merge_formula_text, merge_text_lines, normalize_math_text, order_text_lines
from app.services.ocr_pipeline.types import OcrTextLine


def test_order_text_lines_by_bbox():
    lines = [
        OcrTextLine("B. $(0,1)$", 0.9, (10, 80, 100, 100)),
        OcrTextLine("Câu 1. Cho hàm số", 0.95, (10, 10, 200, 30)),
        OcrTextLine("A. $(1,0)$", 0.9, (10, 50, 100, 70)),
    ]

    assert [line.text for line in order_text_lines(lines)] == ["Câu 1. Cho hàm số", "A. $(1,0)$", "B. $(0,1)$"]
    assert merge_text_lines(lines).splitlines()[0] == "Câu 1. Cho hàm số"


def test_normalize_math_text_replaces_common_symbols():
    text = normalize_math_text("x² ≥ 0 và AB ⊥ CD")

    assert "x^2" in text
    assert "\\ge" in text
    assert "\\perp" in text


def test_merge_formula_text_appends_latex_block():
    merged = merge_formula_text("Giải phương trình", r"x^2+1=0")

    assert merged == "Giải phương trình\n\n$$x^2+1=0$$"


def test_local_pipeline_preserves_raw_blocks_and_formula_candidates(monkeypatch):
    lines = [OcrTextLine("x² + 1 = 0", 0.86, (1, 2, 90, 20))]
    monkeypatch.setattr(local_pipeline, "load_pil_image", lambda _source: object())
    monkeypatch.setattr(local_pipeline, "preprocess_for_ocr", lambda image: image)
    monkeypatch.setattr(local_pipeline, "extract_text_lines", lambda _image, lang: lines)
    monkeypatch.setattr(local_pipeline, "extract_formula_latex", lambda _image: "x^2+1=0")

    result = local_pipeline.run_local_ocr_sync(
        "data:image/png;base64,aGVsbG8=",
        "problem",
        Settings(_env_file=None, local_ocr_use_pix2tex=True),
    )

    assert result.raw_text == "x² + 1 = 0"
    assert result.normalized_text == "x^2 + 1 = 0"
    assert result.lines == lines
    assert result.formula_candidates[0].latex == "x^2+1=0"
    assert result.text.endswith("$$x^2+1=0$$")
