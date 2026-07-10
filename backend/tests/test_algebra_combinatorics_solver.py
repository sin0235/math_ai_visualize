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


def test_combinatorics_rejects_huge_factorial():
    result = solve_algebra(AlgebraSolveRequest(input="100!", topic="combinatorics_probability"))
    assert result.status == "unsupported"
    assert any("20" in err or "≤" in err or "<=" in err for err in result.errors)


def test_combinatorics_rejects_huge_n():
    result = solve_algebra(AlgebraSolveRequest(input="C(50,3)", topic="combinatorics_probability"))
    assert result.status == "unsupported"
    assert any("30" in err for err in result.errors)


def test_probability_classical_fraction():
    result = solve_algebra(AlgebraSolveRequest(input="P(3/10)", topic="combinatorics_probability"))
    assert result.status == "solved"
    assert result.problem_type == "calculate_probability"
    assert result.solution_set.text in {"3/10", "0.3"}


def test_probability_complement_and_independent():
    complement = solve_algebra(AlgebraSolveRequest(input="P_not(2/5)", topic="combinatorics_probability"))
    assert complement.status == "solved"
    assert complement.solution_set.text in {"3/5", "0.6"}
    independent = solve_algebra(AlgebraSolveRequest(input="P_and(1/2,1/3)", topic="combinatorics_probability"))
    assert independent.status == "solved"
    assert independent.solution_set.text in {"1/6", "0.1666666666666667"}


def test_probability_from_vietnamese_interpreter():
    result = solve_algebra(AlgebraSolveRequest(input="Tính xác suất 2/5"))
    assert result.status == "solved"
    assert result.topic == "combinatorics_probability"
