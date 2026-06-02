from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_inequality_solver_solves_polynomial_interval():
    result = solve_algebra(AlgebraSolveRequest(input="x^2 - 1 >= 0"))

    assert result.status == "solved"
    assert result.solution_set.kind == "interval"
    assert "(-∞; -1]" in result.solution_set.text
    assert "[1; +∞)" in result.solution_set.text
    assert result.verification.status == "verified"
    assert all(step.kind != "normalize" for step in result.steps)
    assert all(step.kind != "domain" for step in result.steps)
    assert result.steps[0].title == "Đưa bất phương trình về một vế"
    sign_step = next(step for step in result.steps if step.kind == "verify" and "Dấu trên từng khoảng" in step.explanation)
    assert sign_step.goal
    assert sign_step.why
    assert sign_step.rule == "Bảng xét dấu"
    assert sign_step.check


def test_inequality_solver_solves_rational_interval_with_domain_assumption():
    result = solve_algebra(AlgebraSolveRequest(input="(x-1)/(x+2) < 0"))

    assert result.status == "solved"
    assert "(-2; 1)" in result.solution_set.text
    assert any("x + 2" in assumption for assumption in result.assumptions)
    verification_step = next(step for step in result.steps if step.title == "Kiểm tra tập nghiệm")
    assert verification_step.pitfall and "Dấu ngoặc" in verification_step.pitfall
    assert verification_step.after_latex
