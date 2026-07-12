import pytest

from app.schemas.scene_v3 import MathSceneV3, SceneCommandRequest
from app.services.scene_commands_v3 import SceneCommandError, apply_scene_command
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def scene():
    return MathSceneV3.model_validate({
        "scene_id": "scene_commands",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "command test",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"id": "b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
            {"id": "p", "type": "point_2d", "label": "P", "x": 1, "y": 1},
            {"id": "ab", "type": "segment", "label": "AB", "point_ids": ["a", "b"]},
        ],
        "relations": [],
        "audit": {"created_by": "manual"},
    })


def command(payload):
    return SceneCommandRequest(command=payload).command


def test_move_command_and_inverse_are_revision_safe():
    original = scene()
    applied = apply_scene_command(original, command({
        "type": "move_point", "command_id": "move-1", "scene_id": original.scene_id,
        "base_revision": 1, "point_id": "p", "position": [3, 4, 0],
    }))

    assert original.revision == 1
    assert applied.scene.revision == 2
    assert next(obj for obj in applied.scene.objects if obj.id == "p").x == 3
    assert applied.inverse.base_revision == 2

    undone = apply_scene_command(applied.scene, applied.inverse)
    restored = next(obj for obj in undone.scene.objects if obj.id == "p")
    assert (restored.x, restored.y) == (1, 1)
    assert undone.scene.revision == 3


def test_stale_command_is_rejected_before_change():
    with pytest.raises(SceneCommandError) as caught:
        apply_scene_command(scene(), command({
            "type": "move_point", "command_id": "move-stale", "scene_id": "scene_commands",
            "base_revision": 9, "point_id": "p", "position": [3, 4, 0],
        }))

    assert caught.value.code == "SCENE_EDIT_STALE"


def test_projection_is_atomic_verified_and_undoable():
    original = scene()
    applied = apply_scene_command(original, command({
        "type": "project_point", "command_id": "project-1", "scene_id": original.scene_id,
        "base_revision": 1, "source_point_id": "p", "target_id": "ab", "target_kind": "segment",
        "result_point_id": "h",
    }))

    foot = next(obj for obj in applied.scene.objects if obj.id == "h")
    assert (foot.x, foot.y) == pytest.approx((1, 0))
    assert {relation.type for relation in applied.scene.relations} == {"point_on_segment", "perpendicular"}
    assert run_scene_pipeline_v3(applied.scene).status == "verified"

    undone = apply_scene_command(applied.scene, applied.inverse)
    assert {obj.id for obj in undone.scene.objects} == {obj.id for obj in original.objects}
    assert undone.scene.relations == []


def test_intersection_command_creates_verified_fact():
    payload = scene().model_dump(mode="json")
    payload["objects"].extend([
        {"id": "c", "type": "point_2d", "x": 1, "y": -1},
        {"id": "d", "type": "point_2d", "x": 1, "y": 2},
        {"id": "cd", "type": "segment", "point_ids": ["c", "d"]},
    ])
    base = MathSceneV3.model_validate(payload)
    applied = apply_scene_command(base, command({
        "type": "intersect_objects", "command_id": "intersection-1", "scene_id": base.scene_id,
        "base_revision": 1, "object_ids": ["ab", "cd"], "result_object_id": "i",
    }))

    result = run_scene_pipeline_v3(applied.scene)

    assert result.status == "verified"
    assert result.verification[0].status == "verified"


def test_delete_rejects_object_still_used_by_geometry():
    with pytest.raises(SceneCommandError) as caught:
        apply_scene_command(scene(), command({
            "type": "delete_object", "command_id": "delete-a", "scene_id": "scene_commands",
            "base_revision": 1, "object_id": "a",
        }))

    assert caught.value.code == "SCENE_OBJECT_IN_USE"