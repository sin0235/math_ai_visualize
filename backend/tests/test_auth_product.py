import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.auth import AuthTokenRepository, OAUTH_PASSWORD_SENTINEL, OAUTH_PROVIDER_GOOGLE, OAuthIdentityRepository, OAuthStateRepository, TOKEN_PURPOSE_EMAIL_VERIFICATION, TOKEN_PURPOSE_PASSWORD_RESET, UserRepository
from app.services.google_oauth import GoogleUserInfo


def register_payload(email: str, password: str = "StrongPass123") -> dict:
    return {"email": email, "password": password, "accept_privacy_policy": True, "accept_terms": True}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "auth.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(_env_file=None, sqlite_path=db.path, auth_email_dev_mode=True)
    settings_holder = {"value": settings}
    sent_verifications = []

    async def override_db():
        return db

    async def capture_verification(*args, **kwargs):
        sent_verifications.append((args, kwargs))

    async def noop_email(*args, **kwargs):
        return None

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings_holder["value"]
    monkeypatch.setattr("app.api.routes_auth.send_verification_email", capture_verification)
    monkeypatch.setattr("app.api.routes_auth.send_password_reset_email", noop_email)
    monkeypatch.setattr("app.api.routes_auth.get_settings", lambda: settings_holder["value"])
    monkeypatch.setattr("app.api.deps.get_settings", lambda: settings_holder["value"])
    with TestClient(app) as test_client:
        test_client.db = db
        test_client.settings_holder = settings_holder
        test_client.sent_verifications = sent_verifications
        yield test_client
    app.dependency_overrides.clear()


def test_register_requires_and_records_legal_acceptance(client):
    rejected = client.post("/api/auth/register", json={"email": "legal@example.com", "password": "StrongPass123"})
    assert rejected.status_code == 422

    response = client.post("/api/auth/register", json=register_payload("legal@example.com"))
    assert response.status_code == 201

    async def count_acceptances():
        rows = await client.db.fetch_all("SELECT * FROM legal_acceptances WHERE user_id = ?", [response.json()["user"]["id"]])
        return rows

    rows = asyncio.run(count_acceptances())
    assert {row["document_type"] for row in rows} == {"privacy_policy", "terms"}


def test_register_login_me_logout(client):
    response = client.post("/api/auth/register", json=register_payload("User@Example.com"))

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
    client.post("/api/auth/register", json=register_payload("reset@example.com"))
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


def test_verify_email_requires_token_and_otp(client):
    client.post("/api/auth/register", json=register_payload("verify@example.com"))

    async def get_token():
        user = await UserRepository(client.db).find_by_email("verify@example.com")
        _, raw, otp = await AuthTokenRepository(client.db).create(user.id, TOKEN_PURPOSE_EMAIL_VERIFICATION, 60, include_otp=True)
        return raw, otp

    token, otp = asyncio.run(get_token())
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 422
    assert client.post("/api/auth/verify-email", json={"token": token, "otp": "000000"}).status_code == 400

    async def attempts():
        row = await client.db.fetch_one("SELECT otp_attempts FROM auth_tokens WHERE token_hash IS NOT NULL AND consumed_at IS NULL")
        return int(row["otp_attempts"])

    assert asyncio.run(attempts()) >= 1
    response = client.post("/api/auth/verify-email", json={"token": token, "otp": otp})

    assert response.status_code == 200
    assert response.json()["user"]["email_verified_at"] is not None
    assert client.post("/api/auth/verify-email", json={"token": token, "otp": otp}).status_code == 400


def test_verification_email_send_receives_token_and_otp(client):
    response = client.post("/api/auth/register", json=register_payload("mail@example.com"))

    assert response.status_code == 201
    args, _ = client.sent_verifications[-1]
    assert args[1]
    assert len(args[2]) == 6
    assert args[2].isdigit()


