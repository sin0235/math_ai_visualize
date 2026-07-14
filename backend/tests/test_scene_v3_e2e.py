import asyncio

from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_active_user, require_trusted_origin
from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.schemas.scene_v3 import MathSceneV3
from app.services.model_registry import registry_from_settings
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


USER = UserRecord(
    id="e2e-v3-user",
    email="e2e-v3@example.com",
    password_hash="unused",
    created_at="2026-01-01 00:00:00",
    updated_at="2026-01-01 00:00:00",
    status="active",
    email_verified_at="2026-01-01 00:00:00",
)


def _scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "e2e-v3-scene",
        "revision": 1,
        "problem_text": "Cho A(0,0), B(2,0).",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"id": "b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
            {"id": "ab", "type": "segment", "point_ids": ["a", "b"]},
        ],
        "audit": {"created_by": "manual"},
    })


def test_render_edit_solve_export_history_restore_v3(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "scene-v3-e2e.db"))
    asyncio.run(apply_sqlite_migrations(db))
    asyncio.run(db.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        [USER.id, USER.email, USER.password_hash],
    ))
    settings = Settings(
        _env_file=None,
        database_backend="sqlite",
        sqlite_path=db.path,
        advisory_enabled=False,
        router9_api_key="",
        openrouter_api_key="",
        openai_compat_api_key="",
    )

    async def active_user():
        return USER

    async def database():
        return db

    async def trusted_origin():
        return None

    async def no_op(*_args, **_kwargs):
        return None

    async def no_byok(*_args, **_kwargs):
        return None

    async def render_result(*_args, **_kwargs):
        return run_scene_pipeline_v3(_scene())

    async def effective_settings(*_args, **_kwargs):
        return settings

    async def model_registry(*_args, **_kwargs):
        return registry_from_settings(settings)

    app.dependency_overrides[require_active_user] = active_user
    app.dependency_overrides[get_current_user] = active_user
    app.dependency_overrides[get_database] = database
    app.dependency_overrides[require_trusted_origin] = trusted_origin
    monkeypatch.setattr("app.api.routes_render.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", no_op)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", no_op)
    monkeypatch.setattr("app.api.routes_render.resolve_byok_ai_config", no_byok)
    monkeypatch.setattr("app.api.routes_render.build_problem_render_result_v3", render_result)
    monkeypatch.setattr("app.api.routes_solve.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.routes_solve.enforce_rate_limit", no_op)
    monkeypatch.setattr("app.api.routes_solve.enforce_render_access", no_op)
    monkeypatch.setattr("app.api.routes_solve.resolve_byok_ai_config", no_byok)
    monkeypatch.setattr("app.api.routes_solve.resolve_effective_settings", effective_settings)
    monkeypatch.setattr("app.api.routes_solve.load_model_registry", model_registry)
    monkeypatch.setattr("app.api.routes_export.enforce_rate_limit", no_op)
    monkeypatch.setattr("app.api.routes_export.enforce_render_access", no_op)

    try:
        client = TestClient(app)
        rendered = client.post("/api/render/v3", json={"problem_text": "Cho A(0,0), B(2,0).", "tier": "tier1"})
        assert rendered.status_code == 201
        assert rendered.json()["trusted_for_downstream"] is True
        rendered_scene_id = rendered.json()["scene"]["scene_id"]
        assert rendered.json()["projection"]["scene_id"] == rendered_scene_id

        edited = client.post("/api/render/v3/commands", json={"command": {
            "type": "move_point",
            "command_id": "e2e-move-b",
            "scene_id": rendered_scene_id,
            "base_revision": 1,
            "point_id": "b",
            "position": [3, 0, 0],
        }})
        assert edited.status_code == 200
        assert edited.json()["scene"]["revision"] == 2
        scene_ref = {"scene_id": rendered_scene_id, "revision": 2}

        solved = client.post("/api/solve", json={
            "scene_ref": scene_ref,
            "question": "d(A,B)",
            "geometry_method": "oxyz",
        })
        assert solved.status_code == 200
        assert solved.json()["answer"] in {"d(A,B) = 3", "d(A,B) = 3.0"}

        exported = client.post("/api/export/tikz", json={"scene_ref": scene_ref})
        assert exported.status_code == 200
        assert "\\begin{tikzpicture}" in exported.text

        history_row = asyncio.run(db.fetch_one(
            "SELECT id FROM render_jobs WHERE user_id = ? AND schema_version = '3.0'",
            [USER.id],
        ))
        assert history_row is not None
        history_id = str(history_row["id"])
        detail = client.get(f"/api/history/{history_id}")
        assert detail.status_code == 200
        assert detail.json()["kind"] == "math_scene_v3"
        assert detail.json()["snapshot_revision"] == 2

        restored = client.post(f"/api/history/{history_id}/restore", json={"snapshot_revision": 1})
        assert restored.status_code == 200
        assert restored.json()["scene"]["revision"] == 1
        assert restored.json()["projection"]["revision"] == 1
        assert restored.json()["trusted_for_downstream"] is True

        stale = client.post("/api/solve", json={"scene_ref": scene_ref, "question": "d(A,B)"})
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "SCENE_EDIT_STALE"
    finally:
        app.dependency_overrides.clear()
        asyncio.run(db.close())
