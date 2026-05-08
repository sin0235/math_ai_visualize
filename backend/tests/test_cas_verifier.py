from app.schemas.scene import MathScene
from app.services.cas_verifier import auto_fix_scene, verify_scene


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
