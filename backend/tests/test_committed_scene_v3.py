import asyncio

import pytest

from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.repositories.scene_workspaces import SceneWorkspaceRepository
from app.schemas.scene_v3 import CommittedSceneRefV3, MathSceneV3, SceneCommandRequest
from app.services.committed_scene_v3 import (
    CommittedSceneError,
    confirm_committed_scene_v3,
    load_committed_scene_v3,
)
from app.services.scene_commands_v3 import apply_scene_command
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


USER_ID = "boundary-user"


def scene_needing_confirmation() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "boundary-scene",
        "revision": 1,
        "problem_text": "Hai đoạn cắt nhau tại P",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "x": -1, "y": 0},
            {"id": "b", "type": "point_2d", "x": -1, "y": 0},
            {"id": "c", "type": "point_2d", "x": 0, "y": -1},
            {"id": "d", "type": "point_2d", "x": 0, "y": 1},
            {"id": "p", "type": "point_2d", "x": 0, "y": 0},
            {"id": "ab", "type": "segment", "point_ids": ["a", "b"]},
            {"id": "cd", "type": "segment", "point_ids": ["c", "d"]},
        ],
        "relations": [{
            "id": "perpendicular:degenerate",
            "type": "perpendicular",
            "operands": [
                {"role": "first", "ref_id": "ab", "ref_kind": "segment"},
                {"role": "second", "ref_id": "cd", "ref_kind": "segment"},
            ],
        }],
        "audit": {"created_by": "manual"},
    })


async def initialized_db(path) -> SQLiteClient:
    db = SQLiteClient(str(path))
    await apply_sqlite_migrations(db)
    await db.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        [USER_ID, "boundary@example.com", "unused"],
    )
    return db


def test_committed_boundary_requires_server_confirmation_and_invalidates_it_on_revision(tmp_path):
    async def run():
        db = await initialized_db(tmp_path / "boundary.db")
        repository = SceneWorkspaceRepository(db)
        scene = scene_needing_confirmation()
        result = run_scene_pipeline_v3(scene)
        assert result.status == "needs_confirmation"
        await repository.create(USER_ID, result)
        reference = CommittedSceneRefV3(scene_id=scene.scene_id, revision=1)

        with pytest.raises(CommittedSceneError) as trust_error:
            await load_committed_scene_v3(db, USER_ID, reference)
        assert trust_error.value.code == "SCENE_TRUST_REQUIRED"
        assert trust_error.value.status_code == 409

        confirmed = await confirm_committed_scene_v3(db, USER_ID, reference)
        assert confirmed.trusted_for_downstream
        assert confirmed.workspace.confirmed_revision == 1
        assert (await load_committed_scene_v3(db, USER_ID, reference)).trusted_for_downstream

        command = SceneCommandRequest.model_validate({"command": {
            "type": "move_point",
            "command_id": "move-p",
            "scene_id": scene.scene_id,
            "base_revision": 1,
            "point_id": "p",
            "position": [0, 0, 0],
        }}).command
        applied = apply_scene_command(scene, command)
        next_result = run_scene_pipeline_v3(applied.scene)
        await repository.commit_command(USER_ID, command, applied, next_result, None)
        latest = await repository.find_for_user(USER_ID, scene.scene_id)
        assert latest is not None
        assert latest.scene.revision == 2
        assert latest.confirmed_revision is None

        with pytest.raises(CommittedSceneError) as stale_error:
            await load_committed_scene_v3(db, USER_ID, reference)
        assert stale_error.value.code == "SCENE_EDIT_STALE"
        assert stale_error.value.status_code == 409
        await db.close()

    asyncio.run(run())


def test_committed_boundary_enforces_workspace_ownership(tmp_path):
    async def run():
        db = await initialized_db(tmp_path / "ownership.db")
        scene = scene_needing_confirmation()
        await SceneWorkspaceRepository(db).create(USER_ID, run_scene_pipeline_v3(scene))

        with pytest.raises(CommittedSceneError) as error:
            await load_committed_scene_v3(
                db,
                "another-user",
                CommittedSceneRefV3(scene_id=scene.scene_id, revision=1),
            )
        assert error.value.code == "SCENE_WORKSPACE_NOT_FOUND"
        assert error.value.status_code == 404
        await db.close()

    asyncio.run(run())