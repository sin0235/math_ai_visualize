from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_equation_solver_solves_quadratic():
    result = solve_algebra(AlgebraSolveRequest(input="x^2 - 5*x + 6 = 0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"2", "3"}
    assert result.verification.status == "verified"
    assert result.steps


def test_equation_solver_reports_empty_solution_set():
    result = solve_algebra(AlgebraSolveRequest(input="1/(x-1)=0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "empty"
    assert "Vô nghiệm" in result.answer
    assert any("x - 1" in assumption for assumption in result.assumptions)


def test_equation_solver_filters_extraneous_sqrt_solution():
    result = solve_algebra(AlgebraSolveRequest(input="sqrt(x+1)=x-1"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"3"}
    assert result.verification.status == "verified"


def test_equation_solver_splits_factored_denominator_assumptions():
    result = solve_algebra(AlgebraSolveRequest(input="1/((x-1)*(x+2))=0"))

    assert "x - 1 khác 0" in result.assumptions
    assert "x + 2 khác 0" in result.assumptions