def test_require_email_verification_blocks_login_until_verified(client):
    client.settings_holder["value"] = Settings(_env_file=None, sqlite_path=client.db.path, auth_email_dev_mode=True, require_email_verification=True)
    response = client.post("/api/auth/register", json=register_payload("required@example.com"))

    assert response.status_code == 201
    assert not response.cookies.get("hinh_session")
    assert client.post("/api/auth/login", json={"email": "required@example.com", "password": "StrongPass123"}).status_code == 403

    async def get_token():
        user = await UserRepository(client.db).find_by_email("required@example.com")
        _, raw, otp = await AuthTokenRepository(client.db).create(user.id, TOKEN_PURPOSE_EMAIL_VERIFICATION, 60, include_otp=True)
        return raw, otp

    token, otp = asyncio.run(get_token())
    assert client.post("/api/auth/verify-email", json={"token": token, "otp": otp}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "required@example.com", "password": "StrongPass123"}).status_code == 200


def test_resend_verification_is_generic_and_sends_otp(client):
    client.post("/api/auth/register", json=register_payload("resend@example.com"))
    before = len(client.sent_verifications)
    existing = client.post("/api/auth/resend-verification", json={"email": "resend@example.com"})
    missing = client.post("/api/auth/resend-verification", json={"email": "missing@example.com"})

    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json() == missing.json()
    assert len(client.sent_verifications) == before + 1
    args, _ = client.sent_verifications[-1]
    assert len(args[2]) == 6


def test_change_password_revokes_other_sessions(client):
    client.post("/api/auth/register", json=register_payload("sessions@example.com"))
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
    client.post("/api/auth/register", json=register_payload("device@example.com"))
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
    client.post("/api/auth/register", json=register_payload("lock@example.com"))
    client.post("/api/auth/logout")

    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "lock@example.com", "password": "WrongPass123"}).status_code == 401

    locked = client.post("/api/auth/login", json={"email": "lock@example.com", "password": "StrongPass123"})
    assert locked.status_code == 429


