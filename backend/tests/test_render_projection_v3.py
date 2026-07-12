from app.renderers.geogebra_commands import build_geogebra_commands_v3
from app.renderers.three_scene import build_three_scene_v3
from app.schemas.scene_v3 import MathSceneV3
from app.services.render_projection_v3 import build_render_projection_v3
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def scene_2d() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "projection-2d",
        "revision": 3,
        "problem_text": "projection test",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "point:a", "type": "point_2d", "label": "A", "x": -2, "y": 0},
            {"id": "point:b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
            {"id": "segment:ab", "type": "segment", "label": "AB", "point_ids": ["point:a", "point:b"]},
            {"id": "circle:1", "type": "circle_2d", "label": "c", "center_point_id": "point:a", "radius": 2},
        ],
        "relations": [],
        "annotations": [{
            "id": "ann:eq",
            "type": "equal_marks",
            "target_ids": ["segment:ab"],
            "provenance": "computed",
        }],
        "audit": {"created_by": "manual"},
    })


def scene_3d() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "projection-3d",
        "revision": 1,
        "problem_text": "projection 3d",
        "topic": "coordinate_3d",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"id": "o", "type": "point_3d", "label": "O", "x": 0, "y": 0, "z": 0},
            {"id": "a", "type": "point_3d", "label": "A", "x": 1, "y": 0, "z": 0},
            {"id": "oa", "type": "segment", "label": "OA", "point_ids": ["o", "a"]},
            {"id": "sphere", "type": "sphere", "center_point_id": "o", "radius": 4},
        ],
        "relations": [],
        "audit": {"created_by": "manual"},
    })


def test_projection_is_deterministic_and_renderer_does_not_infer_semantics():
    first = build_render_projection_v3(scene_2d())
    second = build_render_projection_v3(scene_2d())
    commands = build_geogebra_commands_v3(first)

    assert first == second
    assert first.object_names == {
        "point:a": "A",
        "point:b": "B",
        "segment:ab": "AB",
        "circle:1": "c",
    }
    assert first.annotations == []
    assert "A = (-2, 0)" in commands
    assert "AB = Segment(A, B)" in commands
    assert not any("Intersect(" in command for command in commands)
    assert not any("SetDecoration" in command for command in commands)


def test_three_projection_uses_stable_ids_and_bounds_include_sphere():
    projection = build_render_projection_v3(scene_3d())
    payload = build_three_scene_v3(projection)

    assert set(payload["points"]) == {"o", "a"}
    assert payload["segments"][0]["object_id"] == "oa"
    assert payload["segments"][0]["point_ids"] == ["o", "a"]
    assert projection.bounds.minimum == (-4.0, -4.0, -4.0)
    assert projection.bounds.maximum == (4.0, 4.0, 4.0)
    assert projection.bounds.radius == 4


def test_pipeline_attaches_verified_semantic_annotation_to_projection():
    payload = scene_2d().model_dump(mode="json")
    payload["relations"] = [{
        "id": "r:length",
        "type": "distance",
        "operands": [
            {"role": "first", "ref_id": "point:a", "ref_kind": "point"},
            {"role": "second", "ref_id": "point:b", "ref_kind": "point"},
        ],
        "args": {"value": 4},
    }]
    payload["annotations"] = [{
        "id": "ann:length",
        "type": "length",
        "target_ids": ["segment:ab"],
        "label": "4",
        "provenance": "verified",
        "relation_id": "r:length",
    }]

    result = run_scene_pipeline_v3(MathSceneV3.model_validate(payload))

    assert result.status == "verified"
    assert result.projection is not None
    assert [annotation.annotation_id for annotation in result.projection.annotations] == ["ann:length"]
    assert "SetCaption(AB, \"4\")" in build_geogebra_commands_v3(result.projection)


def test_pipeline_reports_renderer_unsupported_at_project_stage():
    payload = scene_2d().model_dump(mode="json")
    payload["renderer"] = "threejs_3d"
    payload["view"]["dimension"] = "3d"

    result = run_scene_pipeline_v3(MathSceneV3.model_validate(payload))

    assert result.status == "failed"
    assert result.projection is None
    assert result.issues[-1].stage == "project"
    assert result.issues[-1].code == "RENDERER_UNSUPPORTED"