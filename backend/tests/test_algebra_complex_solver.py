from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_complex_solver_solves_quadratic_over_complex_domain():
    result = solve_algebra(AlgebraSolveRequest(input="z^2 + 1 = 0", topic="complex", variables=["z"], domain="C"))

    assert result.status == "solved"
    assert result.topic == "complex"
    assert {value.text for value in result.solution_set.values} == {"-I", "I"}
    assert result.verification.status == "verified"


def test_complex_solver_evaluates_abs_expression():
    result = solve_algebra(AlgebraSolveRequest(input="Abs(3+4*i)", topic="complex", domain="C"))

    assert result.status == "solved"
    assert result.solution_set.kind == "expression"
    assert result.solution_set.text == "5"
