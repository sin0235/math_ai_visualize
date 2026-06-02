from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_trig_solver_solves_sine_on_default_interval():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)=1/2"))

    assert result.status == "solved"
    assert result.topic == "trigonometry"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"pi/6", "5*pi/6"}
    assert result.verification.status == "verified"
    assert [step.title for step in result.steps[:3]] == ["Đưa về phương trình lượng giác cơ bản", "Viết nghiệm theo chu kỳ", "Lọc nghiệm trên khoảng chuẩn"]
    assert all(step.kind != "normalize" for step in result.steps)


def test_trig_solver_solves_cos_double_angle_on_default_interval():
    result = solve_algebra(AlgebraSolveRequest(input="cos(2*x)=1"))

    assert result.status == "solved"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"0", "pi"}
    assert "Lọc nghiệm trên khoảng chuẩn" in [step.title for step in result.steps]


def test_trig_solver_simplifies_identity():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)^2+cos(x)^2=1", topic="trigonometry"))

    assert result.status == "solved"
    assert result.steps[0].method == "trig_identity_simplify"
    assert result.answer_latex == r"\left[0, 2 \pi\right)"


def test_trig_solver_uses_substitution_for_quadratic_in_cos():
    result = solve_algebra(AlgebraSolveRequest(input="2*cos(x)^2-3*cos(x)+1=0", topic="trigonometry"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0", "pi/3", "5*pi/3"}
    assert [step.method for step in result.steps[:3]] == ["trig_substitution", "solve_trig_substitution", "filter_trig_interval"]


def test_trig_solver_uses_double_angle_formula():
    result = solve_algebra(AlgebraSolveRequest(input="sin(2*x)=sin(x)", topic="trigonometry"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0", "pi/3", "pi", "5*pi/3"}
    assert result.steps[0].method == "double_angle"


def test_trig_solver_uses_sum_to_product():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)+sin(3*x)=0", topic="trigonometry"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0", "pi/2", "pi", "3*pi/2"}
    assert result.steps[0].method == "sum_to_product"


def test_trig_solver_solves_a_sin_plus_b_cos():
    result = solve_algebra(AlgebraSolveRequest(input="3*sin(x)+4*cos(x)=5", topic="trigonometry"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"atan(3/4)"}
    assert result.steps[0].method == "asin_bcos"


def test_trig_solver_records_tangent_domain():
    result = solve_algebra(AlgebraSolveRequest(input="tan(x)=1", topic="trigonometry"))

    assert result.status == "solved"
    assert "cos(x) khác 0" in result.assumptions
    assert {value.text for value in result.solution_set.values} == {"pi/4", "5*pi/4"}
