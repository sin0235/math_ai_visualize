"""E2E test cho pipeline build_scene_with_cas_fix.

Pre-validate → normalize → Pydantic → scene_validator → cas_verifier.
Bao gồm:
  - Drop object/relation/annotation có type lỗi.
  - Auto-fix midpoint sai vị trí.
  - Auto-fix on_line / on_plane / on_sphere.
  - Drop reference đến điểm không tồn tại.
  - Tách annotation 'ABC' → target='B', arms=['A','C'].
"""

from app.services.extractor import build_scene_with_cas_fix


def _scene(**overrides) -> dict:
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


def test_pipeline_drops_invalid_types_and_keeps_good():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "alien_object", "name": "X"},  # type lạ
            {"type": "segment", "name": "AB", "points": ["A", "B"]},
        ],
        relations=[
            {"type": "perpendicular", "object_1": "AB", "object_2": "BC"},  # BC ko tồn tại
        ],
    )
    scene, warns = build_scene_with_cas_fix(raw)
    types = [o.type for o in scene.objects]
    assert "point_3d" in types
    assert "segment" in types
    assert "alien_object" not in types
    assert all(r.type != "perpendicular" or "BC" not in (r.object_2 or "") for r in scene.relations)
    assert any("alien_object" in w for w in warns)


def test_pipeline_autofix_midpoint():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1.0, "y": 0.0, "z": 0.0},  # sai
        ],
        relations=[
            {"type": "midpoint", "object_1": "M", "object_2": "A-B"},
        ],
    )
    scene, warns = build_scene_with_cas_fix(raw)
    M = next(o for o in scene.objects if getattr(o, "name", None) == "M")
    assert abs(M.x - 2.0) < 1e-6 and abs(M.y) < 1e-6 and abs(M.z) < 1e-6
    assert any("midpoint" in w.lower() and "tự sửa" in w.lower() for w in warns)


def test_pipeline_does_not_mark_relation_metadata_verified_after_cas():
    raw = _scene(
        problem_text="AB vuông góc BC.",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
        ],
        relations=[
            {"type": "perpendicular", "object_1": "AB", "object_2": "BC"},
        ],
    )

    scene, _ = build_scene_with_cas_fix(raw)

    metadata = scene.relations[0].metadata
    assert metadata["source"] == "inferred"
    assert metadata["confidence"] == "partial"
    assert "verified_by" not in metadata


def test_pipeline_autofix_on_line():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "P", "x": 2, "y": 1, "z": 0},  # ngoài đoạn
        ],
        relations=[
            {"type": "on_line", "object_1": "P", "object_2": "A-B"},
        ],
    )
    scene, _ = build_scene_with_cas_fix(raw)
    P = next(o for o in scene.objects if getattr(o, "name", None) == "P")
    # Foot vuông góc: (2, 0, 0)
    assert abs(P.x - 2.0) < 1e-6
    assert abs(P.y) < 1e-6
    assert abs(P.z) < 1e-6


def test_pipeline_autofix_on_sphere():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
            {"type": "sphere", "name": "S", "center": "O", "radius": 5},
            {"type": "point_3d", "name": "P", "x": 3, "y": 0, "z": 0},  # cách 3 ≠ 5
        ],
        relations=[
            {"type": "on_sphere", "object_1": "P", "object_2": "S"},
        ],
    )
    scene, _ = build_scene_with_cas_fix(raw)
    P = next(o for o in scene.objects if getattr(o, "name", None) == "P")
    dist = (P.x ** 2 + P.y ** 2 + P.z ** 2) ** 0.5
    assert abs(dist - 5.0) < 1e-6


def test_pipeline_normalizes_annotation_abc():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
        ],
        annotations=[
            {"type": "right_angle", "target": "ABC"},
        ],
    )
    scene, _ = build_scene_with_cas_fix(raw)
    assert len(scene.annotations) == 1
    ann = scene.annotations[0]
    assert ann.target == "B"
    assert ann.metadata.get("arms") == ["A", "C"]


def test_pipeline_dedupes_duplicate_points():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "A", "x": 9, "y": 9, "z": 9},  # trùng
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
        ],
    )
    scene, warns = build_scene_with_cas_fix(raw)
    a_points = [o for o in scene.objects if getattr(o, "name", None) == "A"]
    assert len(a_points) == 1
    assert a_points[0].x == 0  # giữ object đầu
    assert any("trùng tên" in w for w in warns)


def test_pipeline_drops_invalid_sphere():
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
            {"type": "sphere", "name": "S1", "center": "O", "radius": -3},
        ],
    )
    scene, warns = build_scene_with_cas_fix(raw)
    assert all(o.type != "sphere" for o in scene.objects)
    assert any("radius" in w.lower() for w in warns)


def test_pipeline_full_messy_scene():
    """Combo: type lỗi + trùng tên + reference lỗi + midpoint sai + annotation lỗi."""
    raw = _scene(
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "A", "x": 5, "y": 5, "z": 5},  # trùng
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "M", "x": 1, "y": 0, "z": 0},  # sẽ bị fix → (2,0,0)
            {"type": "noise", "name": "?"},  # type lỗi
            {"type": "segment", "points": ["A", "B"]},
            {"type": "segment", "points": ["A", "Z"]},  # Z không tồn tại
        ],
        relations=[
            {"type": "midpoint", "object_1": "M", "object_2": "A-B"},
            {"type": "perpendicular", "object_1": "AB", "object_2": "QQ"},  # Q ko tồn tại
        ],
        annotations=[
            {"type": "right_angle", "target": "ABC"},
            {"type": "tooltip", "target": "A"},  # type ko hợp lệ
        ],
    )
    scene, warns = build_scene_with_cas_fix(raw)

    # Type lỗi đã bị drop từ pre-validate
    assert all(o.type != "noise" for o in scene.objects)
    # Annotation tooltip bị drop
    assert all(a.type != "tooltip" for a in scene.annotations)
    # Trùng tên A: chỉ còn 1 (giữ object đầu)
    a_points = [o for o in scene.objects if getattr(o, "name", None) == "A"]
    assert len(a_points) == 1 and a_points[0].x == 0
    # Segment A-Z bị drop vì Z không tồn tại
    segs = [o for o in scene.objects if o.type == "segment"]
    assert all(set(s.points) == {"A", "B"} for s in segs)
    # Relation perpendicular tham chiếu QQ → drop
    assert all(r.type != "perpendicular" for r in scene.relations)
    # M được auto-fix về (2,0,0)
    M = next(o for o in scene.objects if getattr(o, "name", None) == "M")
    assert abs(M.x - 2.0) < 1e-6
    # Annotation right_angle 'ABC' đã được tách
    rang = next(a for a in scene.annotations if a.type == "right_angle")
    assert rang.target == "B"
    assert rang.metadata.get("arms") == ["A", "C"]
    # Có warnings
    assert len(warns) >= 4
