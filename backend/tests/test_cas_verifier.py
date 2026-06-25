from app.schemas.scene import MathScene
from app.services.cas_verifier import auto_fix_scene, infer_point_coordinates, verify_scene


def _make_scene(objects, relations=None) -> MathScene:
    return MathScene.model_validate(
        {
            "problem_text": "test",
            "renderer": "threejs_3d",
            "topic": "solid_geometry",
            "view": {"dimension": "3d"},
            "objects": objects,
            "relations": relations or [],
        }
    )


def test_perpendicular_segment_to_plane_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 4},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 4},
            {"type": "point_3d", "name": "S", "x": 0, "y": 3, "z": 0},
        ],
        relations=[
            {"type": "perpendicular", "object_1": "SA", "object_2": "plane(ABCD)"},
        ],
    )
    assert verify_scene(scene) == []


def test_perpendicular_segment_to_plane_violated():
    # SA tilted: not vertical to plane ABCD on Y=0
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 4},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 4},
            {"type": "point_3d", "name": "S", "x": 1, "y": 3, "z": 1},
        ],
        relations=[
            {"type": "perpendicular", "object_1": "SA", "object_2": "plane(ABCD)"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "perpendicular"


def test_perpendicular_two_segments():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
        ],
        relations=[{"type": "perpendicular", "object_1": "AB", "object_2": "AC"}],
    )
    assert verify_scene(scene) == []


def test_parallel_3d_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 1, "z": 0},
        ],
        relations=[{"type": "parallel", "object_1": "AB", "object_2": "CD"}],
    )
    issues = verify_scene(scene)
    assert any(i.relation_type == "parallel" for i in issues)


def test_equal_length_ok_and_violated():
    scene_ok = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 3, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 3, "z": 0},
        ],
        relations=[{"type": "equal_length", "object_1": "AB", "object_2": "AC"}],
    )
    assert verify_scene(scene_ok) == []

    scene_bad = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 3, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 5, "z": 0},
        ],
        relations=[{"type": "equal_length", "object_1": "AB", "object_2": "AC"}],
    )
    assert any(i.relation_type == "equal_length" for i in verify_scene(scene_bad))


def test_midpoint_inference_preserves_exact_expression():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0, "x_expr": "0", "y_expr": "0", "z_expr": "0"},
            {"type": "point_3d", "name": "B", "x": 3, "y": 0, "z": 0, "x_expr": "3", "y_expr": "0", "z_expr": "0"},
            {"type": "point_3d", "name": "M", "x": 0, "y": 0, "z": 0},
        ],
        relations=[{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
    )
    fixed, issues = infer_point_coordinates(scene)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    assert any(i.auto_fixed and i.relation_type == "midpoint" for i in issues)
    assert m.x == 1.5
    assert m.x_expr == "3/2"


def test_on_line_inference_with_parameter_t():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 0, "y": 0, "z": 0},
        ],
        relations=[{"type": "on_line", "object_1": "P", "object_2": "A-B", "metadata": {"t": "1/4"}}],
    )
    fixed, _ = infer_point_coordinates(scene)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert p.x == 1.0
    assert p.x_expr == "1"


def test_on_plane_inference_solves_one_axis():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 1},
            {"type": "point_3d", "name": "P", "x": 0.5, "y": 0.5, "z": 9},
        ],
        relations=[{"type": "on_plane", "object_1": "P", "object_2": "plane(ABC)"}],
    )
    fixed, _ = infer_point_coordinates(scene)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert p.z == 0.5
    assert p.z_expr == "1/2"


def test_on_plane_inference_prefers_smallest_displacement_not_largest():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": -1},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": -1},
            {"type": "point_3d", "name": "P", "x": 100, "y": -100, "z": 1},
        ],
        relations=[{"type": "on_plane", "object_1": "P", "object_2": "plane(ABC)"}],
    )
    fixed, _ = infer_point_coordinates(scene)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert p.x == 100
    assert p.y == -100
    assert p.z == 0



def test_inference_does_not_guess_underdetermined_relation():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 1, "y": 1, "z": 0},
        ],
        relations=[{"type": "on_line", "object_1": "P", "object_2": "A-B"}],
    )
    fixed, issues = infer_point_coordinates(scene)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert issues == []
    assert p.y == 1


