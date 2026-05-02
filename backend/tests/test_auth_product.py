import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.auth import AuthTokenRepository, TOKEN_PURPOSE_EMAIL_VERIFICATION, TOKEN_PURPOSE_PASSWORD_RESET, UserRepository


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "auth.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path, auth_email_dev_mode=True)

    async def override_db():
        return db

    async def noop_email(*args, **kwargs):
        return None

    app.dependency_overrides[get_database] = override_db
    monkeypatch.setattr("app.api.routes_auth.send_verification_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.send_password_reset_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.deps.get_settings", lambda: settings)
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    app.dependency_overrides.clear()


def test_register_login_me_logout(client):
    response = client.post("/api/auth/register", json={"email": "User@Example.com", "password": "StrongPass123"})

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "user@example.com"
    assert response.cookies.get("hinh_session")

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@example.com"

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "StrongPass123"})
    assert login.status_code == 200
    assert login.cookies.get("hinh_session")


def test_forgot_password_response_is_generic_and_reset_consumes_token(client):
    client.post("/api/auth/register", json={"email": "reset@example.com", "password": "StrongPass123"})
    existing = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})

    assert existing.status_code == 200
    assert unknown.status_code == 200
    assert existing.json() == unknown.json()

    async def get_token():
        user = await UserRepository(client.db).find_by_email("reset@example.com")
        _, raw = await AuthTokenRepository(client.db).create(user.id, TOKEN_PURPOSE_PASSWORD_RESET, 60)
        return raw

    token = asyncio.run(get_token())
    reset = client.post("/api/auth/reset-password", json={"token": token, "password": "NewStrongPass123"})
    assert reset.status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "AnotherStrongPass123"}).status_code == 400
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewStrongPass123"}).status_code == 200


def test_verify_email_sets_verified_timestamp(client):
    client.post("/api/auth/register", json={"email": "verify@example.com", "password": "StrongPass123"})

    async def get_token():
        user = await UserRepository(client.db).find_by_email("verify@example.com")
        _, raw = await AuthTokenRepository(client.db).create(user.id, TOKEN_PURPOSE_EMAIL_VERIFICATION, 60)
        return raw

    token = asyncio.run(get_token())
    response = client.post("/api/auth/verify-email", json={"token": token})

    assert response.status_code == 200
    assert response.json()["user"]["email_verified_at"] is not None
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_change_password_revokes_other_sessions(client):
    client.post("/api/auth/register", json={"email": "sessions@example.com", "password": "StrongPass123"})
    first_session = client.cookies.get("hinh_session")
    other = TestClient(app)
    other.cookies.clear()
    other.post("/api/auth/login", json={"email": "sessions@example.com", "password": "StrongPass123"})
    assert other.cookies.get("hinh_session") != first_session

    response = client.post("/api/auth/change-password", json={"current_password": "StrongPass123", "new_password": "NewStrongPass123"})

    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "sessions@example.com", "password": "StrongPass123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "sessions@example.com", "password": "NewStrongPass123"}).status_code == 200


def test_session_listing_and_revocation(client):
    client.post("/api/auth/register", json={"email": "device@example.com", "password": "StrongPass123"})
    second = TestClient(app)
    second.cookies.clear()
    second.post("/api/auth/login", json={"email": "device@example.com", "password": "StrongPass123"})

    sessions = client.get("/api/auth/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 2
    assert "token_hash" not in sessions.text

    other_session = next(session for session in sessions.json() if not session["current"])
    assert client.delete(f"/api/auth/sessions/{other_session['id']}").status_code == 200
    assert second.get("/api/auth/me").status_code == 401


def test_failed_login_lockout(client):
    client.post("/api/auth/register", json={"email": "lock@example.com", "password": "StrongPass123"})
    client.post("/api/auth/logout")

    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "lock@example.com", "password": "WrongPass123"}).status_code == 401

    locked = client.post("/api/auth/login", json={"email": "lock@example.com", "password": "StrongPass123"})
    assert locked.status_code == 429


def test_bad_origin_is_rejected_when_present(client):
    client.post("/api/auth/register", json={"email": "csrf@example.com", "password": "StrongPass123"})

    response = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
