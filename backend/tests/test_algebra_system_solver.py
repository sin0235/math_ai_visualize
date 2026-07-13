from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_system_solver_solves_linear_two_by_two():
    result = solve_algebra(AlgebraSolveRequest(input="x+y=3; x-y=1", topic="system", variables=["x", "y"]))

    assert result.status == "solved"
    assert result.topic == "system"
    assert "x = 2" in result.answer
    assert "y = 1" in result.answer
    assert result.verification.status == "verified"
    assert [step.title for step in result.steps[:3]] == ["Viết hệ dạng chuẩn", "Khử một ẩn", "Thế ngược tìm ẩn còn lại"]
    assert all(step.kind != "normalize" for step in result.steps)


def test_system_solver_detects_system_with_auto_topic():
    result = solve_algebra(AlgebraSolveRequest(input="x+y=3; x-y=1", variables=["x", "y"]))

    assert result.status == "solved"
    assert result.topic == "system"
    assert "x = 2" in result.answer


def test_system_solver_auto_variables_when_empty():
    result = solve_algebra(AlgebraSolveRequest(input="x+y=3; x-y=1", topic="system"))

    assert result.status == "solved"
    assert result.topic == "system"
    assert "x = 2" in result.answer
    assert "y = 1" in result.answer


def test_system_solver_handles_nonlinear_system_with_substitution_verifier():
    result = solve_algebra(AlgebraSolveRequest(input="Giải hệ x^2 + y^2 = 5 và x - y = 1"))

    assert result.status == "solved"
    assert result.topic == "system"
    assert result.problem_type == "solve_system"
    assert "(-1, -2)" in result.solution_set.text
    assert "(2, 1)" in result.solution_set.text
    assert result.verification.status == "verified"
    assert all(check.name == "system_tuple_substitution" for check in result.verification.checks)
