import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.api.deps import require_active_user
from app.db.models import UserRecord
from app.db.session import SQLiteClient, get_database
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository
from app.main import app
from app.services.ocr import OcrResult, _ocr_models_for_provider
from app.services.model_provider import resolve_ocr_provider
from app.services.ocr import extract_text_from_image, validate_image_data_url
from app.services.openrouter_client import OpenRouterClient

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02\x00\x00\x00\x0bIDATx\xdac\xfc\xff\x1f\x00\x03\x03\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    db = SQLiteClient(str(tmp_path / "ocr.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path)
    user = asyncio.run(UserRepository(db).create("ocr@example.com", "StrongPass123"))

    async def override_db():
        return db

    async def override_user():
        return UserRecord(**{**user.__dict__, "role": "admin"})

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[require_active_user] = override_user
    try:
        yield db
    finally:
        app.dependency_overrides.clear()


def _override_ocr_settings(monkeypatch, settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)

def test_validate_image_data_url_accepts_supported_images():
    validate_image_data_url(_IMAGE_DATA_URL)


def test_validate_image_data_url_rejects_non_images():
    try:
        validate_image_data_url("data:text/plain;base64,aGVsbG8=")
    except ValueError as error:
        assert "data URL" in str(error)
    else:
        raise AssertionError("Expected non-image data URL to be rejected")


def test_resolve_ocr_provider_does_not_infer_from_vendor_namespaces():
    for model in [
        "gh/gpt-5.2",
        "cc/codex-5.5-image",
        "cx/gpt-5.2",
        "oc/nemotron-3-super-free",
        "kr/claude-sonnet-4.5",
        "cf/@cf/meta/llama-3.2-1b-instruct",
        "claude-ds/deepseek-v4-vision",
        "openAI-ds/deepseek-v4-vision",
        "kc/anthropic/claude-sonnet-4-20250514",
    ]:
        assert resolve_ocr_provider(None, model) == "openrouter"
    assert resolve_ocr_provider("router9", "gh/gpt-5.2") == "router9"


def test_router9_ocr_fallbacks_keep_slash_models_and_ignore_explicit_other_provider():
    assert _ocr_models_for_provider("router9", None, [
        "nvidia/deepseek-ai/deepseek-v4-flash",
        "ollama/qwen3",
        "openrouter/google/gemma",
        "ollama::qwen3",
    ]) == [
        "nvidia/deepseek-ai/deepseek-v4-flash",
        "ollama/qwen3",
        "openrouter/google/gemma",
    ]


def test_resolve_ocr_provider_supports_all_admin_providers():
    assert resolve_ocr_provider("nvidia", None) == "nvidia"
    assert resolve_ocr_provider("ollama", None) == "ollama"
    assert resolve_ocr_provider("openai_compat", None) == "openai_compat"
    assert resolve_ocr_provider(None, "nvidia/model") == "openrouter"
    assert resolve_ocr_provider(None, "ollama/llava") == "ollama"
    assert resolve_ocr_provider(None, "openai_compat/vision") == "openai_compat"


def test_ocr_upload_endpoint_returns_file_metadata_without_data_url(monkeypatch, isolated_database):
    async def fake_extract_text_from_image(*args, **kwargs):
        raise AssertionError("Upload endpoint must not run OCR directly")

    monkeypatch.setattr("app.services.ocr.extract_text_from_image", fake_extract_text_from_image)

    response = TestClient(app).post(
        "/api/ocr/uploads",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"]
    assert data["filename"] == "problem.png"
    assert data["content_type"] == "image/png"
    assert data["size"] == len(PNG_BYTES)
    assert data["storage_provider"] == "database"
    assert "data_url" not in data



def test_ocr_route_accepts_upload_id(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    captured = []

    async def fake_extract_text_from_image(image_data_url, settings, provider=None, model=None, mode="problem", fallback_models=None):
        captured.append(image_data_url)
        return OcrResult(text="Cho tam giác ABC.", provider="openrouter", model="vision/model", warnings=[])

    async def seed_upload():
        user_row = await isolated_database.fetch_one("SELECT * FROM users WHERE email = ?", ["ocr@example.com"])
        assert user_row is not None
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["upload-owned", user_row["id"], "problem.png", "image/png", 5, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "aGVsbG8="],
        )

    asyncio.run(seed_upload())
    monkeypatch.setattr("app.api.routes_ocr.extract_text_from_image", fake_extract_text_from_image)

    response = TestClient(app).post("/api/ocr", json={"upload_id": "upload-owned"})

    assert response.status_code == 200
    assert response.json()["text"] == "Cho tam giác ABC."
    assert captured == [_IMAGE_DATA_URL]



def test_ocr_route_rejects_missing_or_duplicate_image_source():
    client = TestClient(app)

    missing = client.post("/api/ocr", json={})
    duplicate = client.post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL, "upload_id": "upload-owned"})

    assert missing.status_code == 422
    assert duplicate.status_code == 422



def test_get_ocr_upload_allows_owner_to_read_inline_image(isolated_database):
    async def seed_upload():
        user_row = await isolated_database.fetch_one("SELECT * FROM users WHERE email = ?", ["ocr@example.com"])
        assert user_row is not None
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["upload-inline", user_row["id"], "problem.png", "image/png", 5, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "aGVsbG8="],
        )

    asyncio.run(seed_upload())

    response = TestClient(app).get("/api/ocr/uploads/upload-inline")

    assert response.status_code == 200
    assert response.content == b"hello"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.headers["etag"] == '"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"'
    assert "inline" in response.headers["content-disposition"]



