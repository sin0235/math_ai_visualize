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


def test_solve_line_equation(scene):
    result = solve(scene, "viết phương trình đường thẳng AC")

    assert result.answer.startswith("d_{AC}:")
    assert result.steps[1].kind == "equation_line"
    assert "x=0+4t" in result.steps[2].result_latex


def test_solve_plane_equation(scene):
    result = solve(scene, "pt mặt phẳng (BCD)")

    assert result.answer.startswith("(BCD):")
    assert result.steps[1].kind == "equation_plane"
    assert result.steps[2].result_latex.endswith("=0")


def test_solve_dot_product(scene):
    result = solve(scene, "BA . BC")

    assert result.answer == "\\overrightarrow{BA}\\cdot\\overrightarrow{BC} = 0"
    assert result.steps[1].kind == "vector_dot"


def test_solve_cross_product(scene):
    result = solve(scene, "BC × BD")

    assert result.answer.startswith("\\overrightarrow{BC}\\times\\overrightarrow{BD}")
    assert result.steps[1].kind == "vector_cross"
    assert result.steps[2].result_latex


def test_solve_projection_point_plane(scene):
    result = solve(scene, "hình chiếu của A lên (BCD)")

    assert result.answer == "H(0,0,0)"
    assert result.steps[1].kind == "projection_point_plane"


def test_solve_reflection_point_plane(scene):
    result = solve(scene, "đối xứng A qua (BCD)")

    assert result.answer == "A'(0,0,-3)"
    assert result.steps[1].kind == "reflection_point_plane"


def test_solve_collinear_false(scene):
    result = solve(scene, "A B C thẳng hàng?")

    assert result.answer == "ABC thẳng hàng: SAI"
    assert result.steps[1].kind == "proof_collinear"


def test_solve_coplanar_true(scene):
    result = solve(scene, "B C D E đồng phẳng?")

    assert result.answer == "BCDE đồng phẳng: ĐÚNG"
    assert result.steps[1].kind == "proof_coplanar"


def test_solve_unsupported_returns_warning(scene):
    result = solve(scene, "tính gì đó")

    assert result.answer == "Không xác định"
    assert result.warnings
