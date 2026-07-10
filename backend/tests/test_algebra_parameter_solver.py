from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_parameter_solver_finds_quadratic_double_root_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_double_root(a=1,b=-2*m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.topic == "parameter"
    assert result.solution_set.kind == "conditions"
    assert "1" in result.solution_set.text
    assert "-1" in result.solution_set.text
    assert result.verification.status == "verified"
    assert [step.title for step in result.steps[:2]] == ["Tính biệt thức Delta", "Lập điều kiện theo tham số"]
    assert all(step.kind != "normalize" for step in result.steps)


def test_parameter_solver_finds_quadratic_two_distinct_roots_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_has_two_roots(a=1,b=m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "-2" in result.solution_set.text
    assert "2" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_finds_quadratic_positive_all_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_positive_all(a=1,b=m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "m > -2" in result.solution_set.text
    assert "m < 2" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_auto_detects_structured_template():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_has_real_root(a=1,b=m,c=1,var=x,param=m)", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "parameter"
    assert result.input_interpretation is not None
    assert result.input_interpretation.topic_hint == "parameter"


def test_parameter_solver_case_splits_when_leading_coefficient_depends_on_m():
    # a = m: when m=0 equation becomes linear x+1=0 — not "two distinct quadratic roots".
    import sympy as sp
    from app.services.algebra.solvers.parameter_solver import QuadraticTemplate, _actual_property, _solve_quadratic_template

    template = QuadraticTemplate(
        kind="quadratic_has_two_roots",
        a=sp.Symbol("m", real=True),
        b=sp.Integer(1),
        c=sp.Integer(1),
        variable=sp.Symbol("x", real=True),
        parameter=sp.Symbol("m", real=True),
    )
    condition, explanation, _ = _solve_quadratic_template(template)
    assert "suy biến" in explanation or "a=0" in explanation
    assert _actual_property(template, 0) is False
    # Condition set/relational must not accept m=0
    if isinstance(condition, sp.Set):
        assert bool(condition.contains(0)) is False
    else:
        assert bool(condition.subs(template.parameter, 0)) is False

    result = solve_algebra(AlgebraSolveRequest(
        input="quadratic_has_two_roots(a=m,b=1,c=1,var=x,param=m)",
        topic="parameter",
    ))
    assert result.status in {"solved", "partial"}
    assert "suy biến" in " ".join(step.explanation for step in result.steps).lower()


def test_parameter_solver_opposite_roots():
    # x^2 + m x - 1 = 0 has opposite roots when m = 0 (sum=0) and Delta=4>0.
    result = solve_algebra(AlgebraSolveRequest(
        input="quadratic_opposite_roots(a=1,b=m,c=-1,var=x,param=m)",
        topic="parameter",
    ))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "0" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_opposite_sign_roots():
    # x^2 + m x + (m-2) = 0 has opposite-sign roots when c/a = m-2 < 0 ⇒ m < 2.
    result = solve_algebra(AlgebraSolveRequest(
        input="quadratic_opposite_sign_roots(a=1,b=m,c=m-2,var=x,param=m)",
        topic="parameter",
    ))

    assert result.status == "solved"
    assert "2" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_same_sign_roots():
    # x^2 + m x + 1 = 0: product=1>0, real when |m|>=2.
    result = solve_algebra(AlgebraSolveRequest(
        input="quadratic_same_sign_roots(a=1,b=m,c=1,var=x,param=m)",
        topic="parameter",
    ))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "2" in result.solution_set.text or "-2" in result.solution_set.text
    assert result.verification.status == "verified"