def test_get_ocr_upload_reads_external_only_r2_image(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )
    _override_ocr_settings(monkeypatch, settings)

    async def seed_upload():
        user_row = await isolated_database.fetch_one("SELECT * FROM users WHERE email = ?", ["ocr@example.com"])
        assert user_row is not None
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (
              id, user_id, filename, content_type, size, sha256, data_base64,
              storage_provider, storage_key, storage_bucket
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "upload-r2",
                user_row["id"],
                "problem.png",
                "image/png",
                5,
                "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                "",
                "r2",
                "uploads/ocr/problem.png",
                "bucket",
            ],
        )

    asyncio.run(seed_upload())
    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"hello")

    response = TestClient(app).get("/api/ocr/uploads/upload-r2")

    assert response.status_code == 200
    assert response.content == b"hello"



def test_get_ocr_upload_allows_admin_to_read_other_user_image(isolated_database):
    async def seed_upload():
        other = await UserRepository(isolated_database).create("other@example.com", "StrongPass123")
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["upload-other-readable", other.id, "problem.png", "image/png", 5, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "aGVsbG8="],
        )

    asyncio.run(seed_upload())

    response = TestClient(app).get("/api/ocr/uploads/upload-other-readable")

    assert response.status_code == 200
    assert response.content == b"hello"



def test_get_ocr_upload_rejects_other_non_admin_user(isolated_database):
    async def seed_upload_and_user():
        owner = await UserRepository(isolated_database).create("owner@example.com", "StrongPass123")
        viewer = await UserRepository(isolated_database).create("viewer@example.com", "StrongPass123")
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["upload-private", owner.id, "problem.png", "image/png", 5, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "aGVsbG8="],
        )
        return viewer

    viewer = asyncio.run(seed_upload_and_user())

    async def override_viewer():
        return viewer

    app.dependency_overrides[require_active_user] = override_viewer
    response = TestClient(app).get("/api/ocr/uploads/upload-private")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "OCR_FAILED"



def test_get_ocr_upload_returns_404_for_missing_upload():
    response = TestClient(app).get("/api/ocr/uploads/missing-upload")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "OCR_FAILED"



