import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.services.provider_ping import ProviderPingResult


def register_payload(email: str, password: str = "StrongPass123") -> dict:
    return {"email": email, "password": password, "accept_privacy_policy": True, "accept_terms": True}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "admin-packages.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path, auth_email_dev_mode=True, require_email_verification=False)

    async def override_db():
        return db

    async def noop_email(*args, **kwargs):
        return None

    async def noop_startup(*args, **kwargs):
        return None

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.create_database_client", lambda current_settings: db)
    monkeypatch.setattr("app.main.apply_migrations", noop_startup)
    monkeypatch.setattr("app.main.bootstrap_router9_models", noop_startup)
    monkeypatch.setattr("app.api.routes_auth.send_verification_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.send_password_reset_email", noop_email)
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    app.dependency_overrides.clear()


def make_user(email: str) -> TestClient:
    user_client = TestClient(app)
    user_client.post("/api/auth/register", json=register_payload(email))
    return user_client


def make_admin(client: TestClient, email: str) -> TestClient:
    admin_client = make_user(email)
    user_id = admin_client.get("/api/auth/me").json()["user"]["id"]
    asyncio.run(client.db.execute("UPDATE users SET role = 'admin' WHERE id = ?", [user_id]))
    return admin_client


def test_migration_seeds_default_plans(client):
    rows = asyncio.run(client.db.fetch_all("SELECT id, name, daily_render_limit, daily_ocr_limit FROM plans ORDER BY sort_order"))

    assert [row["id"] for row in rows] == ["free", "pro", "pro_plus"]
    assert rows[0]["daily_render_limit"] == 20
    assert rows[1]["daily_render_limit"] == 200
    assert rows[2]["daily_render_limit"] is None


def test_admin_lists_and_updates_plans(client):
    admin_client = make_admin(client, "admin@example.com")

    listed = admin_client.get("/api/admin/plans")
    updated = admin_client.patch("/api/admin/plans/pro_plus", json={"name": "Pro+", "daily_render_limit": 500, "daily_ocr_limit": None})
    missing = admin_client.patch("/api/admin/plans/missing", json={"daily_render_limit": 5})
    invalid = admin_client.patch("/api/admin/plans/free", json={"daily_render_limit": -1})

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == ["free", "pro", "pro_plus"]
    assert updated.status_code == 200
    assert updated.json()["daily_render_limit"] == 500
    assert updated.json()["daily_ocr_limit"] is None
    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_admin_can_update_and_filter_user_plan(client):
    admin_client = make_admin(client, "admin@example.com")
    user_client = make_user("plan-user@example.com")
    user_id = user_client.get("/api/auth/me").json()["user"]["id"]

    updated = admin_client.patch(f"/api/admin/users/{user_id}", json={"plan": "pro_plus"})

    assert updated.status_code == 200
    assert updated.json()["plan"] == "pro_plus"

    filtered = admin_client.get("/api/admin/users?plan=pro_plus")
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [user_id]


def test_admin_rejects_unknown_or_inactive_user_plan(client):
    admin_client = make_admin(client, "admin@example.com")
    user_client = make_user("unknown-plan@example.com")
    user_id = user_client.get("/api/auth/me").json()["user"]["id"]

    unknown_update = admin_client.patch(f"/api/admin/users/{user_id}", json={"plan": "enterprise"})
    unknown_filter = admin_client.get("/api/admin/users?plan=enterprise")
    disabled_plan = admin_client.patch("/api/admin/plans/pro", json={"is_active": False})
    inactive_update = admin_client.patch(f"/api/admin/users/{user_id}", json={"plan": "pro"})

    assert unknown_update.status_code == 422
    assert unknown_filter.status_code == 422
    assert disabled_plan.status_code == 200
    assert inactive_update.status_code == 422


def test_legacy_plan_settings_is_rejected(client):
    admin_client = make_admin(client, "admin@example.com")

    response = admin_client.put("/api/admin/system-settings", json={"key": "plan_settings", "value": {"version": 1, "plans": {"free": {}}}})

    assert response.status_code == 422


def test_admin_check_all_providers_uses_ping_module(client, monkeypatch):
    admin_client = make_admin(client, "admin@example.com")

    async def fake_ping_provider(provider, settings):
        return ProviderPingResult(provider=provider, status="ok", message=f"{provider} ok", model=f"{provider}-model", latency_ms=3)

    monkeypatch.setattr("app.api.routes_admin.ping_provider", fake_ping_provider)

    response = admin_client.post("/api/admin/providers/check-all", json={})

    assert response.status_code == 200
    body = response.json()
    assert [item["provider"] for item in body["results"]] == ["openrouter", "nvidia", "ollama", "openai_compat", "router9"]
    rows = asyncio.run(client.db.fetch_all("SELECT id, last_check_status FROM ai_providers ORDER BY id"))
    statuses = {row["id"]: row["last_check_status"] for row in rows}
    assert statuses["openrouter"] == "ok"
    assert statuses["router9"] == "ok"