def test_midpoint_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            # M lệch khỏi trung điểm thật (2,0,0)
            {"type": "point_3d", "name": "M", "x": 1, "y": 0.5, "z": 0},
        ],
        relations=[{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.relation_type == "midpoint" and i.auto_fixed for i in issues)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    assert m.x == 2.0 and m.y == 0.0 and m.z == 0.0


def test_auto_fix_does_not_move_given_locked_or_user_edited_point():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0.5, "z": 0, "source": "given", "locked": True},
        ],
        relations=[{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
    )
    fixed, issues = auto_fix_scene(scene)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    assert m.x == 1 and m.y == 0.5 and m.z == 0
    assert any(i.relation_type == "midpoint" and not i.auto_fixed and i.metadata.get("requires_confirmation") for i in issues)



def test_midpoint_already_correct_no_change():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 2, "y": 0, "z": 0},
        ],
        relations=[{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert issues == []
    assert fixed.objects[2].x == 2.0


def test_midpoint_2d():
    scene = MathScene.model_validate(
        {
            "problem_text": "tam giác trung tuyến",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "B", "x": 0, "y": 0},
                {"type": "point_2d", "name": "C", "x": 6, "y": 0},
                {"type": "point_2d", "name": "M", "x": 0, "y": 0},
            ],
            "relations": [{"type": "midpoint", "object_1": "M", "object_2": "B-C"}],
        }
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.auto_fixed for i in issues)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    assert m.x == 3.0 and m.y == 0.0


# ---------------------------------------------------------------------------
# Verifiers mới: collinear, coplanar, on_line, on_plane, on_sphere, on_circle,
# tangent, distance, angle.
# ---------------------------------------------------------------------------


def test_collinear_ok_and_violated():
    scene_ok = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 3, "y": 0, "z": 0},
        ],
        relations=[{"type": "collinear", "object_1": "A,B,C"}],
    )
    assert verify_scene(scene_ok) == []

    scene_bad = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
        ],
        relations=[{"type": "collinear", "object_1": "A,B,C"}],
    )
    issues = verify_scene(scene_bad)
    assert any(i.relation_type == "collinear" for i in issues)


def test_coplanar_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 1},
        ],
        relations=[{"type": "coplanar", "object_1": "A,B,C,D"}],
    )
    issues = verify_scene(scene)
    assert any(i.relation_type == "coplanar" for i in issues)


def test_on_line_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            # H lệch khỏi đường AB
            {"type": "point_3d", "name": "H", "x": 1, "y": 1, "z": 0},
        ],
        relations=[{"type": "on_line", "object_1": "H", "object_2": "A-B"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.auto_fixed and i.relation_type == "on_line" for i in issues)
    h = next(o for o in fixed.objects if getattr(o, "name", None) == "H")
    # Foot vuông góc của (1,1,0) xuống AB là (1,0,0)
    assert abs(h.x - 1.0) < 1e-9
    assert abs(h.y) < 1e-9
    assert abs(h.z) < 1e-9


def test_on_plane_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
            # H phải nằm trên plane(ABC) tức z=0; ở đây z=2
            {"type": "point_3d", "name": "H", "x": 0.5, "y": 0.5, "z": 2.0},
        ],
        relations=[{"type": "on_plane", "object_1": "H", "object_2": "plane(ABC)"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.auto_fixed and i.relation_type == "on_plane" for i in issues)
    h = next(o for o in fixed.objects if getattr(o, "name", None) == "H")
    assert abs(h.x - 0.5) < 1e-9
    assert abs(h.y - 0.5) < 1e-9
    assert abs(h.z) < 1e-9


def test_on_sphere_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 1, "y": 0, "z": 0},
            {"type": "sphere", "name": "S", "center": "O", "radius": 2.0},
        ],
        relations=[{"type": "on_sphere", "object_1": "P", "object_2": "S"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.auto_fixed and i.relation_type == "on_sphere" for i in issues)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert abs((p.x ** 2 + p.y ** 2 + p.z ** 2) ** 0.5 - 2.0) < 1e-9


def test_on_circle_auto_fix():
    scene = MathScene.model_validate(
        {
            "problem_text": "đường tròn",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "O", "x": 0, "y": 0},
                {"type": "point_2d", "name": "P", "x": 1.5, "y": 0},
                {"type": "circle_2d", "name": "C", "center": "O", "radius": 3.0},
            ],
            "relations": [{"type": "on_circle", "object_1": "P", "object_2": "C"}],
        }
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(i.auto_fixed and i.relation_type == "on_circle" for i in issues)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert abs(p.x - 3.0) < 1e-9 and abs(p.y) < 1e-9


