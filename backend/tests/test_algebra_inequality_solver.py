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
    assert result.steps[0].title == "Chọn phương pháp xét dấu"
    assert result.steps[0].method == "sign_chart"
    assert result.steps[1].title == "Đưa bất phương trình về một vế"
    assert "sample_substitution" in result.verification.method
    assert any(check.name == "inequality_sample" for check in result.verification.checks)
    assert "Phân tích dấu" in [step.title for step in result.steps]
    assert "Lập bảng xét dấu" in [step.title for step in result.steps]
    assert "Chọn khoảng nghiệm" in [step.title for step in result.steps]
    sign_step = next(step for step in result.steps if step.kind == "verify" and "Dấu trên từng khoảng" in step.explanation)
    assert sign_step.goal
    assert sign_step.why
    assert sign_step.rule == "Bảng xét dấu"
    assert sign_step.check
    assert "\\text{chọn}" in sign_step.after_latex
    assert "\\text{không chọn}" in sign_step.after_latex


def test_inequality_solver_solves_rational_interval_with_domain_assumption():
    result = solve_algebra(AlgebraSolveRequest(input="(x-1)/(x+2) < 0"))

    assert result.status == "solved"
    assert "(-2; 1)" in result.solution_set.text
    assert any("x + 2" in assumption for assumption in result.assumptions)
    verification_step = next(step for step in result.steps if step.title == "Kiểm tra tập nghiệm")
    assert verification_step.pitfall and "Dấu ngoặc" in verification_step.pitfall
    assert verification_step.after_latex


def test_inequality_solver_excludes_denominator_boundary_in_sign_chart():
    result = solve_algebra(AlgebraSolveRequest(input="(x-1)/(x+2) <= 0"))

    assert result.status == "solved"
    assert "(-2; 1]" in result.solution_set.text
    critical_step = next(step for step in result.steps if step.title == "Phân tích dấu")
    assert "-2" in critical_step.after_latex
    assert "\\text{mẫu bằng 0, loại}" in critical_step.after_latex
    choose_step = next(step for step in result.steps if step.title == "Chọn khoảng nghiệm")
    assert "\\left(-2, 1\\right]" in choose_step.after_latex
