from app.services.extractor import build_scene_with_cas_fix
from app.services.solver_service import solve


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


def _distance_scene(annotation_metadata: dict) -> dict:
    return _scene(
        problem_text="Cho điểm A cách mặt phẳng (BCD) một khoảng 3.",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
        ],
        annotations=[
            {
                "type": "length",
                "target": "A-B",
                "label": "3",
                "metadata": annotation_metadata,
            }
        ],
        relations=[
            {
                "type": "perpendicular",
                "object_1": "AB",
                "object_2": "plane(BCD)",
                "metadata": {
                    "source": "given",
                    "confidence": "partial",
                    "evidence": "A cách mặt phẳng (BCD) một khoảng 3",
                },
            }
        ],
    )


def test_phase5_classical_solver_accepts_given_metric_pipeline_scene():
    scene, warnings = build_scene_with_cas_fix(
        _distance_scene({"source": "given", "confidence": "partial", "evidence": "khoảng 3"})
    )

    result = solve(scene.model_dump(), "d(A,(BCD))", geometry_method="classical")

    assert not any("không tồn tại" in warning for warning in warnings)
    assert result.answer == "d(A,(BCD)) = 3"
    assert result.method == "classical"
    assert result.confidence == "verified"
    assert any(fact["source"] == "given" and "khoảng 3" in fact["text"] for fact in result.used_facts)
    explanations = " ".join(step.explanation for step in result.steps).lower()
    assert "tọa độ" not in explanations
    assert "phép tính" not in explanations
    assert "ab là đoạn vuông góc" in explanations


def test_phase5_solver_rejects_construction_metric_pipeline_scene():
    scene, _ = build_scene_with_cas_fix(
        _distance_scene({"source": "construction", "confidence": "unverified"})
    )

    result = solve(scene.model_dump(), "d(A,(BCD))", geometry_method="classical")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert result.data_issues


def test_phase5_pipeline_preserves_inferred_source_and_marks_cas_verified():
    raw = _scene(
        problem_text="ABCD là hình vuông.",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 1, "y": 1, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 1, "z": 0},
        ],
        annotations=[
            {
                "type": "length",
                "target": "A-B",
                "label": "1",
                "metadata": {"source": "given", "confidence": "partial", "evidence": "cạnh bằng 1"},
            }
        ],
        relations=[
            {
                "type": "perpendicular",
                "object_1": "AB",
                "object_2": "BC",
                "metadata": {"source": "inferred", "confidence": "partial", "evidence": "ABCD là hình vuông"},
            }
        ],
    )

    scene, _ = build_scene_with_cas_fix(raw)
    result = solve(scene.model_dump(), "góc giữa AB và BC", geometry_method="classical")

    assert scene.relations[0].metadata["source"] == "inferred"
    assert scene.relations[0].metadata["confidence"] == "verified"
    assert result.answer == "\\angle(AB,BC) = 90°"
    assert any(fact["source"] == "verified" and "ABCD là hình vuông" in fact["text"] for fact in result.used_facts)