def test_get_ocr_upload_rejects_remote_checksum_mismatch(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )
    _override_ocr_settings(monkeypatch, settings)

    async def seed_upload():
        user_row = await isolated_database.fetch_one("SELECT * FROM users WHERE email = ?", ["ocr@example.com"])
        assert user_row is not None
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (
              id, user_id, filename, content_type, size, sha256, data_base64,
              storage_provider, storage_key, storage_bucket
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "upload-mismatch",
                user_row["id"],
                "problem.png",
                "image/png",
                5,
                "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                "",
                "r2",
                "uploads/ocr/problem.png",
                "bucket",
            ],
        )

    asyncio.run(seed_upload())
    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"HELLO")

    response = TestClient(app).get("/api/ocr/uploads/upload-mismatch")

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OCR_FAILED"



def test_ocr_route_rejects_upload_owned_by_other_user(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)

    async def fake_extract_text_from_image(*args, **kwargs):
        raise AssertionError("OCR must not run for another user's upload")

    async def seed_upload():
        other = await UserRepository(isolated_database).create("other@example.com", "StrongPass123")
        await isolated_database.execute(
            """
            INSERT INTO uploaded_files (id, user_id, filename, content_type, size, sha256, data_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ["upload-other", other.id, "problem.png", "image/png", 5, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "aGVsbG8="],
        )

    asyncio.run(seed_upload())
    monkeypatch.setattr("app.api.routes_ocr.extract_text_from_image", fake_extract_text_from_image)

    response = TestClient(app).post("/api/ocr", json={"upload_id": "upload-other"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "OCR_FAILED"



def test_ocr_route_returns_openrouter_text(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="secret",
        openrouter_vision_model="vision/model",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)

    async def fake_ocr_image(self, image_data_url: str, model: str | None = None):
        assert image_data_url == _IMAGE_DATA_URL
        assert model == "vision/model"
        return "Cho tam giác ABC."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_ocr_image)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["text"] == "Cho tam giác ABC."
    assert response.json()["model"] == "vision/model"
    assert response.json()["provider"] == "openrouter"


def test_ocr_route_rejects_client_provider_model_selection():
    response = TestClient(app).post(
        "/api/ocr",
        json={
            "image_data_url": _IMAGE_DATA_URL,
            "ocr_provider": "openrouter",
            "ocr_model": "vision/model",
            "runtime_settings": {"openrouter": {"api_key": "secret"}},
        },
    )

    assert response.status_code == 422


def test_ocr_prefers_router9_codex_when_connected(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        router9_api_key="router9-secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
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

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ Codex 5.5."
    assert response.json()["model"] == "codex-5.5-image"
    assert response.json()["provider"] == "router9"
    assert calls == [("router9", "codex-5.5-image")]


def test_ocr_falls_back_to_nvidia_when_openrouter_fails(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="secret",
        nvidia_api_key="nv-secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    calls = []

    async def fail_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        raise RuntimeError("rate limited")

    async def fake_nvidia(self, image_data_url: str, model: str | None = None):
        calls.append(("nvidia", model))
        return "Đề từ NVIDIA."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fail_openrouter)
    monkeypatch.setattr("app.services.nvidia_client.NvidiaClient.ocr_image", fake_nvidia)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ NVIDIA."
    assert response.json()["provider"] == "nvidia"
    assert response.json()["model"] == "qwen/qwen3-coder-480b-a35b-instruct"
    assert "OpenRouter" in response.json()["warnings"][0] or "openrouter" in response.json()["warnings"][0]
    assert calls == [
        ("openrouter", "google/gemma-4-31b-it:free"),
        ("openrouter", "google/gemma-4-26b-a4b-it:free"),
        ("nvidia", "qwen/qwen3-coder-480b-a35b-instruct"),
    ]


def test_ocr_uses_admin_ollama_profile(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_task_profile

    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        ollama_text_model="llava:latest",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_task_profile(isolated_database, "ocr", "ollama", "llava:latest", []))
    calls = []

    async def fake_ollama(self, image_data_url: str, model: str | None = None, system_prompt=None, user_text="Trích xuất nguyên văn đề toán trong ảnh."):
        calls.append(("ollama", model))
        return "Đề từ Ollama."

    monkeypatch.setattr("app.services.ollama_client.OllamaClient.ocr_image", fake_ollama)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    assert response.json()["model"] == "llava:latest"
    assert response.json()["text"] == "Đề từ Ollama."
    assert calls == [("ollama", "llava:latest")]


def test_ocr_uses_admin_openai_compat_profile(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_task_profile

    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openai_compat_api_key="secret",
        openai_compat_text_model="vision-model",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_task_profile(isolated_database, "ocr", "openai_compat", "vision-model", []))
    calls = []

    async def fake_openai_compat(self, image_data_url: str, model: str | None = None, system_prompt=None, user_text="Trích xuất nguyên văn đề toán trong ảnh."):
        calls.append(("openai_compat", model))
        return "Đề từ OpenAI-compatible."

    monkeypatch.setattr("app.services.openai_compat_client.OpenAICompatClient.ocr_image", fake_openai_compat)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["provider"] == "openai_compat"
    assert response.json()["model"] == "vision-model"
    assert response.json()["text"] == "Đề từ OpenAI-compatible."
    assert calls == [("openai_compat", "vision-model")]


def test_ocr_router9_allowlist_uses_single_selected_model(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        router9_api_key="router9-secret",
        router9_allowed_models=["cc/codex-5.5-image", "cc/codex-5.4-image", "gh/gpt-5.2"],
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        return "Đề từ Codex 5.5."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ Codex 5.5."
    assert response.json()["model"] == "cc/codex-5.5-image"
    assert calls == [("router9", "cc/codex-5.5-image")]


def test_ocr_router9_falls_back_to_openrouter_when_not_only(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        router9_api_key="router9-secret",
        openrouter_api_key="secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    calls = []

    async def fail_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        raise RuntimeError("gateway down")

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        return "Đề từ OpenRouter."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fail_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

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


def test_ocr_router9_only_auto_uses_router9(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        router9_api_key="router9-secret",
        router9_only=True,
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        return "Đề từ 9router-only."

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        return "Không nên gọi OpenRouter."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["provider"] == "router9"
    assert response.json()["text"] == "Đề từ 9router-only."
    assert calls == [("router9", "codex-5.5-image")]


def test_ocr_openrouter_fallback_reports_actual_model(monkeypatch, isolated_database):
    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="secret",
        local_ocr_enabled=False,
    )
    _override_ocr_settings(monkeypatch, settings)
    calls = []

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(model)
        if model == "google/gemma-4-31b-it:free":
            raise RuntimeError("rate limited")
        return "Đề từ fallback."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["model"] == "google/gemma-4-26b-a4b-it:free"
    assert "google/gemma-4-31b-it:free" in response.json()["warnings"][0]
    assert calls == ["google/gemma-4-31b-it:free", "google/gemma-4-26b-a4b-it:free"]

def test_ocr_enforces_daily_plan_limit(isolated_database, monkeypatch):
    async def fake_ocr_image(self, image_data_url: str, model: str | None = None):
        return "Đề từ OCR."

    async def seed_user_and_plan():
        user_row = await isolated_database.fetch_one("SELECT * FROM users WHERE email = ?", ["ocr@example.com"])
        assert user_row is not None
        await isolated_database.execute(
            "UPDATE plans SET daily_ocr_limit = ? WHERE id = ?",
            [1, "free"],
        )
        await isolated_database.execute(
            "INSERT INTO usage_events (id, user_id, event_type) VALUES (?, ?, ?)",
            ["used-ocr", user_row["id"], "ocr"],
        )
        return "unused-token"

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_ocr_image)
    token = asyncio.run(seed_user_and_plan())

    response = TestClient(app).post(
        "/api/ocr",
        cookies={SESSION_COOKIE_NAME: token},
        json={"image_data_url": _IMAGE_DATA_URL},
    )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "PLAN_QUOTA_EXCEEDED"
    assert "hạn mức OCR" in detail["debug_message"]
    assert detail["suggestions"]


def test_ocr_route_uses_env_openrouter_key_with_registry_ocr_profile(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_task_profile

    settings = Settings(_env_file=None, sqlite_path=isolated_database.path, openrouter_api_key="env-openrouter-key")
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_task_profile(isolated_database, "ocr", "openrouter", "openrouter/gh/gpt-5.2", []))
    payloads = []

    class FakeAsyncClient:
        is_closed = False

        async def post(self, url: str, headers: dict[str, str], json: dict, timeout=None):
            payloads.append((url, headers, json))
            return httpx.Response(200, json={"choices": [{"message": {"content": "Đề OCR."}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient())

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["model"] == "gh/gpt-5.2"
    assert payloads[0][1]["Authorization"] == "Bearer env-openrouter-key"
    assert payloads[0][2]["model"] == "gh/gpt-5.2"


def test_ocr_route_uses_provider_default_for_empty_registry_ocr_profile(monkeypatch, isolated_database):
    from app.services.model_registry import invalidate_model_registry_cache, load_model_registry, save_provider_config

    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="env-openrouter-key",
        openrouter_text_model="admin/text",
        openrouter_vision_model="env/vision",
        local_ocr_enabled=False,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_provider_config(isolated_database, "openrouter", "https://openrouter.ai/api/v1"))
    # Empty model is not allowed via save_task_profile; store provider-only profile directly.
    asyncio.run(
        isolated_database.execute(
            """
            INSERT INTO ai_task_profiles (task, provider_id, model_id, fallbacks_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(task) DO UPDATE SET
              provider_id = excluded.provider_id,
              model_id = excluded.model_id,
              fallbacks_json = excluded.fallbacks_json,
              updated_at = CURRENT_TIMESTAMP
            """,
            ["ocr", "openrouter", "", "[]"],
        )
    )
    invalidate_model_registry_cache()
    payloads = []

    class FakeAsyncClient:
        is_closed = False

        async def post(self, url: str, headers: dict[str, str], json: dict, timeout=None):
            payloads.append(json)
            return httpx.Response(200, json={"choices": [{"message": {"content": "Đề OCR."}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient())

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["model"] == "admin/text"
    assert payloads[0]["model"] == "admin/text"


def test_ocr_route_uses_profile_fallback_models(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_task_profile, set_allowed_models

    settings = Settings(
        _env_file=None,
        sqlite_path=isolated_database.path,
        openrouter_api_key="env-openrouter-key",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(set_allowed_models(isolated_database, "openrouter", ["primary/vision", "fallback/vision"]))
    asyncio.run(save_task_profile(isolated_database, "ocr", "openrouter", "primary/vision", ["fallback/vision"]))
    calls = []

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(model)
        if model == "primary/vision":
            raise RuntimeError("primary unavailable")
        return "Đề từ fallback."

    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["text"] == "Đề từ fallback."
    assert response.json()["model"] == "fallback/vision"
    assert calls == ["primary/vision", "fallback/vision"]


def test_ocr_route_uses_router9_for_router9_github_profile(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_task_profile

    settings = Settings(_env_file=None, sqlite_path=isolated_database.path, router9_api_key="router9-key")
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_task_profile(isolated_database, "ocr", "router9", "gh/gpt-5.2", []))
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append(("router9", model))
        return "Đề OCR."

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        calls.append(("openrouter", model))
        return "Không nên gọi OpenRouter."

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200
    assert response.json()["provider"] == "router9"
    assert response.json()["model"] == "gh/gpt-5.2"
    assert calls == [("router9", "gh/gpt-5.2")]


def test_ocr_route_uses_admin_stored_router9_key_and_profile(monkeypatch, isolated_database):
    from app.services.model_registry import load_model_registry, save_provider_config, save_task_profile, set_allowed_models

    settings = Settings(_env_file=None, sqlite_path=isolated_database.path, local_ocr_enabled=False)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_ocr.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    # Registry is the authority for OCR profile; legacy ai_settings still supplies the API key.
    admin_ai_settings = {
        "version": 1,
        "router9": {
            "api_key": "router9-secret",
            "base_url": "https://api.9router.com/v1",
            "allowed_model_ids": ["gh/gpt-5-mini"],
        },
        "ocr": {"provider": "router9", "model": "gh/gpt-5-mini", "max_image_mb": 5},
    }
    asyncio.run(
        isolated_database.execute(
            "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
            ["ai_settings", json.dumps(admin_ai_settings)],
        )
    )
    asyncio.run(load_model_registry(isolated_database, settings))
    asyncio.run(save_provider_config(isolated_database, "router9", "https://api.9router.com/v1", api_key_configured=True))
    asyncio.run(set_allowed_models(isolated_database, "router9", ["gh/gpt-5-mini"]))
    asyncio.run(save_task_profile(isolated_database, "ocr", "router9", "gh/gpt-5-mini", []))
    calls = []

    async def fake_router9(self, image_data_url: str, model: str | None = None):
        calls.append((self.settings.router9_api_key, model))
        return "Đề OCR từ 9router."

    async def fake_openrouter(self, image_data_url: str, model: str | None = None):
        raise AssertionError("Không nên fallback sang OpenRouter khi admin đã cấu hình OCR 9router.")

    monkeypatch.setattr("app.services.router9_client.Router9Client.ocr_image", fake_router9)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    response = TestClient(app).post("/api/ocr", json={"image_data_url": _IMAGE_DATA_URL})

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "router9"
    assert response.json()["model"] == "gh/gpt-5-mini"
    assert calls == [("router9-secret", "gh/gpt-5-mini")]


def test_ocr_profile_filters_cross_provider_fallback_models(monkeypatch):
    settings = Settings(
        _env_file=None,
        openai_compat_api_key="compat-secret",
        openai_compat_base_url="https://compat.example/v1",
        openai_compat_text_model="compat/default",
        openrouter_api_key="openrouter-secret",
        local_ocr_enabled=False,
    )
    calls = []

    async def fail_openai_compat(self, image_data_url: str, model: str | None = None, system_prompt=None, user_text="Trích xuất nguyên văn đề toán trong ảnh."):
        calls.append(("openai_compat", model))
        raise RuntimeError("compat unauthorized")

    async def fake_openrouter(self, image_data_url: str, model: str | None = None, system_prompt=None, user_text="Trích xuất nguyên văn đề toán trong ảnh."):
        calls.append(("openrouter", model))
        return "Đề từ OpenRouter."

    monkeypatch.setattr("app.services.openai_compat_client.OpenAICompatClient.ocr_image", fail_openai_compat)
    monkeypatch.setattr("app.services.openrouter_client.OpenRouterClient.ocr_image", fake_openrouter)

    result = asyncio.run(
        extract_text_from_image(
            _IMAGE_DATA_URL,
            settings,
            provider="openai_compat",
            model="compat/primary",
            fallback_models=[
                "openrouter::google/gemma-4-31b-it:free",
                "router9::codex-5.5-image",
                "openai_compat::compat/fallback",
            ],
        )
    )

    assert result.provider == "openrouter"
    assert result.model == "google/gemma-4-31b-it:free"
    assert any("openai_compat/compat/fallback" in warning for warning in result.warnings)
    assert calls == [
        ("openai_compat", "compat/primary"),
        ("openai_compat", "compat/fallback"),
        ("openrouter", "google/gemma-4-31b-it:free"),
    ]



def test_openrouter_ocr_payload_uses_vision_message(monkeypatch):
    payloads = []

    class FakeAsyncClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict, timeout=None):
            payloads.append((url, headers, json))
            return httpx.Response(200, json={"choices": [{"message": {"content": "Cho A(0,0)."}}]})

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient(kwargs.get("timeout") or args[1] if len(args) > 1 else 20))

    text = __import__("asyncio").run(
        OpenRouterClient(Settings(openrouter_api_key="secret")).ocr_image(_IMAGE_DATA_URL, "openrouter/vision-model")
    )

    assert text == "Cho A(0,0)."
    assert payloads[0][0] == "https://openrouter.ai/api/v1/chat/completions"
    assert payloads[0][1]["Authorization"] == "Bearer secret"
    assert payloads[0][2]["model"] == "vision-model"
    assert payloads[0][2]["messages"][1]["content"][1]["image_url"]["url"] == _IMAGE_DATA_URL
