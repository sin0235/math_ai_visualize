import pytest
from pydantic import ValidationError

from app.schemas.scene_v3 import MathSceneV3, MovePointCommand, SceneCommandRequest
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3
from app.services.scene_v3_adapter import migrate_scene_v2_dict


def v2_scene():
    return {
        "schema_version": "2.0",
        "scene_id": "scene_demo",
        "revision": 2,
        "problem_text": "Cho M là trung điểm AB",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d", "show_axes": True, "show_grid": True},
        "objects": [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "M", "x": 1, "y": 0},
            {"type": "point_2d", "name": "B", "x": 2, "y": 0},
            {"type": "segment", "name": "AB", "points": ["A", "B"]},
        ],
        "relations": [
            {"type": "midpoint", "object_1": "M", "object_2": "A-B"},
        ],
        "annotations": [
            {"type": "equal_marks", "target": "A-M", "metadata": {"source": "given"}},
        ],
    }


def test_v2_adapter_creates_deterministic_typed_references():
    first, first_report = migrate_scene_v2_dict(v2_scene())
    second, second_report = migrate_scene_v2_dict(v2_scene())

    assert first.schema_version == "3.0"
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first_report == second_report
    assert not first_report.requires_confirmation

    by_label = {obj.label: obj for obj in first.objects}
    segment = by_label["AB"]
    assert segment.point_ids == (by_label["A"].id, by_label["B"].id)
    assert {operand.ref_id for operand in first.relations[0].operands} == {
        by_label["M"].id,
        by_label["AB"].id,
    }


def test_v2_adapter_resolves_compact_segment_names_for_linear_relations():
    payload = v2_scene()
    payload["objects"][3].pop("name")
    payload["objects"].extend([
        {"type": "point_2d", "name": "C", "x": 0, "y": 2},
        {"type": "segment", "points": ["A", "C"]},
    ])
    payload["relations"] = [
        {"type": "perpendicular", "object_1": "AB", "object_2": "AC"},
        {"type": "distance", "object_1": "AB", "metadata": {"value": 2}},
        {"type": "distance", "object_1": "AC", "metadata": {"value": 2}},
    ]
    payload["annotations"] = []

    scene, report = migrate_scene_v2_dict(payload)
    result = run_scene_pipeline_v3(scene)

    assert not report.requires_confirmation
    assert [operand.ref_kind for operand in scene.relations[0].operands] == ["segment", "segment"]
    assert all([operand.ref_kind for operand in relation.operands] == ["point", "point"] for relation in scene.relations[1:])
    assert [relation.args["value"] for relation in scene.relations[1:]] == [2, 2]
    assert result.status == "verified"
    assert result.can_project


def test_v3_rejects_missing_reference_instead_of_dropping_data():
    scene, _ = migrate_scene_v2_dict(v2_scene())
    payload = scene.model_dump(mode="json")
    payload["objects"] = [obj for obj in payload["objects"] if obj["label"] != "A"]

    with pytest.raises(ValidationError, match="tham chiếu ID không tồn tại"):
        MathSceneV3.model_validate(payload)


def test_v2_adapter_marks_ambiguous_label_for_confirmation():
    payload = v2_scene()
    payload["objects"].append({"type": "point_2d", "name": "A", "x": 4, "y": 0})

    scene, report = migrate_scene_v2_dict(payload)

    assert report.requires_confirmation
    assert any("không duy nhất" in item for item in report.unresolved_references)
    assert all(obj.type != "segment" for obj in scene.objects)


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


def test_v3_does_not_generate_missing_ids_during_validation():
    payload = v2_scene()
    payload["schema_version"] = "3.0"

    with pytest.raises(ValidationError):
        MathSceneV3.model_validate(payload)