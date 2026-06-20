import csv
from pathlib import Path

from app.schemas.scene import MathScene
from app.services.problem_classifier import classify_render_problem, classify_solve_question
from app.services.solver_service import solve


BENCHMARK_PATH = Path(__file__).with_name("advisory_classifier_benchmark_300.csv")


def _scene(topic: str = "solid_geometry") -> MathScene:
    return MathScene.model_validate(
        {
            "problem_text": "Cho hình chóp S.ABCD có SA vuông góc với đáy.",
            "topic": topic,
            "renderer": "threejs_3d",
            "view": {"dimension": "3d"},
            "objects": [
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
                {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
                {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            ],
        }
    )


def _solve_scene() -> dict:
    return {
        "problem_text": "Cho hệ trục Oxyz với các điểm A, B, C, D.",
        "topic": "coordinate_3d",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
        ],
    }


def test_classify_render_uses_scene_topic_before_keywords():
    classification = classify_render_problem("Vẽ hình chóp S.ABCD", 12, _scene())

    assert classification.domain == "geometry"
    assert classification.topic == "solid_geometry"
    assert classification.task_type == "render_scene"
    assert classification.confidence >= 0.8
    assert "scene.topic=solid_geometry" in classification.signals


def test_classify_render_detects_function_graph_without_scene():
    classification = classify_render_problem("Vẽ đồ thị hàm số y = x^2 - 1", 12)

    assert classification.domain == "function"
    assert classification.topic == "function_graph"
    assert classification.sub_type == "function_plot"
    assert classification.confidence >= 0.7


def test_classify_solve_uses_deterministic_step_kind():
    scene = _solve_scene()
    result = solve(scene, "d(A,(BCD))")
    classification = classify_solve_question("d(A,(BCD))", scene, result)

    assert classification.task_type == "distance"
    assert classification.sub_type == "point_plane"
    assert classification.supported_by_current_solver is True
    assert "step.kind=distance_point_plane" in classification.signals


def test_classify_solve_marks_unsupported_question():
    scene = _solve_scene()
    result = solve(scene, "hãy giải thích ý nghĩa hình học")
    classification = classify_solve_question("hãy giải thích ý nghĩa hình học", scene, result)

    assert classification.task_type == "unknown"
    assert classification.supported_by_current_solver is False
    assert classification.confidence <= 0.3


def test_classifier_benchmark_csv_has_expected_coverage():
    rows = list(csv.DictReader(BENCHMARK_PATH.open(encoding="utf-8")))

    assert len(rows) == 300
    assert {row["mode"] for row in rows} == {"render", "solve"}

    for row in rows:
        if row["mode"] == "render":
            classification = classify_render_problem(row["input"], 12)
            assert classification.topic == row["expected_topic"]
            assert classification.task_type == row["expected_task_type"]
        else:
            classification = classify_solve_question(row["input"], {"topic": row["scene_topic"]})
            assert classification.task_type == row["expected_task_type"]
            expected_sub_type = row["expected_sub_type"] or None
            assert classification.sub_type == expected_sub_type
