import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.auth import UserRepository
from app.services.secret_crypto import generate_user_secret_key


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "user-settings.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(
        _env_file=None,
        sqlite_path=db.path,
        auth_email_dev_mode=True,
        require_email_verification=False,
        user_secret_encryption_key=generate_user_secret_key(),
    )

    async def override_db():
        return db

    async def noop_email(*args, **kwargs):
        return None

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_auth.send_verification_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.send_password_reset_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.deps.get_settings", lambda: settings)
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str = "byok@example.com") -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "accept_privacy_policy": True, "accept_terms": True},
    )
    assert response.status_code == 201
    return response.json()["user"]["id"]


def test_user_settings_defaults_are_redacted(client):
    register_and_login(client)

    response = client.get("/api/user/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_provider"]["enabled"] is False
    assert payload["ai_provider"]["api_key_configured"] is False
    assert "sk-" not in response.text
    assert "api_key_ciphertext" not in response.text


def test_user_can_save_byok_provider_without_leaking_key(client):
    register_and_login(client)

    response = client.put(
        "/api/user/settings/ai-provider",
        json={"enabled": True, "base_url": "http://localhost:1234/v1", "api_key": "sk-test-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_provider"]["enabled"] is True
    assert payload["ai_provider"]["api_key_configured"] is True
    assert payload["ai_provider"]["api_key_last4"] == "cret"
    assert "sk-test-secret" not in response.text

    async def stored_secret():
        return await client.db.fetch_one("SELECT api_key_ciphertext, api_key_last4 FROM user_ai_provider_settings")

    row = asyncio.run(stored_secret())
    assert row["api_key_ciphertext"] != "sk-test-secret"
    assert row["api_key_last4"] == "cret"


def test_user_settings_requires_encryption_key_for_enabled_byok(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "missing-key.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path, auth_email_dev_mode=True, require_email_verification=False)

    async def override_db():
        return db

    async def noop_email(*args, **kwargs):
        return None

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes_auth.send_verification_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.send_password_reset_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.deps.get_settings", lambda: settings)
    with TestClient(app) as test_client:
        register_and_login(test_client, "missing-key@example.com")
        response = test_client.put(
            "/api/user/settings/ai-provider",
            json={"enabled": True, "base_url": "http://localhost:1234/v1", "api_key": "sk-test-secret"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "USER_SECRET_ENCRYPTION_KEY" in response.json()["detail"]


def test_user_ai_models_and_profiles_validate_vision(client):
    register_and_login(client)

    models = client.put(
        "/api/user/settings/ai-models",
        json={"models": [{"model_id": "text-model", "label": "Text", "supports_vision": False, "enabled": True}]},
    )
    assert models.status_code == 200

    invalid_profile = client.put(
        "/api/user/settings/ai-task-profiles",
        json={"task_profiles": [{"task": "ocr", "model_id": "text-model", "enabled": True}]},
    )
    assert invalid_profile.status_code == 400

    models = client.put(
        "/api/user/settings/ai-models",
        json={"models": [{"model_id": "vision-model", "label": "Vision", "supports_vision": True, "enabled": True}]},
    )
    assert models.status_code == 200
    valid_profile = client.put(
        "/api/user/settings/ai-task-profiles",
        json={"task_profiles": [{"task": "ocr", "model_id": "vision-model", "enabled": True}]},
    )
    assert valid_profile.status_code == 200
    assert valid_profile.json()["task_profiles"] == [{"task": "ocr", "model_id": "vision-model", "enabled": True}]


def test_byok_settings_are_scoped_per_user(client):
    first_id = register_and_login(client, "first@example.com")
    first = client.put(
        "/api/user/settings/ai-provider",
        json={"enabled": True, "base_url": "http://localhost:1234/v1", "api_key": "sk-first-secret"},
    )
    assert first.status_code == 200
    client.post("/api/auth/logout")

    second_id = register_and_login(client, "second@example.com")
    second = client.get("/api/user/settings")

    assert first_id != second_id
    assert second.status_code == 200
    assert second.json()["ai_provider"]["enabled"] is False
    assert second.json()["ai_provider"]["api_key_configured"] is False


def test_cannot_delete_model_used_by_task_profile(client):
    register_and_login(client)
    models = client.put(
        "/api/user/settings/ai-models",
        json={"models": [{"model_id": "vision-model", "label": "Vision", "supports_vision": True, "enabled": True}]},
    )
    assert models.status_code == 200
    profile = client.put(
        "/api/user/settings/ai-task-profiles",
        json={"task_profiles": [{"task": "ocr", "model_id": "vision-model", "enabled": True}]},
    )
    assert profile.status_code == 200

    response = client.put("/api/user/settings/ai-models", json={"models": []})

    assert response.status_code == 400
    assert "vision-model" in response.json()["detail"]


def test_byok_provider_check_returns_generic_provider_error(client, monkeypatch):
    register_and_login(client)

    async def fail_check(self):
        raise RuntimeError("Bearer sk-test-secret provider body echoed api_key=sk-test-secret")

    monkeypatch.setattr("app.services.openai_compat_client.OpenAICompatClient.check_connection", fail_check)
    response = client.post(
        "/api/user/settings/ai-provider/check",
        json={"base_url": "http://localhost:1234/v1", "api_key": "sk-test-secret", "model": "gpt-test"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "sk-test-secret" not in response.text
    assert "api_key" not in response.text
