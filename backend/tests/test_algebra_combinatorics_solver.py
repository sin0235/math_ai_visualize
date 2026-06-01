from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_combinatorics_solver_calculates_combination():
    result = solve_algebra(AlgebraSolveRequest(input="C(10,3)", topic="combinatorics_probability"))

    assert result.status == "solved"
    assert result.topic == "combinatorics_probability"
    assert result.solution_set.text == "120"
    assert result.verification.status == "verified"


def test_combinatorics_solver_calculates_permutation():
    result = solve_algebra(AlgebraSolveRequest(input="A(5,2)", topic="combinatorics_probability"))

    assert result.status == "solved"
    assert result.solution_set.text == "20"


def test_combinatorics_solver_calculates_factorial():
    result = solve_algebra(AlgebraSolveRequest(input="5!", topic="combinatorics_probability"))

    assert result.status == "solved"
    assert result.solution_set.text == "120"


def test_combinatorics_solver_calculates_coefficient():
    result = solve_algebra(AlgebraSolveRequest(input="coefficient((1+x)^5,x,3)", topic="combinatorics_probability"))

    assert result.status == "solved"
    assert result.solution_set.text == "10"
