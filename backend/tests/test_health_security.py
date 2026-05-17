import asyncio

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.auth import UserRepository


def test_health_detail_requires_admin(tmp_path):
    db = SQLiteClient(str(tmp_path / "health.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, database_backend="sqlite", sqlite_path=db.path, require_email_verification=False)

    async def override_db():
        return db

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        client = TestClient(app)
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health/detail").status_code == 401

        user = asyncio.run(UserRepository(db).create("admin@example.com", "StrongPass123"))
        asyncio.run(db.execute("UPDATE users SET role = 'admin' WHERE id = ?", [user.id]))
        login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "StrongPass123"})
        assert login.status_code == 200
        assert client.get("/api/health/detail").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_ai_status_hides_sensitive_provider_metadata(tmp_path):
    db = SQLiteClient(str(tmp_path / "ai-status.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(
        _env_file=None,
        database_backend="sqlite",
        sqlite_path=db.path,
        openrouter_api_key="secret",
    )

    async def override_db():
        return db

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get("/api/ai/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "secret" not in response.text
    for provider in payload["providers"]:
        assert "api_key_configured" not in provider
        assert "base_url_configured" not in provider
        assert "last_check_message" not in provider
        assert "default_model_id" not in provider
