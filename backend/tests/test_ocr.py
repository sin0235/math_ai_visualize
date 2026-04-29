import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.ocr import validate_image_data_url
from app.services.openrouter_client import OpenRouterClient

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="


def test_validate_image_data_url_accepts_supported_images():
    validate_image_data_url(_IMAGE_DATA_URL)


def test_validate_image_data_url_rejects_non_images():
    try:
        validate_image_data_url("data:text/plain;base64,aGVsbG8=")
    except ValueError as error:
        assert "data URL" in str(error)
    else:
        raise AssertionError("Expected non-image data URL to be rejected")


def test_ocr_route_returns_openrouter_text(monkeypatch):
    async def fake_ocr_image(self, image_data_url: str, model: str | None = None):
        assert image_data_url == _IMAGE_DATA_URL
        assert model == "vision/model"
        return "Cho tam giác ABC."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_ocr_image)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "ocr_model": "vision/model",
            "runtime_settings": {"openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Cho tam giác ABC."
    assert response.json()["model"] == "vision/model"
    assert response.json()["provider"] == "openrouter"


def test_openrouter_ocr_payload_uses_vision_message(monkeypatch):
    payloads = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict):
            payloads.append((url, headers, json))
            return httpx.Response(200, json={"choices": [{"message": {"content": "Cho A(0,0)."}}]})

    monkeypatch.setattr("app.services.openrouter_client.httpx.AsyncClient", FakeAsyncClient)

    text = __import__("asyncio").run(
        OpenRouterClient(Settings(openrouter_api_key="secret")).ocr_image(_IMAGE_DATA_URL, "openrouter/vision-model")
    )

    assert text == "Cho A(0,0)."
    assert payloads[0][0] == "https://openrouter.ai/api/v1/chat/completions"
    assert payloads[0][1]["Authorization"] == "Bearer secret"
    assert payloads[0][2]["model"] == "vision-model"
    assert payloads[0][2]["messages"][1]["content"][1]["image_url"]["url"] == _IMAGE_DATA_URL
