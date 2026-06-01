from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_exp_log_solver_solves_exponential_equation():
    result = solve_algebra(AlgebraSolveRequest(input="2^(x+1)=8"))

    assert result.status == "solved"
    assert result.topic == "exponential_log"
    assert {value.text for value in result.solution_set.values} == {"2"}
    assert result.verification.status == "verified"


def test_exp_log_solver_solves_log_equation_with_domain():
    result = solve_algebra(AlgebraSolveRequest(input="log(x-1, 2)=3"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"9"}
    assert "x - 1 > 0" in result.assumptions


def test_exp_log_solver_solves_log_sum_equation():
    result = solve_algebra(AlgebraSolveRequest(input="log(x,2)+log(x-2,2)=3"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"4"}
    assert "x > 0" in result.assumptions
    assert "x - 2 > 0" in result.assumptions
