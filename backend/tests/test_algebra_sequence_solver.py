from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_sequence_solver_calculates_arithmetic_term():
    result = solve_algebra(AlgebraSolveRequest(input="arithmetic(u1=2,d=3,n=10)", topic="sequence"))

    assert result.status == "solved"
    assert result.topic == "sequence"
    assert result.solution_set.text == "29"
    assert result.verification.status == "verified"


def test_sequence_solver_calculates_arithmetic_sum():
    result = solve_algebra(AlgebraSolveRequest(input="arithmetic_sum(u1=2,d=3,n=10)", topic="sequence"))

    assert result.status == "solved"
    assert result.solution_set.text == "155"


def test_sequence_solver_calculates_geometric_term():
    result = solve_algebra(AlgebraSolveRequest(input="geometric(u1=3,q=2,n=5)", topic="sequence"))

    assert result.status == "solved"
    assert result.solution_set.text == "48"


def test_sequence_solver_calculates_geometric_sum():
    result = solve_algebra(AlgebraSolveRequest(input="geometric_sum(u1=3,q=2,n=5)", topic="sequence"))

    assert result.status == "solved"
    assert result.solution_set.text == "93"