def test_tangent_circle_ok():
    scene = MathScene.model_validate(
        {
            "problem_text": "tiếp tuyến đường tròn",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "O", "x": 0, "y": 0},
                {"type": "point_2d", "name": "A", "x": 3, "y": 0},
                {"type": "point_2d", "name": "T", "x": 3, "y": 5},
                {"type": "circle_2d", "name": "C", "center": "O", "radius": 3},
            ],
            "relations": [{"type": "tangent", "object_1": "A-T", "object_2": "C"}],
        }
    )
    assert verify_scene(scene) == []


def test_tangent_violated():
    scene = MathScene.model_validate(
        {
            "problem_text": "tiếp tuyến sai",
            "renderer": "geogebra_2d",
            "topic": "coordinate_2d",
            "view": {"dimension": "2d"},
            "objects": [
                {"type": "point_2d", "name": "O", "x": 0, "y": 0},
                {"type": "point_2d", "name": "A", "x": 5, "y": 0},
                {"type": "point_2d", "name": "T", "x": 5, "y": 5},
                {"type": "circle_2d", "name": "C", "center": "O", "radius": 3},
            ],
            "relations": [{"type": "tangent", "object_1": "A-T", "object_2": "C"}],
        }
    )
    issues = verify_scene(scene)
    assert any(i.relation_type == "tangent" for i in issues)


def test_distance_value():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 5, "y": 0, "z": 0},
        ],
        relations=[{"type": "distance", "object_1": "A-B", "metadata": {"value": 5}}],
    )
    assert verify_scene(scene) == []

    scene_bad = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
        ],
        relations=[{"type": "distance", "object_1": "A-B", "metadata": {"value": 5}}],
    )
    issues = verify_scene(scene_bad)
    assert any(i.relation_type == "distance" for i in issues)


def test_angle_value():
    # 60° giữa AB và AC
    import math as _math
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {
                "type": "point_3d", "name": "C",
                "x": _math.cos(_math.radians(60)),
                "y": _math.sin(_math.radians(60)),
                "z": 0,
            },
        ],
        relations=[
            {"type": "angle", "object_1": "A-B", "object_2": "A-C", "metadata": {"value": 60}}
        ],
    )
    assert verify_scene(scene) == []

    scene_bad = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
        ],
        relations=[
            {"type": "angle", "object_1": "A-B", "object_2": "A-C", "metadata": {"value": 60}}
        ],
    )
    assert any(i.relation_type == "angle" for i in verify_scene(scene_bad))


def test_optimizer_repairs_equal_length_when_enabled():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 2, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 1, "y": 0, "z": 0},
        ],
        relations=[{"type": "equal_length", "object_1": "A-B", "object_2": "C-D"}],
    )

    fixed, issues = auto_fix_scene(scene, use_optimizer=True)

    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []


def test_optimizer_repairs_angle_when_enabled():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 1, "y": 1, "z": 0},
        ],
        relations=[{"type": "angle", "object_1": "A-B", "object_2": "C-D", "metadata": {"value": 90}}],
    )

    fixed, issues = auto_fix_scene(scene, use_optimizer=True)

    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []


def test_optimizer_repairs_collinear_when_enabled():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 2, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
        ],
        relations=[{"type": "collinear", "object_1": "A,B,C"}],
    )

    fixed, issues = auto_fix_scene(scene, use_optimizer=True)

    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []


def test_optimizer_disabled_explicitly_keeps_residual_issue():
    """Khi caller pass use_optimizer=False, residual issue equal_length giữ nguyên."""
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 2, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 1, "y": 0, "z": 0},
        ],
        relations=[{"type": "equal_length", "object_1": "A-B", "object_2": "C-D"}],
    )

    fixed, issues = auto_fix_scene(scene, use_optimizer=False)

    assert any(issue.relation_type == "equal_length" for issue in issues)
    assert verify_scene(fixed)


