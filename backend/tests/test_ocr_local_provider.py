import pytest

from app.core.config import Settings
from app.services.ocr import extract_text_from_image
from app.services.ocr_pipeline.types import LocalOcrResult, OcrFormulaCandidate, OcrTextLine

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="


@pytest.mark.anyio
async def test_local_ocr_provider_returns_local_result(monkeypatch):
    async def fake_local(*args, **kwargs):
        return LocalOcrResult(
            text="Cho hàm số $$x^2+1$$",
            model="paddleocr+pix2tex",
            confidence=0.92,
            raw_text="Cho hàm số x²+1",
            normalized_text="Cho hàm số x^2+1",
            lines=[OcrTextLine("Cho hàm số x²+1", 0.92, (10, 20, 200, 50))],
            formula_candidates=[OcrFormulaCandidate("x^2+1")],
        )

    monkeypatch.setattr("app.services.ocr._run_local_ocr", fake_local)

    result = await extract_text_from_image(_IMAGE_DATA_URL, Settings(_env_file=None), provider="local")

    assert result.provider == "local"
    assert result.model == "paddleocr+pix2tex"
    assert "x^2" in result.text
    assert result.raw_text == "Cho hàm số x²+1"
    assert result.normalized_text == "Cho hàm số x^2+1"
    assert result.lines == [OcrTextLine("Cho hàm số x²+1", 0.92, (10, 20, 200, 50))]
    assert result.formula_candidates == [OcrFormulaCandidate("x^2+1")]


@pytest.mark.anyio
async def test_local_ocr_low_confidence_falls_back_to_openrouter(monkeypatch):
    async def low_confidence_local(*args, **kwargs):
        return LocalOcrResult(text="mờ", model="paddleocr+pix2tex", confidence=0.1)

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        return "Đề từ fallback."

    monkeypatch.setattr("app.services.ocr._run_local_ocr", low_confidence_local)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    result = await extract_text_from_image(
        _IMAGE_DATA_URL,
        Settings(_env_file=None, openrouter_api_key="secret"),
    )

    assert result.provider == "openrouter"
    assert result.text == "Đề từ fallback."
    assert any("local" in warning for warning in result.warnings)


@pytest.mark.anyio
async def test_explicit_remote_provider_does_not_try_local(monkeypatch):
    called = False

    async def fake_local(*args, **kwargs):
        nonlocal called
        called = True
        return LocalOcrResult(text="Không nên gọi local", model="paddleocr+pix2tex", confidence=0.99)

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        return "Đề từ OpenRouter."

    monkeypatch.setattr("app.services.ocr._run_local_ocr", fake_local)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    result = await extract_text_from_image(
        _IMAGE_DATA_URL,
        Settings(_env_file=None, openrouter_api_key="secret"),
        provider="openrouter",
    )

    assert result.provider == "openrouter"
    assert called is False


@pytest.mark.anyio
async def test_explicit_local_without_fallback_raises(monkeypatch):
    async def low_confidence_local(*args, **kwargs):
        return LocalOcrResult(text="mờ", model="paddleocr+pix2tex", confidence=0.1)

    monkeypatch.setattr("app.services.ocr._run_local_ocr", low_confidence_local)

    with pytest.raises(RuntimeError) as error:
        await extract_text_from_image(
            _IMAGE_DATA_URL,
            Settings(_env_file=None, local_ocr_fallback_to_llm=False),
            provider="local",
        )

    assert "Local OCR" in str(error.value)
