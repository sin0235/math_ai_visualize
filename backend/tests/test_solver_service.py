import pytest

from app.services.solver_service import solve


@pytest.fixture
def scene():
    return {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 6},
            {"type": "face", "points": ["B", "C", "E", "D"]},
        ]
    }


def test_solve_point_point_distance(scene):
    result = solve(scene, "d(B,C)")

    assert result.answer == "d(B,C) = 4"
    assert result.steps[1].formula_latex
    assert result.steps[1].substitution_latex
    assert result.steps[2].result_latex == "4"


def test_solve_point_line_distance(scene):
    result = solve(scene, "d(A,BC)")

    assert result.answer == "d(A,BC) = 3"
    assert result.steps[1].kind == "distance_point_line"


def test_solve_point_plane_distance(scene):
    result = solve(scene, "d(A,(BCD))")

    assert result.answer == "d(A,(BCD)) = 3"
    assert result.steps[1].kind == "distance_point_plane"


def test_solve_line_plane_angle(scene):
    result = solve(scene, "Góc giữa BA và (BCD)")

    assert result.answer == "\\angle(BA,(BCD)) = 90°"
    assert result.steps[1].kind == "angle_line_plane"


def test_solve_area(scene):
    result = solve(scene, "S(BCED)")

    assert result.answer == "S(BCED) = 16"


def test_solve_pyramid_volume(scene):
    result = solve(scene, "V(S.BCED)")

    assert result.answer == "V(S.BCED) = 32"


def test_solve_zero_distance_warns_about_scene_geometry(scene):
    result = solve(scene, "d(B,(BCD))")

    assert result.answer == "d(B,(BCD)) = 0"
    assert "đang nằm trên mặt phẳng" in result.warnings[0]


def test_solve_skew_line_distance():
    scene = {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 1},
            {"type": "point_3d", "name": "D", "x": 0, "y": 2, "z": 1},
        ]
    }

    result = solve(scene, "d(AB,CD)")

    assert result.answer == "d(AB,CD) = 1"
    assert result.steps[1].kind == "distance_line_line"


def test_perpendicular_check_rejects_skew_orthogonal_lines():
    scene = {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 1},
            {"type": "point_3d", "name": "D", "x": 0, "y": 2, "z": 1},
        ]
    }

    result = solve(scene, "AB vuông góc CD")

    assert result.answer == "AB vuông góc CD: SAI"
    assert "chéo nhau" in result.warnings[0]


def test_solve_unsupported_returns_warning(scene):
    result = solve(scene, "tính gì đó")

    assert result.answer == "Không xác định"
    assert result.warnings
