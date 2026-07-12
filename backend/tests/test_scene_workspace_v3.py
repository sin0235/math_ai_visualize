import asyncio

from fastapi.testclient import TestClient

from app.api.deps import require_active_user, require_trusted_origin
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient, get_database
from app.main import app
from app.repositories.scene_workspaces import SceneWorkspaceRepository
from app.schemas.scene_v3 import MathSceneV3, SceneCommandRequest
from app.services.scene_commands_v3 import apply_scene_command
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


USER = UserRecord(
    id="user-v3",
    email="v3@example.com",
    password_hash="unused",
    created_at="2026-01-01 00:00:00",
    updated_at="2026-01-01 00:00:00",
)


def scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "workspace-v3",
        "revision": 1,
        "problem_text": "workspace test",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "x": 0, "y": 0},
            {"id": "b", "type": "point_2d", "x": 2, "y": 0},
            {"id": "p", "type": "point_2d", "x": 1, "y": 1},
            {"id": "ab", "type": "segment", "point_ids": ["a", "b"]},
        ],
        "relations": [],
        "audit": {"created_by": "manual"},
    })


def command(command_id: str, x: float, revision: int = 1):
    return SceneCommandRequest.model_validate({
        "command": {
            "type": "move_point",
            "command_id": command_id,
            "scene_id": "workspace-v3",
            "base_revision": revision,
            "point_id": "p",
            "position": [x, 1, 0],
        }
    }).command


async def initialized_db(path) -> SQLiteClient:
    db = SQLiteClient(str(path))
    await apply_sqlite_migrations(db)
    await db.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        [USER.id, USER.email, USER.password_hash],
    )
    return db


def test_workspace_api_commits_command_and_rejects_stale_revision(tmp_path):
    db = asyncio.run(initialized_db(tmp_path / "workspace-api.db"))

    async def active_user():
        return USER

    async def database():
        return db

    async def trusted_origin():
        return None

    app.dependency_overrides[require_active_user] = active_user
    app.dependency_overrides[get_database] = database
    app.dependency_overrides[require_trusted_origin] = trusted_origin
    try:
        client = TestClient(app)
        created = client.post("/api/render/v3/workspaces", json={"scene": scene().model_dump(mode="json")})
        assert created.status_code == 201
        assert created.json()["scene"]["revision"] == 1
        assert created.json()["projection"]["scene_id"] == "workspace-v3"
        assert created.json()["payload"]["renderer"] == "geogebra_2d"
        assert "p = (1, 1)" in created.json()["payload"]["geogebra_commands"]

        applied = client.post("/api/render/v3/commands", json={"command": command("move-1", 3).model_dump(mode="json")})
        assert applied.status_code == 200
        assert applied.json()["scene"]["revision"] == 2
        assert applied.json()["inverse_command"]["base_revision"] == 2

        stale = client.post("/api/render/v3/commands", json={"command": command("move-2", 4).model_dump(mode="json")})
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "SCENE_EDIT_STALE"

        latest = client.get("/api/render/v3/workspaces/workspace-v3")
        assert latest.status_code == 200
        assert latest.json()["scene"]["revision"] == 2
    finally:
        app.dependency_overrides.clear()
        asyncio.run(db.close())


def test_workspace_revision_commit_is_atomic_under_conflict(tmp_path):
    async def run():
        db = await initialized_db(tmp_path / "workspace-race.db")
        repository = SceneWorkspaceRepository(db)
        base = scene()
        initial = run_scene_pipeline_v3(base)
        await repository.create(USER.id, initial)

        first_command = command("race-1", 3)
        second_command = command("race-2", 4)
        first = apply_scene_command(base, first_command)
        second = apply_scene_command(base, second_command)
        outcomes = await asyncio.gather(
            repository.commit_command(USER.id, first_command, first, run_scene_pipeline_v3(first.scene), None),
            repository.commit_command(USER.id, second_command, second, run_scene_pipeline_v3(second.scene), None),
            return_exceptions=True,
        )

        workspace = await repository.find_for_user(USER.id, base.scene_id)
        rows = await db.fetch_all("SELECT * FROM scene_commands WHERE scene_id = ?", [base.scene_id])
        await db.close()
        assert sum(isinstance(outcome, Exception) for outcome in outcomes) == 1
        assert workspace is not None and workspace.scene.revision == 2
        assert len(rows) == 1

    asyncio.run(run())


def test_problem_render_v3_creates_committed_workspace(tmp_path, monkeypatch):
    db = asyncio.run(initialized_db(tmp_path / "problem-render-v3.db"))
    problem_scene = scene().model_copy(update={"scene_id": "problem-render-v3"})

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

    async def build_result(*_args, **_kwargs):
        return run_scene_pipeline_v3(problem_scene)

    app.dependency_overrides[require_active_user] = active_user
    app.dependency_overrides[get_database] = database
    app.dependency_overrides[require_trusted_origin] = trusted_origin
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", no_op)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", no_op)
    monkeypatch.setattr("app.api.routes_render.resolve_byok_ai_config", no_byok)
    monkeypatch.setattr("app.api.routes_render.build_problem_render_result_v3", build_result)
    try:
        response = TestClient(app).post("/api/render/v3", json={"problem_text": "Dựng AB", "tier": "tier1"})
        assert response.status_code == 201
        payload = response.json()
        assert payload["scene"]["scene_id"] == "problem-render-v3"
        assert payload["projection"]["scene_id"] == "problem-render-v3"
        stored = asyncio.run(SceneWorkspaceRepository(db).find_for_user(USER.id, "problem-render-v3"))
        assert stored is not None
        assert stored.scene.revision == 1
    finally:
        app.dependency_overrides.clear()
        asyncio.run(db.close())