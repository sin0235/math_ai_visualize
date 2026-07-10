"""Unit test cho sinh đề biến thể từ MathScene."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.migrations import apply_sqlite_migrations
from app.api.deps import require_active_user
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.auth import UserRepository
from app.schemas.scene import MathScene
from app.services import problem_variants as variants_module

_IMAGE_DATA_URL = "data:image/png;base64,aGVsbG8="

_SCENE_JSON = {
    "problem_text": "Cho tam giác ABC vuông tại A.",
    "topic": "coordinate_2d",
    "renderer": "geogebra_2d",
    "view": {"dimension": "2d", "show_axes": True, "show_grid": False},
    "objects": [
        {"type": "point_2d", "name": "A", "x": 0, "y": 0},
        {"type": "point_2d", "name": "B", "x": 4, "y": 0},
        {"type": "point_2d", "name": "C", "x": 0, "y": 3},
        {"type": "segment", "name": "AB", "points": ["A", "B"]},
        {"type": "segment", "name": "AC", "points": ["A", "C"]},
        {"type": "segment", "name": "BC", "points": ["B", "C"]},
    ],
    "annotations": [],
}


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "diagram.db"))
    asyncio.run(apply_sqlite_migrations(db))
    settings = Settings(
        _env_file=None,
        sqlite_path=db.path,
        openrouter_api_key="ROUTER_KEY",
    )
    user = asyncio.run(UserRepository(db).create("diagram@example.com", "StrongPass123"))

    async def override_db():
        return db

    async def override_user():
        return user

    app.dependency_overrides[get_database] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[require_active_user] = override_user
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.model_registry.get_settings", lambda: settings)
    try:
        yield db
    finally:
        app.dependency_overrides.clear()


def test_diagram_ocr_endpoint_removed():
    response = TestClient(app).post(
        "/api/diagram/ocr",
        json={"image_data_url": _IMAGE_DATA_URL},
    )

    assert response.status_code == 404


def test_generate_variants_returns_list(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"variants": ['
                                '"Cho tam giác MNP vuông tại M có MN = 3, MP = 4. Tính diện tích tam giác MNP.",'
                                '"Cho tam giác PQR vuông tại Q có QP = 6, QR = 8. Tính độ dài cạnh huyền PR."'
                                "]}"
                            )
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient())

    response = TestClient(app).post(
        "/api/problem/variants",
        json={
            "scene": _SCENE_JSON,
            "count": 2,
            "original_problem": "Cho tam giác ABC vuông tại A có AB = 3, AC = 4.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["variants"]) == 2
    assert "tam giác" in body["variants"][0]
    payload = captured["payload"]
    assert payload is not None
    assert payload["messages"][0]["role"] == "system"


def test_generate_variants_validates_count(monkeypatch):
    """Pydantic chặn count > 10 ở tầng schema (HTTP 422)."""
    response = TestClient(app).post(
        "/api/problem/variants",
        json={"scene": _SCENE_JSON, "count": 999},
    )
    assert response.status_code == 422


def test_generate_variants_handles_empty_response(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {"choices": [{"message": {"content": '{"variants": []}'}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            return FakeResponse()

    monkeypatch.setattr("app.services.http_pool.get_client", lambda *args, **kwargs: FakeAsyncClient())

    response = TestClient(app).post(
        "/api/problem/variants",
        json={"scene": _SCENE_JSON, "count": 2},
    )
    # Service raise RuntimeError -> route trả 400
    assert response.status_code == 400


def test_math_scene_serialises_for_variants_prompt():
    """Đảm bảo MathScene từ _SCENE_JSON validate được."""
    scene = MathScene.model_validate(_SCENE_JSON)
    assert scene.problem_text.startswith("Cho tam giác")
    assert len(scene.objects) == 6