def test_optimizer_runs_by_default_and_repairs_equal_length():
    """v2: optimizer ON mặc định — equal_length được fix tự động."""
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 2, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 1, "y": 0, "z": 0},
        ],
        relations=[{"type": "equal_length", "object_1": "A-B", "object_2": "C-D"}],
    )
    fixed, issues = auto_fix_scene(scene)
    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []


def test_face_planarity_violation_is_reported():
    """4 điểm tạo Face nhưng không đồng phẳng → verify_scene phát hiện qua SVD."""
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 1.0},  # lệch khỏi mặt phẳng
            {
                "type": "face",
                "name": "ABCD",
                "points": ["A", "B", "C", "D"],
                "color": "#5da9ff",
                "fill_opacity": 0.4,
            },
        ],
    )
    issues = verify_scene(scene)
    assert any(
        i.relation_type == "planarity"
        and "ABCD" in i.description
        for i in issues
    ), [(i.relation_type, i.description) for i in issues]


def test_face_planarity_holds_when_coplanar():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {
                "type": "face",
                "name": "ABCD",
                "points": ["A", "B", "C", "D"],
                "color": "#5da9ff",
                "fill_opacity": 0.4,
            },
        ],
    )
    issues = verify_scene(scene)
    assert not any(i.relation_type == "planarity" for i in issues)


def test_priority_midpoint_over_on_line():
    """Khi điểm bị cả midpoint và on_line ép, midpoint phải thắng."""
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 8, "y": 0, "z": 0},  # trên line AB
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},  # lệch trung điểm
        ],
        relations=[
            {"type": "midpoint", "object_1": "M", "object_2": "A-B"},
            {"type": "on_line", "object_1": "M", "object_2": "A-C"},
        ],
    )
    fixed, _ = auto_fix_scene(scene)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    # Midpoint của AB là (2,0,0), nằm cũng trên A-C nên cả hai relation đều ok
    assert abs(m.x - 2.0) < 1e-9


# ===========================================================================
# Phase 4 CAS Verifier additions
# ===========================================================================


def test_point_on_segment_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 2, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "point_on_segment", "object_1": "M", "object_2": "A-B"},
        ],
    )
    assert verify_scene(scene) == []


def test_point_on_segment_outside():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 6, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "point_on_segment", "object_1": "P", "object_2": "A-B"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "point_on_segment"
    assert "ngoài đoạn" in issues[0].description


def test_point_on_segment_off_line():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 2, "y": 1, "z": 0},
        ],
        relations=[
            {"type": "point_on_segment", "object_1": "P", "object_2": "A-B"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "point_on_segment"


def test_point_on_segment_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 2, "y": 1, "z": 0},
        ],
        relations=[
            {"type": "point_on_segment", "object_1": "P", "object_2": "A-B"},
        ],
    )
    fixed, _ = auto_fix_scene(scene)
    p = next(o for o in fixed.objects if getattr(o, "name", None) == "P")
    assert abs(p.x - 2.0) < 1e-6
    assert abs(p.y - 0.0) < 1e-6
    assert abs(p.z - 0.0) < 1e-6


def test_line_in_plane_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 2, "y": 2, "z": 0},
        ],
        relations=[
            {"type": "line_in_plane", "object_1": "EA", "object_2": "plane(ABCD)"},
        ],
    )
    assert verify_scene(scene) == []


def test_line_in_plane_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 1, "y": 1, "z": 1},
            {"type": "point_3d", "name": "F", "x": 3, "y": 3, "z": 2},
        ],
        relations=[
            {"type": "line_in_plane", "object_1": "E-F", "object_2": "plane(ABCD)"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "line_in_plane"


def test_parallel_planes_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "F", "x": 4, "y": 0, "z": 3},
            {"type": "point_3d", "name": "G", "x": 4, "y": 4, "z": 3},
            {"type": "point_3d", "name": "H", "x": 0, "y": 4, "z": 3},
        ],
        relations=[
            {"type": "parallel_planes", "object_1": "plane(ABCD)", "object_2": "plane(EFGH)"},
        ],
    )
    assert verify_scene(scene) == []


