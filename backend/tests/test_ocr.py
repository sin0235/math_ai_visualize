import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.services.ocr import validate_image_data_url
from app.services.openrouter_client import OpenRouterClient

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    db = SQLiteClient(str(tmp_path / "ocr.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path)

    async def override_db():
        return db

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield db
    finally:
        app.dependency_overrides.clear()


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


def test_ocr_prefers_router9_codex_when_connected(monkeypatch):
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        assert image_data_url == _IMAGE_DATA_URL
        return "Đề từ Codex 5.5."

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        return "Không nên gọi OpenRouter."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "runtime_settings": {"router9": {"api_key": "router9-secret"}, "openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ Codex 5.5."
    assert response.json()["model"] == "codex-5.5-image"
    assert response.json()["provider"] == "router9"
    assert calls == [("router9", "codex-5.5-image")]


def test_ocr_falls_back_to_nvidia_when_openrouter_fails(monkeypatch):
    calls = []

    async def fail_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        raise RuntimeError("rate limited")

    async def fake_nvidia(self, image_data_url: str, model: str | None = None):
        calls.append(("nvidia", model))
        return "Đề từ NVIDIA."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fail_openrouter)
    monkeypatch.setattr("app.services.nvidia_client.NvidiaClient.ocr_image", fake_nvidia)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "runtime_settings": {"openrouter": {"api_key": "secret"}, "nvidia": {"api_key": "nv-secret"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ NVIDIA."
    assert response.json()["model"] == "nvidia:google/gemma-3n-e2b-it"
    assert "OpenRouter" in response.json()["warnings"][0] or "openrouter" in response.json()["warnings"][0]
    assert calls == [
        ("openrouter", "google/gemma-4-31b-it:free"),
        ("openrouter", "google/gemma-4-26b-a4b-it:free"),
        ("nvidia", "google/gemma-3n-e2b-it"),
    ]


def test_ocr_router9_tries_image_models_then_github_gpt52(monkeypatch):
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        if model != "gh/gpt-5.2":
            raise RuntimeError("model unavailable")
        return "Đề từ GPT 5.2."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "runtime_settings": {
                "router9": {
                    "api_key": "router9-secret",
                    "allowed_model_ids": ["cc/codex-5.5-image", "cc/codex-5.4-image", "gh/gpt-5.2"],
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ GPT 5.2."
    assert response.json()["model"] == "gh/gpt-5.2"
    assert calls == [
        ("router9", "cc/codex-5.5-image"),
        ("router9", "cc/codex-5.4-image"),
        ("router9", "gh/gpt-5.2"),
    ]


def test_ocr_router9_falls_back_to_openrouter_when_not_only(monkeypatch):
    calls = []

    async def fail_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        raise RuntimeError("gateway down")

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        return "Đề từ OpenRouter."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fail_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "router9",
            "runtime_settings": {"router9": {"api_key": "router9-secret"}, "openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ OpenRouter."
    assert response.json()["provider"] == "openrouter"
    assert response.json()["model"] == "google/gemma-4-31b-it:free"
    assert "router9/codex-5.5-image" in response.json()["warnings"][0]
    assert calls == [
        ("router9", "codex-5.5-image"),
        ("router9", "codex-5.4-image"),
        ("router9", "github/gpt-5.2"),
        ("openrouter", "google/gemma-4-31b-it:free"),
    ]


def test_ocr_router9_only_rejects_openrouter_provider():
    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "runtime_settings": {"router9": {"only_mode": True}},
        },
    )

    assert response.status_code == 400
    assert "9router-only" in response.json()["detail"]


def test_ocr_openrouter_fallback_reports_actual_model(monkeypatch):
    calls = []

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(model)
        if model == "google/gemma-4-31b-it:free":
            raise RuntimeError("rate limited")
        return "Đề từ fallback."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "runtime_settings": {"openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "google/gemma-4-26b-a4b-it:free"
    assert "google/gemma-4-31b-it:free" in response.json()["warnings"][0]
    assert calls == ["google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"]


def test_ocr_explicit_model_does_not_try_fallback_model(monkeypatch):
    calls = []

    async def fail_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(model)
        raise RuntimeError("bad model")

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fail_openrouter)

    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "ocr_model": "vision/model",
            "runtime_settings": {"openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 400
    assert "vision/model" in response.json()["detail"]
    assert calls == ["vision/model"]


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
