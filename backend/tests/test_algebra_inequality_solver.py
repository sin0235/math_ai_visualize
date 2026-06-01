from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_inequality_solver_solves_polynomial_interval():
    result = solve_algebra(AlgebraSolveRequest(input="x^2 - 1 >= 0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "interval"
    assert "(-∞; -1]" in result.solution_set.text
    assert "[1; +∞)" in result.solution_set.text
    assert result.verification.status == "verified"
    assert any(step.kind == "verify" and "Dấu trên từng khoảng" in step.explanation for step in result.steps)


def test_inequality_solver_solves_rational_interval_with_domain_assumption():
    result = solve_algebra(AlgebraSolveRequest(input="(x-1)/(x+2) < 0"))

    assert result.status == "solved"
    assert "(-2; 1)" in result.solution_set.text
    assert any("x + 2" in assumption for assumption in result.assumptions)
