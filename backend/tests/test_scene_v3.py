"""Native MathSceneV3 contract and command tests (no v2 adapter)."""

import pytest
from pydantic import ValidationError

from app.schemas.scene_v3 import MathSceneV3, MovePointCommand, SceneCommandRequest
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def native_midpoint_scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "scene_demo",
        "schema_version": "3.0",
        "revision": 2,
        "problem_text": "Cho M là trung điểm AB",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d", "show_axes": True, "show_grid": True},
        "objects": [
            {"id": "pt_a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"id": "pt_m", "type": "point_2d", "label": "M", "x": 1, "y": 0},
            {"id": "pt_b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
            {"id": "seg_ab", "type": "segment", "label": "AB", "point_ids": ["pt_a", "pt_b"]},
        ],
        "relations": [
            {
                "id": "rel_mid",
                "type": "midpoint",
                "operands": [
                    {"role": "point", "ref_id": "pt_m", "ref_kind": "point"},
                    {"role": "segment", "ref_id": "seg_ab", "ref_kind": "segment"},
                ],
            }
        ],
        "annotations": [
            {"id": "ann_eq", "type": "equal_marks", "target_ids": ["seg_ab"], "metadata": {"source": "given"}},
        ],
        "audit": {"created_by": "test"},
    })


def test_native_scene_has_stable_ids_and_typed_operands():
    scene = native_midpoint_scene()
    assert scene.schema_version == "3.0"
    by_label = {obj.label: obj for obj in scene.objects if obj.label}
    assert by_label["AB"].point_ids == (by_label["A"].id, by_label["B"].id)
    assert {op.ref_id for op in scene.relations[0].operands} == {by_label["M"].id, by_label["AB"].id}
    assert [op.ref_kind for op in scene.relations[0].operands] == ["point", "segment"]


def test_native_linear_relations_pass_pipeline():
    scene = MathSceneV3.model_validate({
        "scene_id": "perp-demo",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "AB vuông góc AC, AB = 2, AC = 2",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "pt_a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"id": "pt_b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
            {"id": "pt_c", "type": "point_2d", "label": "C", "x": 0, "y": 2},
            {"id": "seg_ab", "type": "segment", "label": "AB", "point_ids": ["pt_a", "pt_b"]},
            {"id": "seg_ac", "type": "segment", "label": "AC", "point_ids": ["pt_a", "pt_c"]},
        ],
        "relations": [
            {
                "id": "rel_perp",
                "type": "perpendicular",
                "operands": [
                    {"role": "a", "ref_id": "seg_ab", "ref_kind": "segment"},
                    {"role": "b", "ref_id": "seg_ac", "ref_kind": "segment"},
                ],
            },
            {
                "id": "rel_d1",
                "type": "distance",
                "operands": [
                    {"role": "a", "ref_id": "pt_a", "ref_kind": "point"},
                    {"role": "b", "ref_id": "pt_b", "ref_kind": "point"},
                ],
                "args": {"value": 2},
            },
            {
                "id": "rel_d2",
                "type": "distance",
                "operands": [
                    {"role": "a", "ref_id": "pt_a", "ref_kind": "point"},
                    {"role": "b", "ref_id": "pt_c", "ref_kind": "point"},
                ],
                "args": {"value": 2},
            },
        ],
        "audit": {"created_by": "test"},
    })
    result = run_scene_pipeline_v3(scene)
    assert not any(issue.code == "RELATION_CONTRACT_INVALID" for issue in result.issues)
    assert result.can_project
    assert result.status == "verified"


def test_v3_rejects_missing_reference_instead_of_dropping_data():
    payload = native_midpoint_scene().model_dump(mode="json")
    payload["objects"] = [obj for obj in payload["objects"] if obj.get("label") != "A"]
    with pytest.raises(ValidationError, match="tham chiếu ID không tồn tại"):
        MathSceneV3.model_validate(payload)


def test_point_operands_on_perpendicular_fail_contract():
    scene = MathSceneV3.model_validate({
        "scene_id": "bad-perp",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "SA vuông góc đáy",
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"id": "pt_s", "type": "point_3d", "label": "S", "x": 0, "y": 3, "z": 0},
            {"id": "pt_a", "type": "point_3d", "label": "A", "x": 0, "y": 0, "z": 0},
            {"id": "pt_b", "type": "point_3d", "label": "B", "x": 4, "y": 0, "z": 0},
            {"id": "pt_c", "type": "point_3d", "label": "C", "x": 4, "y": 0, "z": 4},
            {"id": "pl_base", "type": "plane", "label": "ABCD", "point_ids": ["pt_a", "pt_b", "pt_c"]},
        ],
        "relations": [
            {
                "id": "rel_bad",
                "type": "perpendicular",
                "operands": [
                    {"role": "a", "ref_id": "pt_s", "ref_kind": "point"},
                    {"role": "b", "ref_id": "pt_a", "ref_kind": "point"},
                ],
            }
        ],
        "audit": {"created_by": "test"},
    })
    result = run_scene_pipeline_v3(scene)
    assert any(issue.code == "RELATION_CONTRACT_INVALID" for issue in result.issues)
    assert not result.can_project


def test_scene_command_requires_scene_and_base_revision():
    command = SceneCommandRequest(command={
        "type": "move_point",
        "command_id": "cmd_1",
        "scene_id": "scene_demo",
        "base_revision": 2,
        "point_id": "obj_a",
        "position": [1, 2, 3],
    }).command
    assert isinstance(command, MovePointCommand)
    assert command.position == (1, 2, 3)


def test_v3_requires_ids_on_objects():
    with pytest.raises(ValidationError):
        MathSceneV3.model_validate({
            "scene_id": "x",
            "schema_version": "3.0",
            "problem_text": "A",
            "topic": "coordinate_2d",
            "renderer": "geogebra_2d",
            "view": {"dimension": "2d"},
            "objects": [{"type": "point_2d", "label": "A", "x": 0, "y": 0}],
            "audit": {"created_by": "test"},
        })
