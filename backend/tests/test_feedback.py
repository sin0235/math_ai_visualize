import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient, get_database
from app.main import app


def register_payload(email: str, password: str = "StrongPass123") -> dict:
    return {"email": email, "password": password, "accept_privacy_policy": True, "accept_terms": True}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "feedback.db"))
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
    with TestClient(app) as test_client:
        test_client.db = db
        yield test_client
    app.dependency_overrides.clear()


def make_user(client: TestClient, email: str) -> TestClient:
    user_client = TestClient(app)
    user_client.post("/api/auth/register", json=register_payload(email))
    return user_client


def make_admin(client: TestClient, email: str) -> TestClient:
    admin_client = make_user(client, email)
    user_id = admin_client.get("/api/auth/me").json()["user"]["id"]
    asyncio.run(client.db.execute("UPDATE users SET role = 'admin' WHERE id = ?", [user_id]))
    return admin_client


def test_user_can_have_only_one_pending_feedback_until_admin_receives(client):
    user_client = make_user(client, "feedback@example.com")
    admin_client = make_admin(client, "admin@example.com")

    first = user_client.post("/api/feedback", json={"subject": "OCR đọc sai", "message": "OCR đọc sai ký hiệu trên hình tam giác."})
    assert first.status_code == 201
    feedback_id = first.json()["id"]

    status_response = user_client.get("/api/feedback/status")
    assert status_response.status_code == 200
    assert status_response.json()["can_submit"] is False

    blocked = user_client.post("/api/feedback", json={"subject": "Góp ý nữa", "message": "Nội dung góp ý thứ hai đang bị chặn."})
    assert blocked.status_code == 409

    listed = admin_client.get("/api/admin/feedback?status=pending")
    assert listed.status_code == 200
    assert any(item["id"] == feedback_id for item in listed.json())

    received = admin_client.patch(f"/api/admin/feedback/{feedback_id}", json={"status": "received", "admin_note": "Đã ghi nhận"})
    assert received.status_code == 200
    assert received.json()["status"] == "received"

    second = user_client.post("/api/feedback", json={"subject": "Góp ý mới", "message": "Admin đã tiếp nhận nên gửi góp ý mới được."})
    assert second.status_code == 201


def test_admin_accepting_feedback_unlocks_next_submission(client):
    user_client = make_user(client, "accepted@example.com")
    admin_client = make_admin(client, "accept-admin@example.com")

    first = user_client.post("/api/feedback", json={"subject": "Đề xuất", "message": "Nên có thêm hướng dẫn trong trang góp ý."})
    assert first.status_code == 201

    accepted = admin_client.patch(f"/api/admin/feedback/{first.json()['id']}", json={"status": "accepted"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    second = user_client.post("/api/feedback", json={"subject": "Đề xuất tiếp", "message": "Có thể gửi tiếp sau khi admin chấp nhận."})
    assert second.status_code == 201


def test_feedback_admin_endpoints_require_admin(client):
    user_client = make_user(client, "normal@example.com")

    assert user_client.get("/api/admin/feedback").status_code == 403
    assert user_client.patch("/api/admin/feedback/missing", json={"status": "received"}).status_code == 403

    anonymous = TestClient(app)
    assert anonymous.post("/api/feedback", json={"subject": "Không", "message": "Chưa đăng nhập không được gửi."}).status_code == 401
