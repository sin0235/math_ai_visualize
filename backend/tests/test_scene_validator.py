"""Tests cho scene_validator: pre-validate raw + post-Pydantic semantic checks."""

from app.schemas.scene import MathScene
from app.services.scene_validator import pre_validate_raw, validate_and_repair


def _base_scene(**overrides) -> dict:
    base = {
        "problem_text": "test",
        "renderer": "threejs_3d",
        "topic": "solid_geometry",
        "view": {"dimension": "3d"},
        "objects": [],
        "relations": [],
        "annotations": [],
        "parameters": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# pre_validate_raw
# ---------------------------------------------------------------------------


def test_pre_validate_drops_invalid_object_type():
    raw = _base_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "circle_3d", "name": "C", "center": "A", "radius": 1},  # not in schema
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
        ]
    )
    cleaned, warnings = pre_validate_raw(raw)
    assert len(cleaned["objects"]) == 2
    assert any("type='circle_3d'" in w for w in warnings)


def test_pre_validate_drops_invalid_relation_type():
    raw = _base_scene(
        relations=[
            {"type": "perpendicular", "object_1": "AB", "object_2": "CD"},
            {"type": "magic", "object_1": "X"},
        ]
    )
    cleaned, warnings = pre_validate_raw(raw)
    assert len(cleaned["relations"]) == 1
    assert any("magic" in w for w in warnings)


def test_pre_validate_normalizes_relation_type_case():
    raw = _base_scene(
        relations=[
            {"type": "  Perpendicular ", "object_1": "AB", "object_2": "CD"},
        ]
    )
    cleaned, _ = pre_validate_raw(raw)
    assert cleaned["relations"][0]["type"] == "perpendicular"


def test_pre_validate_drops_invalid_annotation_type():
    raw = _base_scene(
        annotations=[
            {"type": "length", "target": "A-B", "label": "3"},
            {"type": "tooltip", "target": "A"},
        ]
    )
    cleaned, warnings = pre_validate_raw(raw)
    assert len(cleaned["annotations"]) == 1
    assert any("tooltip" in w for w in warnings)


# ---------------------------------------------------------------------------
# validate_and_repair: naming uniqueness
# ---------------------------------------------------------------------------


def test_numeric_quality_warns_near_duplicate_points():
    scene = MathScene.model_validate(_base_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1e-9, "y": 0, "z": 0},
        ]
    ))
    report = validate_and_repair(scene)
    assert any("gần trùng" in warning for warning in report.warnings)


def test_dedupe_duplicate_point_names():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "A", "x": 5, "y": 0, "z": 0},  # trùng
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            ]
        )
    )
    report = validate_and_repair(scene)
    names = [o.name for o in report.scene.objects if hasattr(o, "name")]
    assert names.count("A") == 1
    assert any("trùng tên" in r for r in report.repairs)


# ---------------------------------------------------------------------------
# validate_and_repair: reference integrity
# ---------------------------------------------------------------------------


def test_reference_integrity_drops_segment_with_missing_point():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
                {"type": "segment", "name": "AB", "points": ["A", "B"]},
                {"type": "segment", "name": "AC", "points": ["A", "C"]},  # C không tồn tại
            ]
        )
    )
    report = validate_and_repair(scene)
    types = [o.type for o in report.scene.objects]
    assert types.count("segment") == 1
    assert any("không tồn tại" in r for r in report.repairs)


def test_reference_integrity_drops_relation_with_missing_point():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            ],
            relations=[
                {"type": "perpendicular", "object_1": "AB", "object_2": "CD"},
            ],
        )
    )
    report = validate_and_repair(scene)
    assert len(report.scene.relations) == 0
    assert any("CD" in w or "C" in w or "D" in w for w in report.warnings)


def test_reference_integrity_drops_annotation_with_missing_arms():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            ],
            annotations=[
                {
                    "type": "right_angle",
                    "target": "A",
                    "metadata": {"arms": ["B", "Z"]},  # Z không tồn tại
                },
            ],
        )
    )
    report = validate_and_repair(scene)
    assert len(report.scene.annotations) == 0


# ---------------------------------------------------------------------------
# validate_and_repair: dimension consistency
# ---------------------------------------------------------------------------


def test_dimension_warning_2d_renderer_with_3d_point():
    scene = MathScene.model_validate(
        _base_scene(
            renderer="geogebra_2d",
            view={"dimension": "2d"},
            objects=[
                {"type": "point_2d", "name": "A", "x": 0, "y": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            ],
        )
    )
    report = validate_and_repair(scene)
    assert any("geogebra_2d" in w and "point_3d" in w for w in report.warnings)


# ---------------------------------------------------------------------------
# validate_and_repair: geometry sanity
# ---------------------------------------------------------------------------


def test_geometry_drops_zero_segment():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "segment", "points": ["A", "A"]},
            ]
        )
    )
    report = validate_and_repair(scene)
    types = [o.type for o in report.scene.objects]
    assert "segment" not in types


def test_geometry_drops_invalid_sphere_radius():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
                {"type": "sphere", "name": "S", "center": "O", "radius": -1},
            ]
        )
    )
    report = validate_and_repair(scene)
    assert all(o.type != "sphere" for o in report.scene.objects)


