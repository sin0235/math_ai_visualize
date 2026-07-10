from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_trig_solver_returns_general_solution_for_sine_on_reals():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)=1/2"))

    assert result.status == "solved"
    assert result.topic == "trigonometry"
    assert result.solution_set.kind == "periodic"
    assert "pi/6" in result.answer or "\\frac{\\pi}{6}" in (result.answer_latex or "")
    assert result.solution_set.values == []
    assert any(step.method == "trig_general_solution" or step.method == "trig_periodic_solution" for step in result.steps)
    assert all(step.method != "filter_trig_interval" for step in result.steps)
    assert any("tổng quát" in warning.lower() or "symbolic" in warning.lower() for warning in result.warnings) or result.verification.status in {"verified", "partially_verified"}


def test_trig_solver_solves_cos_double_angle_general():
    result = solve_algebra(AlgebraSolveRequest(input="cos(2*x)=1"))

    assert result.status == "solved"
    assert result.solution_set.kind == "periodic"
    assert "pi" in result.answer.lower() or "\\pi" in (result.answer_latex or "")


def test_trig_solver_simplifies_identity():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)^2+cos(x)^2=1", topic="trigonometry"))

    assert result.status == "solved"
    assert result.steps[0].method == "trig_identity_simplify"
    # Identity on R is the reals, not a single period interval.
    assert result.solution_set.kind in {"set", "interval", "periodic"}
    assert "mathbb{R}" in (result.answer_latex or "") or "Reals" in result.answer or result.answer_latex in {r"\mathbb{R}", "R"}


def test_trig_solver_uses_substitution_for_quadratic_in_cos():
    result = solve_algebra(AlgebraSolveRequest(input="2*cos(x)^2-3*cos(x)+1=0", topic="trigonometry"))

    assert result.status == "solved"
    assert result.solution_set.kind == "periodic"
    assert [step.method for step in result.steps if step.method][:2] == ["trig_substitution", "solve_trig_substitution"]


def test_trig_solver_uses_double_angle_formula():
    result = solve_algebra(AlgebraSolveRequest(input="sin(2*x)=sin(x)", topic="trigonometry"))

    assert result.status == "solved"
    assert result.solution_set.kind == "periodic"
    assert result.steps[0].method == "double_angle"


def test_trig_solver_uses_sum_to_product():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)+sin(3*x)=0", topic="trigonometry"))

    assert result.status == "solved"
    assert result.solution_set.kind == "periodic"
    assert result.steps[0].method == "sum_to_product"


def test_trig_solver_solves_a_sin_plus_b_cos():
    result = solve_algebra(AlgebraSolveRequest(input="3*sin(x)+4*cos(x)=5", topic="trigonometry"))

    assert result.status == "solved"
    # May be finite special case or periodic depending on SymPy representation.
    assert result.solution_set.kind in {"periodic", "finite"}
    assert result.steps[0].method == "asin_bcos"


def test_trig_solver_records_tangent_domain():
    result = solve_algebra(AlgebraSolveRequest(input="tan(x)=1", topic="trigonometry"))

    assert result.status == "solved"
    assert "cos(x) khác 0" in result.assumptions
    assert result.solution_set.kind == "periodic"
    assert "pi/4" in result.answer or "\\frac{\\pi}{4}" in (result.answer_latex or "")


def test_trig_solver_evaluates_latex_inverse_trig_expression():
    result = solve_algebra(AlgebraSolveRequest(input=r"\tan^{-1}\left(1\right)", input_format="latex", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "trigonometry"
    assert result.problem_type == "evaluate_trigonometric_expression"
    assert result.answer_latex == r"\frac{\pi}{4}"
