from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_sequence_solver_calculates_arithmetic_term():
    result = solve_algebra(AlgebraSolveRequest(input="arithmetic(u1=2,d=3,n=10)", topic="sequence"))

    assert result.status == "solved"
    assert result.topic == "sequence"
    assert result.solution_set.text == "29"
    assert [step.title for step in result.steps[:2]] == ["Viết công thức", "Tính kết quả"]
    assert all(step.kind != "normalize" for step in result.steps)
    assert result.verification.status == "skipped"


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


def test_sequence_solver_solves_natural_language_geometric_sum():
    request = AlgebraSolveRequest(input="dãy 3,6,12,... tính S5")
    result = solve_algebra(request)

    assert result.status == "solved"
    assert result.solution_set.text == "93"
    assert result.steps[0].after_latex == r"S_{5}=\frac{3\left((2)^5-1\right)}{2-1}"
    assert result.input_interpretation is not None
    assert result.input_interpretation.variables == []


def test_sequence_solver_rejects_fractional_n():
    result = solve_algebra(AlgebraSolveRequest(input="arithmetic(u1=2,d=3,n=3/2)", topic="sequence"))

    assert result.status == "unsupported"
    assert "SEQUENCE_N_NOT_INTEGER" in result.answer or "nguyên" in result.answer.lower()


def test_sequence_solver_rejects_zero_n():
    result = solve_algebra(AlgebraSolveRequest(input="arithmetic(u1=2,d=3,n=0)", topic="sequence"))

    assert result.status == "unsupported"
    assert "nguyên dương" in result.answer.lower() or "dương" in result.answer.lower()


def test_natural_language_arithmetic_u1_u2_u9():
    result = solve_algebra(AlgebraSolveRequest(
        input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
        topic="sequence",
    ))
    assert result.status == "solved"
    assert "34" in (result.answer or "") or result.answer_latex == "34"
    assert result.steps[0].title == "Tìm công sai"
    assert result.verification.status == "skipped"
    assert result.verification.checks == []