def test_geometry_drops_face_with_too_few_points():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
                {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
                # Pydantic min_length=3 đã chặn từ trước, nhưng test trùng điểm
                {"type": "face", "name": "ABA", "points": ["A", "B", "A"]},
            ]
        )
    )
    report = validate_and_repair(scene)
    assert all(o.type != "face" for o in report.scene.objects)


def test_geometry_drops_invalid_function_graph():
    scene = MathScene.model_validate(
        _base_scene(
            renderer="geogebra_2d",
            view={"dimension": "2d"},
            topic="function_graph",
            objects=[
                {"type": "function_graph", "name": "f", "expression": "  "},
            ],
        )
    )
    report = validate_and_repair(scene)
    assert all(o.type != "function_graph" for o in report.scene.objects)


# ---------------------------------------------------------------------------
# validate_and_repair: parameter integrity
# ---------------------------------------------------------------------------


def test_parameter_clamps_default():
    scene = MathScene.model_validate(
        _base_scene(
            parameters=[
                {"name": "a", "min": 1, "max": 5, "default": 10, "step": 0.5},
            ],
        )
    )
    report = validate_and_repair(scene)
    a = next(p for p in report.scene.parameters if p.name == "a")
    assert a.default == 5.0
    assert any("clamp" in r.lower() for r in report.repairs)


def test_parameter_drops_reserved_name():
    scene = MathScene.model_validate(
        _base_scene(
            parameters=[
                {"name": "pi", "min": 1, "max": 5, "default": 3, "step": 0.5},
            ],
        )
    )
    report = validate_and_repair(scene)
    assert all(p.name != "pi" for p in report.scene.parameters)


def test_expr_drops_unknown_variable():
    scene = MathScene.model_validate(
        _base_scene(
            parameters=[{"name": "a", "min": 1, "max": 5, "default": 3, "step": 0.5}],
            objects=[
                {
                    "type": "point_3d",
                    "name": "A",
                    "x": 3.0,
                    "y": 0.0,
                    "z": 0.0,
                    "x_expr": "a",  # ok
                    "y_expr": "k",  # k chưa khai báo
                },
            ],
        )
    )
    report = validate_and_repair(scene)
    a = next(o for o in report.scene.objects if getattr(o, "name", None) == "A")
    assert a.x_expr == "a"
    assert a.y_expr is None
    assert any("y_expr" in r and "k" in r for r in report.repairs)


# ---------------------------------------------------------------------------
# validate_and_repair: annotation shape
# ---------------------------------------------------------------------------


def test_annotation_target_abc_split_to_arms():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
                {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
            ],
            annotations=[
                # LLM thường viết target='ABC' không có arms
                {"type": "right_angle", "target": "ABC", "metadata": {}},
            ],
        )
    )
    report = validate_and_repair(scene)
    ann = report.scene.annotations[0]
    assert ann.target == "B"
    assert ann.metadata.get("arms") == ["A", "C"]


def test_annotation_segment_target_normalized():
    scene = MathScene.model_validate(
        _base_scene(
            objects=[
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            ],
            annotations=[
                {"type": "length", "target": "AB", "label": "1"},
            ],
        )
    )
    report = validate_and_repair(scene)
    assert report.scene.annotations[0].target == "A-B"


# ---------------------------------------------------------------------------
# E2E: pre_validate + Pydantic + validate_and_repair
# ---------------------------------------------------------------------------


def test_e2e_full_pipeline():
    """Một scene "bẩn" tổng hợp nhiều lỗi LLM thường gặp."""
    raw = _base_scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "A", "x": 5, "y": 0, "z": 0},  # trùng tên
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},  # midpoint sai
            {"type": "magic_object", "name": "?"},  # type lạ
            {"type": "segment", "points": ["A", "Z"]},  # Z không tồn tại
            {"type": "segment", "points": ["A", "B"]},
        ],
        relations=[
            {"type": "midpoint", "object_1": "M", "object_2": "A-B"},
            {"type": "perpendicular", "object_1": "AB", "object_2": "ZZ"},  # Z thiếu
        ],
        annotations=[
            {"type": "length", "target": "AB", "label": "4"},  # cần normalize
        ],
    )

    cleaned, pre_warnings = pre_validate_raw(raw)
    scene = MathScene.model_validate(cleaned)
    report = validate_and_repair(scene)

    # Type lạ bị drop ở pre-validate
    assert any("magic_object" in w for w in pre_warnings)
    # A trùng đã được dedupe
    points_a = [o for o in report.scene.objects if getattr(o, "name", None) == "A"]
    assert len(points_a) == 1
    # Segment A-Z bị drop vì Z không tồn tại
    segs = [o for o in report.scene.objects if o.type == "segment"]
    assert all(set(s.points) <= {"A", "B", "M"} for s in segs)
    # Relation tham chiếu Z bị drop
    assert all(r.type == "midpoint" for r in report.scene.relations)
    # Annotation target được chuẩn hoá
    assert report.scene.annotations[0].target == "A-B"
