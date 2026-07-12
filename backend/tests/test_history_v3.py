import asyncio
import json

from app.api.routes_history import get_history, restore_history_v3
from app.api.routes_render import workspace_response_v3
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient
from app.repositories.history import RenderHistoryRepository
from app.repositories.scene_workspaces import SceneWorkspaceRepository
from app.schemas.auth import RestoreHistoryV3Request
from app.schemas.scene_v3 import MathSceneV3, SceneCommandRequest, SceneWorkspaceResponseV3
from app.services.committed_scene_v3 import load_committed_scene_v3
from app.services.scene_commands_v3 import apply_scene_command
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3
from app.schemas.scene_v3 import CommittedSceneRefV3


USER_ID = "history-v3-user"


def _user() -> UserRecord:
    return UserRecord(
        id=USER_ID,
        email="history-v3@example.com",
        password_hash="unused",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        status="active",
        email_verified_at="2024-01-01T00:00:00Z",
    )


def _scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "history-v3-scene",
        "revision": 1,
        "problem_text": "Đoạn thẳng AB.",
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


async def _db(path) -> SQLiteClient:
    db = SQLiteClient(str(path))
    await apply_sqlite_migrations(db)
    await db.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        [USER_ID, "history-v3@example.com", "unused"],
    )
    return db


def test_v3_history_snapshots_commands_and_restores_workspace(tmp_path):
    async def run():
        db = await _db(tmp_path / "history-v3.db")
        history = RenderHistoryRepository(db)
        workspaces = SceneWorkspaceRepository(db)
        initial_result = run_scene_pipeline_v3(_scene())
        initial_response = workspace_response_v3(initial_result, trusted_for_downstream=True)

        job = await history.create_v3_workspace(USER_ID, initial_response)
        persisted = await workspaces.find_for_user(USER_ID, _scene().scene_id)
        assert persisted is not None
        assert persisted.history_item_id == job.id
        first_snapshot = await history.find_v3_snapshot_for_user(USER_ID, job.id, 1)
        assert first_snapshot is not None
        assert first_snapshot.schema_version == "3.0"
        assert first_snapshot.snapshot_revision == 1
        assert first_snapshot.command_log_json == "[]"

        command = SceneCommandRequest.model_validate({"command": {
            "type": "move_point",
            "command_id": "move-b",
            "scene_id": _scene().scene_id,
            "base_revision": 1,
            "point_id": "b",
            "position": [3, 0, 0],
        }}).command
        applied = apply_scene_command(persisted.scene, command)
        next_result = run_scene_pipeline_v3(applied.scene)
        await workspaces.commit_command(USER_ID, command, applied, next_result, job.id)

        latest_snapshot = await history.find_v3_snapshot_for_user(USER_ID, job.id)
        assert latest_snapshot is not None
        assert latest_snapshot.snapshot_revision == 2
        assert json.loads(latest_snapshot.command_log_json)[0]["command_id"] == "move-b"
        latest_response = SceneWorkspaceResponseV3.model_validate_json(latest_snapshot.response_json)
        assert latest_response.scene.revision == 2
        assert latest_response.changed_object_ids == ["b"]
        detail = await get_history(job.id, user=_user(), db=db)
        assert detail.kind == "math_scene_v3"
        assert detail.snapshot_revision == 2
        assert detail.command_log[0].command_id == "move-b"

        restored_response = await restore_history_v3(
            job.id,
            RestoreHistoryV3Request(snapshot_revision=1),
            user=_user(),
            db=db,
        )
        assert restored_response.scene.revision == 1
        restored = await workspaces.find_for_user(USER_ID, _scene().scene_id)
        assert restored is not None
        assert restored.scene.revision == 1
        assert restored.scene.objects[1].x == 2
        committed = await load_committed_scene_v3(
            db,
            USER_ID,
            CommittedSceneRefV3(scene_id=_scene().scene_id, revision=1),
        )
        assert committed.trusted_for_downstream
        await db.close()

    asyncio.run(run())