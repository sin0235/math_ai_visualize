from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_exp_log_solver_solves_exponential_equation():
    result = solve_algebra(AlgebraSolveRequest(input="2^(x+1)=8"))

    assert result.status == "solved"
    assert result.topic == "exponential_log"
    assert {value.text for value in result.solution_set.values} == {"2"}
    assert result.verification.status == "verified"
    assert [step.title for step in result.steps[:2]] == ["Chọn phương pháp cùng cơ số", "Giải phương trình số mũ"]
    assert result.steps[0].method == "same_base_exponential"


def test_exp_log_solver_solves_log_equation_with_domain():
    result = solve_algebra(AlgebraSolveRequest(input="log(x-1, 2)=3"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"9"}
    assert any(r"\left(1, \infty\right)" in a for a in result.assumptions)


def test_exp_log_solver_solves_log_sum_equation():
    result = solve_algebra(AlgebraSolveRequest(input="log(x,2)+log(x-2,2)=3"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"4"}
    assert any(r"\left(2, \infty\right)" in a for a in result.assumptions)

    assert [step.title for step in result.steps[1:5]] == ["Gộp log cùng cơ số", "Bỏ log", "Giải phương trình đại số", "Thử lại điều kiện log"]


def test_exp_log_solver_accepts_mathquill_log_base_with_fraction_argument():
    result = solve_algebra(AlgebraSolveRequest(input=r"\log_3((x-3)/(x-2)^2)=22", input_format="latex", topic="exponential_log"))

    assert result.status == "solved"
    assert result.topic == "exponential_log"
    assert result.solution_set.kind == "empty"
    assert result.answer == "Vô nghiệm."
    assert any(step.title == "Bỏ log" for step in result.steps)
    assert all(step.kind != "normalize" for step in result.steps)


def test_exp_log_solver_explains_exponential_substitution():
    result = solve_algebra(AlgebraSolveRequest(input="2^(2*x)-5*2^x+4=0"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0", "2"}
    titles = [step.title for step in result.steps]
    assert titles[:3] == ["Đặt ẩn phụ", "Giải phương trình theo ẩn phụ", "Trả về biến ban đầu"]
    substitution_step = result.steps[0]
    assert "t=2^{x}" in substitution_step.after_latex
    back_step = next(step for step in result.steps if step.title == "Trả về biến ban đầu")
    assert "2^{x}=4" in back_step.after_latex


def test_exp_log_solver_moves_log_coefficient_inside():
    result = solve_algebra(AlgebraSolveRequest(input="2*log(x,2)=6"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"8"}
    titles = [step.title for step in result.steps]
    assert "Đưa hệ số log vào biểu thức" in titles
    assert "Thử lại điều kiện log" in titles


def test_exp_log_solver_combines_log_quotient():
    result = solve_algebra(AlgebraSolveRequest(input="log(x,2)-log(x-2,2)=1"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"4"}
    quotient_step = next(step for step in result.steps if step.title == "Gộp log dạng thương")
    assert quotient_step.method == "combine_logarithms"



def test_exp_log_solver_handles_reciprocal_exponential_substitution():
    result = solve_algebra(AlgebraSolveRequest(input="2^x+2^(-x)=5"))

    assert result.status == "solved"
    assert len(result.solution_set.values) == 2
    substitution_step = next(step for step in result.steps if step.title == "Đặt ẩn phụ")
    assert substitution_step.method == "exponential_substitution"
    assert "t>0" in substitution_step.after_latex
    assert "t^{2} - 5 t + 1 = 0" in substitution_step.after_latex


def test_exp_log_solver_uses_log_both_sides_for_single_exponential():
    result = solve_algebra(AlgebraSolveRequest(input="3^x=10"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"log(10)/log(3)"}
    assert result.steps[0].title == "Lấy log hai vế"
    assert result.steps[0].method == "log_both_sides"


def test_exp_log_solver_accepts_lowercase_e_as_euler():
    result = solve_algebra(AlgebraSolveRequest(input="e**x=5"))

    assert result.status == "solved"
    assert result.topic == "exponential_log"
    assert {value.text for value in result.solution_set.values} == {"log(5)"}
    assert result.steps[0].method == "log_both_sides"


def test_exp_log_solver_accepts_uppercase_E_without_stealing_variable():
    result = solve_algebra(AlgebraSolveRequest(input="E**x=5"))

    assert result.status == "solved"
    assert result.topic == "exponential_log"
    assert {value.text for value in result.solution_set.values} == {"log(5)"}
    assert result.input_interpretation is not None
    assert result.input_interpretation.variables == ["x"]


def test_exp_log_solver_substitutes_exp_sum_of_reciprocals():
    result = solve_algebra(AlgebraSolveRequest(input="exp(x)+exp(-x)=2"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0"}
    titles = [step.title for step in result.steps]
    assert titles[:3] == ["Đặt ẩn phụ", "Giải phương trình theo ẩn phụ", "Trả về biến ban đầu"]


def test_exp_log_solver_substitutes_quadratic_in_exp():
    result = solve_algebra(AlgebraSolveRequest(input="exp(2*x)-3*exp(x)+2=0"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"0", "log(2)"}
    assert result.steps[0].method == "exponential_substitution"


def test_exp_log_domain_filters_spurious_root():
    # log(x-1)+log(x+1)=log(3) ⇒ (x-1)(x+1)=3 ⇒ x^2=4 ⇒ x=±2; domain x>1 keeps only 2.
    result = solve_algebra(AlgebraSolveRequest(input="log(x-1)+log(x+1)=log(3)"))

    assert result.status == "solved"
    assert {value.text for value in result.solution_set.values} == {"2"}
    assert any("Thử lại điều kiện log" in (step.title or "") for step in result.steps)
    assert any("1" in a and "infty" in a for a in result.assumptions)