def test_parallel_plane_plane_alias_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 2},
            {"type": "point_3d", "name": "E", "x": 1, "y": 0, "z": 2},
            {"type": "point_3d", "name": "F", "x": 0, "y": 1, "z": 2},
        ],
        relations=[
            {"type": "parallel_plane_plane", "object_1": "plane(ABC)", "object_2": "plane(DEF)"},
        ],
    )
    assert verify_scene(scene) == []


def test_parallel_planes_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "F", "x": 4, "y": 0, "z": 3},
            {"type": "point_3d", "name": "G", "x": 4, "y": 4, "z": 0},  # tilted
        ],
        relations=[
            {"type": "parallel_planes", "object_1": "plane(ABC)", "object_2": "plane(EFG)"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "parallel_planes"


def test_perpendicular_planes_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},  # normal is (0,0,1)
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "E", "x": 0, "y": 1, "z": 0},
            {"type": "point_3d", "name": "F", "x": 0, "y": 0, "z": 1},  # normal is (1,0,0)
        ],
        relations=[
            {"type": "perpendicular_planes", "object_1": "plane(ABC)", "object_2": "plane(DEF)"},
        ],
    )
    assert verify_scene(scene) == []


def test_perpendicular_plane_plane_alias_ok():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "E", "x": 0, "y": 1, "z": 0},
            {"type": "point_3d", "name": "F", "x": 0, "y": 0, "z": 1},
        ],
        relations=[
            {"type": "perpendicular_plane_plane", "object_1": "plane(ABC)", "object_2": "plane(DEF)"},
        ],
    )
    assert verify_scene(scene) == []


def test_perpendicular_planes_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},  # normal is (0,0,1)
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "E", "x": 1, "y": 0, "z": -1},
            {"type": "point_3d", "name": "F", "x": 0, "y": 1, "z": -1},  # normal is (1,1,1)
        ],
        relations=[
            {"type": "perpendicular_planes", "object_1": "plane(ABC)", "object_2": "plane(DEF)"},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "perpendicular_planes"


def test_ratio_ok_with_value():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "ratio", "object_1": "M", "object_2": "A-B", "metadata": {"value": 0.25}},
        ],
    )
    assert verify_scene(scene) == []


def test_segment_ratio_alias_ok_with_value():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "segment_ratio", "object_1": "M", "object_2": "A-B", "metadata": {"value": 0.25}},
        ],
    )
    assert verify_scene(scene) == []


def test_ratio_violated():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 3, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "ratio", "object_1": "M", "object_2": "A-B", "metadata": {"value": 0.25}},
        ],
    )
    issues = verify_scene(scene)
    assert len(issues) == 1
    assert issues[0].relation_type == "ratio"


def test_ratio_with_colon_notation():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "ratio", "object_1": "M", "object_2": "A-B", "metadata": {"ratio": "1:3"}},
        ],
    )
    assert verify_scene(scene) == []


def test_ratio_auto_fix():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 3, "y": 0, "z": 0},
        ],
        relations=[
            {"type": "ratio", "object_1": "M", "object_2": "A-B", "metadata": {"value": 0.5}},
        ],
    )
    fixed, _ = auto_fix_scene(scene)
    m = next(o for o in fixed.objects if getattr(o, "name", None) == "M")
    assert abs(m.x - 2.0) < 1e-6


def test_optimizer_repairs_parallel_planes():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "F", "x": 4, "y": 0, "z": 3},
            {"type": "point_3d", "name": "G", "x": 4, "y": 4, "z": 3},
            {"type": "point_3d", "name": "H", "x": 0, "y": 4, "z": 3.5},  # tilted by 0.5
        ],
        relations=[
            {"type": "parallel_planes", "object_1": "plane(ABCD)", "object_2": "plane(EFGH)"},
        ],
    )
    fixed, issues = auto_fix_scene(scene, use_optimizer=True)
    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []


def test_optimizer_repairs_perpendicular_planes():
    scene = _make_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},  # normal (0,0,1)
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "E", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "F", "x": 0, "y": 0.1, "z": 1},  # slightly off perpendicular
        ],
        relations=[
            {"type": "perpendicular_planes", "object_1": "plane(ABC)", "object_2": "plane(DEF)"},
        ],
    )
    fixed, issues = auto_fix_scene(scene, use_optimizer=True)
    assert any(issue.relation_type == "optimizer" and issue.auto_fixed for issue in issues)
    assert verify_scene(fixed) == []

