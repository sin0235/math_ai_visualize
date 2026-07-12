import pytest

from app.schemas.scene_v3 import MathSceneV3
from app.services.geometry_kernel import build_constraint_graph, build_geometry_index, verify_constraints
from app.services.relation_registry import validate_v3_relation_operands


def make_scene(objects, relations):
    return MathSceneV3.model_validate({
        "scene_id": "scene_kernel",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "kernel test",
        "topic": "coordinate_3d",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": objects,
        "relations": relations,
        "audit": {"created_by": "manual"},
    })


def point(identifier, x, y, z=0):
    return {"id": identifier, "type": "point_3d", "label": identifier, "x": x, "y": y, "z": z}


def segment(identifier, start, end):
    return {"id": identifier, "type": "segment", "label": identifier, "point_ids": [start, end]}


def operand(role, ref_id, ref_kind):
    return {"role": role, "ref_id": ref_id, "ref_kind": ref_kind}


def relation(identifier, relation_type, operands, args=None):
    return {"id": identifier, "type": relation_type, "operands": operands, "args": args or {}}


def test_kernel_verifies_perpendicular_and_intersection_by_ids():
    scene = make_scene(
        [
            point("a", -1, 0), point("b", 1, 0), point("c", 0, -1), point("d", 0, 1), point("i", 0, 0),
            segment("ab", "a", "b"), segment("cd", "c", "d"),
        ],
        [
            relation("r_perp", "perpendicular", [operand("first", "ab", "segment"), operand("second", "cd", "segment")]),
            relation("r_intersection", "intersection", [
                operand("result", "i", "point"), operand("first", "ab", "segment"), operand("second", "cd", "segment"),
            ]),
        ],
    )

    results = verify_constraints(scene)

    assert [result.status for result in results] == ["verified", "verified"]
    assert results[1].evidence["point_id"] == "i"


def test_kernel_reports_degenerate_constraint_as_unverifiable():
    scene = make_scene(
        [point("a", 0, 0), point("b", 0, 0), point("c", 0, 1), segment("ab", "a", "b"), segment("ac", "a", "c")],
        [relation("r", "perpendicular", [operand("first", "ab", "segment"), operand("second", "ac", "segment")])],
    )

    result = verify_constraints(scene)[0]

    assert result.status == "unverifiable"
    assert "suy biến" in (result.message or "")


def test_distance_tolerance_scales_with_scene_not_fixed_coordinates():
    scene = make_scene(
        [point("a", 0, 0), point("b", 1_000_000, 0), point("p", 500_000, 0.05), segment("ab", "a", "b")],
        [relation("r", "on_line", [operand("point", "p", "point"), operand("line", "ab", "segment")])],
    )

    index = build_geometry_index(scene)
    result = verify_constraints(scene, index)[0]

    assert index.tolerance == pytest.approx(0.1)
    assert result.status == "verified"


def test_kernel_does_not_mutate_scene():
    scene = make_scene(
        [point("a", 0, 0), point("b", 2, 0), point("m", 1, 0), segment("ab", "a", "b")],
        [relation("r", "midpoint", [operand("point", "m", "point"), operand("segment", "ab", "segment")])],
    )
    before = scene.model_dump(mode="json")

    verify_constraints(scene)

    assert scene.model_dump(mode="json") == before
    assert scene.relations[0].verification is None


def test_constraint_graph_returns_only_relations_affected_by_object():
    scene = make_scene(
        [point("a", 0, 0), point("b", 2, 0), point("m", 1, 0), point("c", 0, 1), segment("ab", "a", "b"), segment("ac", "a", "c")],
        [
            relation("r_mid", "midpoint", [operand("point", "m", "point"), operand("segment", "ab", "segment")]),
            relation("r_perp", "perpendicular", [operand("first", "ab", "segment"), operand("second", "ac", "segment")]),
        ],
    )

    graph = build_constraint_graph(scene)

    assert graph.affected_relations({"m"}) == frozenset({"r_mid"})
    assert graph.affected_relations({"a"}) == frozenset({"r_mid", "r_perp"})
    assert graph.affected_relations({"ab"}) == frozenset({"r_mid", "r_perp"})


def test_registry_rejects_wrong_operand_shape_and_dimension():
    errors = validate_v3_relation_operands("on_plane", ["point", "line"], "2d")

    assert any("dimension=2d" in error for error in errors)
    assert any("kind=planar" in error for error in errors)