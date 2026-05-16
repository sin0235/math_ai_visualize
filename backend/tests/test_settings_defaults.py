import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.api.routes_settings import LoadedAiSettings
from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.schemas.auth import SystemAiSettings
from app.services.model_registry import registry_from_settings


@pytest.fixture()
def settings_defaults_client(tmp_path):
    db = SQLiteClient(str(tmp_path / "settings.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path, ollama_base_url="http://env-ollama.local", ollama_api_key="", ollama_text_model="env-ollama")

    async def override_db():
        return db

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    import app.api.routes_settings as routes_settings
    import app.services.model_registry as model_registry

    original_routes_get_settings = routes_settings.get_settings
    original_registry_get_settings = model_registry.get_settings
    routes_settings.get_settings = lambda: settings
    model_registry.get_settings = lambda: settings
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    routes_settings.get_settings = original_routes_get_settings
    model_registry.get_settings = original_registry_get_settings
    app.dependency_overrides.clear()



def test_cors_defaults_target_local_dev_origins():
    settings = Settings(_env_file=None)

    assert "*" not in settings.cors_origins
    assert "http://localhost:5173" in settings.cors_origins
    assert "http://127.0.0.1:5173" in settings.cors_origins
    assert settings.require_email_verification is True



def test_settings_defaults_route_hides_api_keys(monkeypatch):
    settings = Settings(
        _env_file=None,
        openrouter_api_key="openrouter-secret",
        nvidia_api_key="nvidia-secret",
        ollama_api_key="ollama-secret",
        router9_api_key="router9-secret",
        router9_text_model="router/model",
        router9_allowed_models=["router/model"],
    )
    monkeypatch.setattr("app.api.routes_settings.get_settings", lambda: settings)

    async def fake_load_system_ai_settings(_db):
        return LoadedAiSettings(SystemAiSettings(), {})

    async def fake_load_model_registry(_db, s=None):
        return registry_from_settings(s if s is not None else settings)

    monkeypatch.setattr("app.api.routes_settings.load_system_ai_settings", fake_load_system_ai_settings)
    monkeypatch.setattr("app.api.routes_settings.load_model_registry", fake_load_model_registry)

    response = TestClient(app).get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert "openrouter-secret" not in response.text
    assert "nvidia-secret" not in response.text
    assert "ollama-secret" not in response.text
    assert "router9-secret" not in response.text
    assert payload["openrouter"]["api_key_configured"] is True
    assert payload["nvidia"]["api_key_configured"] is True
    assert payload["ollama"]["api_key_configured"] is True
    assert payload["router9"]["api_key_configured"] is True
    assert payload["router9"]["model"] == "router/model"
    assert payload["router9"]["allowed_model_ids"] == ["router/model"]



def test_settings_defaults_exposes_public_feature_flags(settings_defaults_client):
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["feature_flags", json.dumps({"version": 1, "maintenance_mode": True, "maintenance_message": "Đang nâng cấp hệ thống.", "render_enabled": False, "ocr_enabled": True, "google_oauth_enabled": False})],
    ))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    assert response.json()["feature_flags"] == {
        "maintenance_mode": True,
        "maintenance_message": "Đang nâng cấp hệ thống.",
        "google_oauth_enabled": False,
        "ocr_enabled": True,
        "render_enabled": False,
    }



def test_settings_defaults_loads_ollama_base_url_from_database(settings_defaults_client):
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({"version": 1, "ollama": {"base_url": "http://db-ollama.local", "model": "db-ollama"}})],
    ))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ollama"]["base_url"] == "http://db-ollama.local"
    assert payload["ollama"]["model"] == "db-ollama"



def test_settings_defaults_falls_back_to_env_when_database_lacks_ollama(settings_defaults_client):
    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ollama"]["base_url"] == "http://env-ollama.local"
    assert payload["ollama"]["model"] == "env-ollama"



def test_settings_defaults_reports_legacy_key_present_without_activating_it(settings_defaults_client):
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({"version": 1, "ollama": {"api_key": "db-ollama-secret"}})],
    ))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ollama"]["api_key_configured"] is False
    assert payload["registry_legacy_ai_settings_present"] is True
    assert "db-ollama-secret" not in response.text


def test_settings_defaults_reports_allowed_openrouter_default(settings_defaults_client):
    asyncio.run(settings_defaults_client.db.execute(
        """
        INSERT INTO ai_providers (id, label, default_model_id)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET default_model_id = excluded.default_model_id
        """,
        ["openrouter", "OpenRouter", "stale/model"],
    ))
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO ai_models (provider_id, id, label, enabled, allowed, source) VALUES (?, ?, ?, 1, 1, 'manual')",
        ["openrouter", "allowed/model", "Allowed model"],
    ))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["openrouter"]["model"] == "allowed/model"
    assert payload["openrouter"]["allowed_model_ids"] == ["allowed/model"]


def test_settings_defaults_reports_nvidia_ocr_profile(settings_defaults_client):
    from app.services.model_registry import save_provider_config, save_task_profile

    asyncio.run(save_provider_config(settings_defaults_client.db, "nvidia", "https://integrate.api.nvidia.com/v1", "nvidia/vision", api_key_configured=True))
    asyncio.run(save_task_profile(settings_defaults_client.db, "ocr", "nvidia", "nvidia/vision", []))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ocr"]["provider"] == "nvidia"
    assert payload["ocr"]["model"] == "vision"


def test_settings_defaults_normalizes_raw_openrouter_model_to_allowlist(settings_defaults_client):
    asyncio.run(settings_defaults_client.db.execute(
        """
        INSERT INTO ai_providers (id, label, default_model_id)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET default_model_id = excluded.default_model_id
        """,
        ["openrouter", "OpenRouter", "stale/model"],
    ))
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO ai_models (provider_id, id, label, enabled, allowed, source) VALUES (?, ?, ?, 1, 1, 'manual')",
        ["openrouter", "allowed/model", "Allowed model"],
    ))
    asyncio.run(settings_defaults_client.db.execute(
        "INSERT INTO system_settings (key, value_json) VALUES (?, ?)",
        ["ai_settings", json.dumps({"version": 1, "openrouter": {"model": "stale/model", "allowed_model_ids": ["allowed/model"]}})],
    ))

    response = settings_defaults_client.get("/api/settings/defaults")

    assert response.status_code == 200
    payload = response.json()
    assert payload["openrouter"]["model"] == "allowed/model"
