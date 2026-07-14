"""NLP normalization for geometry solver questions (Vietnamese natural language)."""

from app.services.geometry.parser import normalize_solver_question, parse_angle_goal, parse_point_plane_distance_goal
from app.services.solver_service import solve


def test_normalize_distance_point_to_plane_vietnamese():
    cases = [
        "Khoảng cách từ điểm M đến mặt phẳng (PFB) bằng bao nhiêu?",
        "Khoảng cách từ điểm (M) đến mặt phẳng ((PFB)) bằng bao nhiêu?",
        "khoảng cách từ M đến mp PFB",
        "d(M,(PFB))",
    ]
    for text in cases:
        assert normalize_solver_question(text) == "d(M,(PFB))", text


def test_parse_point_plane_distance_goal_from_full_problem():
    full = (
        "Cho hình lập phương ABCD.MNPQ cạnh 8. F là trung điểm CD. "
        "Khoảng cách từ điểm (M) đến mặt phẳng ((PFB)) bằng bao nhiêu?"
    )

    assert parse_point_plane_distance_goal(full) == ("M", ("P", "F", "B"))


def test_parse_angle_goal_component_types():
    assert parse_angle_goal("Góc ABC bằng bao nhiêu?").kind == "point_angle"
    assert parse_angle_goal("Tính góc giữa hai đường thẳng AB và CD.").kind == "line_line"
    assert parse_angle_goal("Tính góc giữa MN và mặt phẳng (PFB).").kind == "line_plane"
    assert parse_angle_goal("Tính góc giữa hai mặt phẳng (ABC) và (PFB).").kind == "plane_plane"


def test_normalize_extracts_metric_from_full_problem_text():
    full = (
        "Khoảng cách từ điểm (M) đến mặt phẳng (PFB) bằng bao nhiêu? "
        "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng (18), trong đó (M, N, P, Q) "
        "lần lượt nằm trên các đường thẳng vuông góc với mặt phẳng ((ABCD)) tại (A, B, C, D). "
        "Gọi (F) là trung điểm của đoạn thẳng (CD). "
        "Khoảng cách từ điểm (M) đến mặt phẳng ((PFB)) bằng bao nhiêu?"
    )
    assert normalize_solver_question(full) == "d(M,(PFB))"


def test_solve_cube_distance_m_to_plane_pfb_from_vietnamese():
    a = 18.0
    def pt(name, x, y, z):
        return {"type": "point_3d", "name": name, "id": name, "x": x, "y": y, "z": z, "label": name}

    scene = {
        "scene_id": "cube-mn pq",
        "revision": 1,
        "topic": "solid_geometry",
        "objects": [
            pt("A", 0, 0, 0),
            pt("B", a, 0, 0),
            pt("C", a, a, 0),
            pt("D", 0, a, 0),
            pt("M", 0, 0, a),
            pt("N", a, 0, a),
            pt("P", a, a, a),
            pt("Q", 0, a, a),
            pt("F", a / 2, a, 0),
        ],
        "relations": [],
    }
    question = "Khoảng cách từ điểm M đến mặt phẳng (PFB) bằng bao nhiêu?"
    result = solve(scene, question)
    assert result.answer == r"d(M,(PFB)) = 9 \sqrt{6}"
    assert result.steps
