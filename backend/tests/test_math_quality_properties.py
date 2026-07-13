from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra.service import solve_algebra_deterministic
from app.services.solver_service import solve


def test_linear_equation_solution_is_invariant_under_nonzero_scaling():
    original = solve_algebra_deterministic(
        AlgebraSolveRequest(input="2*x + 4 = 10", topic="equation", variables=["x"])
    )
    scaled = solve_algebra_deterministic(
        AlgebraSolveRequest(input="6*x + 12 = 30", topic="equation", variables=["x"])
    )

    assert original.status == scaled.status == "solved"
    assert original.solution_set.text == scaled.solution_set.text
    assert original.verification.status == scaled.verification.status == "verified"


def test_coordinate_distance_is_invariant_under_translation():
    original = {
        "topic": "coordinate_3d",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 1, "y": 2, "z": 3},
            {"type": "point_3d", "name": "B", "x": 4, "y": 6, "z": 3},
        ],
    }
    translated = {
        "topic": "coordinate_3d",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 11, "y": -3, "z": 5},
            {"type": "point_3d", "name": "B", "x": 14, "y": 1, "z": 5},
        ],
    }

    first = solve(original, "d(A,B)")
    second = solve(translated, "d(A,B)")

    assert first.answer == second.answer == "d(A,B) = 5"
    assert first.steps[-1].result_latex == second.steps[-1].result_latex == "5"