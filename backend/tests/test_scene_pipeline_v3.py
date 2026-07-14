from app.schemas.scene_v3 import MathSceneV3
from app.services.scene_pipeline_v3 import affected_relation_ids, run_scene_pipeline_v3


def make_scene(*, perpendicular=True, declared_kind="segment"):
    return MathSceneV3.model_validate({
        "scene_id": "scene_pipeline",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "Hai đoạn vuông góc",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "x": 0, "y": 0},
            {"id": "b", "type": "point_2d", "x": 1, "y": 0},
            {"id": "c", "type": "point_2d", "x": 0, "y": 0},
            {"id": "d", "type": "point_2d", "x": 0 if perpendicular else 1, "y": 1},
            {"id": "ab", "type": "segment", "point_ids": ["a", "b"]},
            {"id": "cd", "type": "segment", "point_ids": ["c", "d"]},
        ],
        "relations": [{
            "id": "r_perp",
            "type": "perpendicular",
            "operands": [
                {"role": "first", "ref_id": "ab", "ref_kind": declared_kind},
                {"role": "second", "ref_id": "cd", "ref_kind": "segment"},
            ],
        }],
        "audit": {"created_by": "manual"},
    })


def test_pipeline_attaches_verification_without_mutating_input():
    scene = make_scene()

    result = run_scene_pipeline_v3(scene)

    assert result.status == "verified"
    assert result.scene is not scene
    assert scene.relations[0].verification is None
    assert result.scene.relations[0].verification.status == "verified"
    assert result.issues == ()


def test_pipeline_reports_failed_constraint_with_stage_code():
    result = run_scene_pipeline_v3(make_scene(perpendicular=False))

    assert result.status == "failed"
    assert result.requires_user_confirmation
    assert result.issues[0].stage == "verify"
    assert result.issues[0].code == "CONSTRAINT_FAILED"


def test_pipeline_stops_before_verification_on_kind_mismatch():
    result = run_scene_pipeline_v3(make_scene(declared_kind="line"))

    assert result.status == "failed"
    assert not result.can_project
    assert result.verification == ()
    assert any(issue.code == "REFERENCE_KIND_MISMATCH" for issue in result.issues)


def make_line_plane_scene(*, perpendicular=True):
    return MathSceneV3.model_validate({
        "scene_id": "scene_pipeline_line_plane",
        "schema_version": "3.0",
        "revision": 1,
        "problem_text": "SA vuông góc với đáy ABCD",
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"id": "s", "type": "point_3d", "x": 1 if not perpendicular else 0, "y": 0, "z": 2 if perpendicular else 2},
            {"id": "a", "type": "point_3d", "x": 0, "y": 0, "z": 0},
            {"id": "b", "type": "point_3d", "x": 1, "y": 0, "z": 0},
            {"id": "c", "type": "point_3d", "x": 1, "y": 1, "z": 0},
            {"id": "d", "type": "point_3d", "x": 0, "y": 1, "z": 0},
            {"id": "sa", "type": "segment", "point_ids": ["s", "a"]},
            {"id": "abcd", "type": "face", "point_ids": ["a", "b", "c", "d"]},
        ],
        "relations": [{
            "id": "r_line_plane_perp",
            "type": "perpendicular",
            "operands": [
                {"role": "line", "ref_id": "sa", "ref_kind": "segment"},
                {"role": "plane", "ref_id": "abcd", "ref_kind": "face"},
            ],
        }],
        "audit": {"created_by": "manual"},
    })


def test_pipeline_accepts_3d_line_plane_perpendicular_relation():
    result = run_scene_pipeline_v3(make_line_plane_scene())

    assert result.status == "verified"
    assert result.can_project
    assert result.issues == ()
    assert result.scene.relations[0].verification.status == "verified"




def test_pipeline_verifies_failed_3d_line_plane_perpendicular_relation():
    result = run_scene_pipeline_v3(make_line_plane_scene(perpendicular=False))

    assert result.status == "failed"
    # Fail-closed: constraint errors must not project as a successful figure.
    assert not result.can_project
    assert any(issue.code == "CONSTRAINT_FAILED" for issue in result.issues)


def test_pipeline_failed_2d_constraint_blocks_projection():
    result = run_scene_pipeline_v3(make_scene(perpendicular=False))
    assert result.status == "failed"
    assert not result.can_project
    assert result.projection is not None  # projection may be built but can_project is false


def test_pipeline_dependency_query_uses_typed_ids():
    scene = make_scene()

    assert affected_relation_ids(scene, {"ab"}) == frozenset({"r_perp"})
    assert affected_relation_ids(scene, {"a"}) == frozenset({"r_perp"})


def test_pipeline_verifier_error_is_hard_failure_not_soft_warning(monkeypatch):
    """Kernel exceptions must block projection (no stuck unconfirmable workspace)."""
    from app.schemas.scene_v3 import ConstraintResultV3
    import app.services.scene_pipeline_v3 as pipeline

    scene = make_scene()

    def boom(_scene, _index=None):
        return (
            ConstraintResultV3(
                relation_id="r_perp",
                status="error",
                verifier="geometry-kernel-v3",
                message="SyntheticError",
            ),
        )

    monkeypatch.setattr(pipeline, "verify_constraints", boom)
    result = run_scene_pipeline_v3(scene)

    assert result.status == "failed"
    assert not result.can_project
    assert any(
        issue.code == "CONSTRAINT_FAILED" and issue.severity == "error"
        for issue in result.issues
    )