def test_google_start_redirects_to_google_and_stores_hashed_state(client):
    client.settings_holder["value"] = Settings(
        _env_file=None,
        sqlite_path=client.db.path,
        auth_email_dev_mode=True,
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://math-renderer-api.sin235.live/api/auth/google/callback",
    )

    response = client.get("/api/auth/google/start", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=client-id" in response.headers["location"]

    async def states():
        return await client.db.fetch_all("SELECT * FROM oauth_states")

    rows = asyncio.run(states())
    assert len(rows) == 1
    assert rows[0]["state_hash"] not in response.headers["location"]


def test_google_callback_creates_verified_user_session(client, monkeypatch):
    client.settings_holder["value"] = Settings(
        _env_file=None,
        sqlite_path=client.db.path,
        auth_email_dev_mode=True,
        public_app_url="https://math-renderer.sin235.live",
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://math-renderer-api.sin235.live/api/auth/google/callback",
    )

    async def create_state():
        _, raw_state = await OAuthStateRepository(client.db).create(OAUTH_PROVIDER_GOOGLE, 10)
        return raw_state

    async def fake_exchange(*args, **kwargs):
        return "access-token"

    async def fake_userinfo(*args, **kwargs):
        return GoogleUserInfo("google-sub", "oauth@example.com", True, "OAuth User", "https://example.com/avatar.png")

    monkeypatch.setattr("app.api.routes_auth.exchange_google_code", fake_exchange)
    monkeypatch.setattr("app.api.routes_auth.fetch_google_userinfo", fake_userinfo)
    state = asyncio.run(create_state())

    response = client.get(f"/api/auth/google/callback?code=code&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://math-renderer.sin235.live?auth=google-success"
    assert response.cookies.get("hinh_session")
    assert client.get("/api/auth/me").json()["user"]["email"] == "oauth@example.com"

    async def identity():
        return await OAuthIdentityRepository(client.db).find_by_provider_subject(OAUTH_PROVIDER_GOOGLE, "google-sub")

    record = asyncio.run(identity())
    assert record is not None
    assert record.email_verified is True


def test_google_callback_links_existing_email_user(client, monkeypatch):
    client.settings_holder["value"] = Settings(
        _env_file=None,
        sqlite_path=client.db.path,
        auth_email_dev_mode=True,
        public_app_url="https://math-renderer.sin235.live",
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://math-renderer-api.sin235.live/api/auth/google/callback",
    )
    client.post("/api/auth/register", json=register_payload("linked@example.com"))

    async def create_state():
        _, raw_state = await OAuthStateRepository(client.db).create(OAUTH_PROVIDER_GOOGLE, 10)
        return raw_state

    async def fake_exchange(*args, **kwargs):
        return "access-token"

    async def fake_userinfo(*args, **kwargs):
        return GoogleUserInfo("google-linked", "linked@example.com", True, "Linked User")

    monkeypatch.setattr("app.api.routes_auth.exchange_google_code", fake_exchange)
    monkeypatch.setattr("app.api.routes_auth.fetch_google_userinfo", fake_userinfo)
    state = asyncio.run(create_state())

    response = client.get(f"/api/auth/google/callback?code=code&state={state}", follow_redirects=False)

    assert response.status_code == 302

    async def users_and_identity():
        users = await client.db.fetch_all("SELECT * FROM users WHERE email = ?", ["linked@example.com"])
        identity = await OAuthIdentityRepository(client.db).find_by_provider_subject(OAUTH_PROVIDER_GOOGLE, "google-linked")
        return users, identity

    users, identity = asyncio.run(users_and_identity())
    assert len(users) == 1
    assert users[0]["email_verified_at"] is not None
    assert identity is not None
    assert identity.user_id == users[0]["id"]


def test_google_callback_rejects_unverified_email_and_replayed_state(client, monkeypatch):
    client.settings_holder["value"] = Settings(
        _env_file=None,
        sqlite_path=client.db.path,
        auth_email_dev_mode=True,
        public_app_url="https://math-renderer.sin235.live",
        google_oauth_client_id="client-id",
        google_oauth_client_secret="client-secret",
        google_oauth_redirect_uri="https://math-renderer-api.sin235.live/api/auth/google/callback",
    )

    async def create_state():
        _, raw_state = await OAuthStateRepository(client.db).create(OAUTH_PROVIDER_GOOGLE, 10)
        return raw_state

    async def fake_exchange(*args, **kwargs):
        return "access-token"

    async def fake_unverified_userinfo(*args, **kwargs):
        return GoogleUserInfo("google-unverified", "unverified@example.com", False)

    monkeypatch.setattr("app.api.routes_auth.exchange_google_code", fake_exchange)
    monkeypatch.setattr("app.api.routes_auth.fetch_google_userinfo", fake_unverified_userinfo)
    state = asyncio.run(create_state())

    first = client.get(f"/api/auth/google/callback?code=code&state={state}", follow_redirects=False)
    second = client.get(f"/api/auth/google/callback?code=code&state={state}", follow_redirects=False)

    assert first.status_code == 302
    assert first.headers["location"] == "https://math-renderer.sin235.live?auth_error=google_unverified_email"
    assert second.status_code == 302
    assert second.headers["location"] == "https://math-renderer.sin235.live?auth_error=google_oauth_failed"


def test_oauth_only_user_password_login_returns_401(client):
    async def create_user():
        return await UserRepository(client.db).create_oauth_user("oauth-only@example.com", "OAuth Only")

    user = asyncio.run(create_user())
    assert user.password_hash == OAUTH_PASSWORD_SENTINEL

    response = client.post("/api/auth/login", json={"email": "oauth-only@example.com", "password": "StrongPass123"})

    assert response.status_code == 401


def test_bad_origin_is_rejected_when_present(client):
    client.post("/api/auth/register", json=register_payload("csrf@example.com"))

    response = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
