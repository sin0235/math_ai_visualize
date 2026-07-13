from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_calculus_solver_explains_chain_rule_derivative():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=(x^2+1)^3,var=x)", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "calculus_derivative"
    assert result.answer_latex == r"6 x \left(x^{2} + 1\right)^{2}"
    assert [step.title for step in result.steps[:3]] == ["Nhận dạng hàm cần đạo hàm", "Dùng quy tắc dây chuyền", "Rút gọn kết quả"]
    assert all(step.kind != "normalize" for step in result.steps)


def test_calculus_solver_explains_zero_over_zero_limit():
    result = solve_algebra(AlgebraSolveRequest(input="limit(expr=(x^2-1)/(x-1),var=x,to=1)", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "calculus_limit"
    assert result.answer_latex == "2"
    titles = [step.title for step in result.steps]
    assert "Thử thay trực tiếp" in titles
    assert "Khử dạng vô định 0/0" in titles
    assert "Kết luận giới hạn" in titles


def test_calculus_solver_explains_definite_integral():
    result = solve_algebra(AlgebraSolveRequest(input="integral(expr=2*x,var=x,a=0,b=1)", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "calculus_integral"
    assert result.answer_latex == "1"
    assert [step.title for step in result.steps[:3]] == ["Nhận dạng tích phân", "Tìm nguyên hàm", "Thay cận tích phân"]


def test_calculus_integral_equation_solves_upper_bound():
    result = solve_algebra(AlgebraSolveRequest(input="integral(expr=2*x,var=x,a=1,b=z,target=2)", topic="auto", variables=["z"]))

    assert result.status == "solved"
    assert result.topic == "calculus_integral"
    assert result.answer == "Nghiệm: z = -sqrt(3), sqrt(3)"
    assert result.answer_latex == "z=- \\sqrt{3}, \\sqrt{3}"


def test_calculus_interpreter_detects_vietnamese_natural_inputs():
    derivative = solve_algebra(AlgebraSolveRequest(input="đạo hàm (x^2+1)^3"))
    limit = solve_algebra(AlgebraSolveRequest(input="giới hạn (x^2-1)/(x-1) khi x tới 1"))
    integral = solve_algebra(AlgebraSolveRequest(input="tích phân 2*x từ 0 đến 1"))
    logarithmic_integral = solve_algebra(AlgebraSolveRequest(input="Tính tích phân x*lnx từ 1 đến 2"))

    assert derivative.topic == "calculus_derivative"
    assert limit.topic == "calculus_limit"
    assert integral.topic == "calculus_integral"
    assert logarithmic_integral.topic == "calculus_integral"
    assert derivative.status == limit.status == integral.status == logarithmic_integral.status == "solved"
    assert logarithmic_integral.normalized_input == "integral(expr=x*ln(x),var=x,a=1,b=2)"


def test_calculus_interpreter_solves_vietnamese_integral_phrase_with_steps():
    result = solve_algebra(AlgebraSolveRequest(input="tìm tích phân của 2*x+1", topic="calculus_integral"))

    assert result.status == "solved"
    assert result.topic == "calculus_integral"
    assert result.normalized_input == "integral(expr=2*x+1,var=x)"
    assert result.answer_latex == r"x \left(x + 1\right)+C"
    assert [step.title for step in result.steps[:2]] == ["Nhận dạng tích phân", "Tìm nguyên hàm"]


def test_calculus_interpreter_does_not_double_wrap_structured_integral_with_bad_expr():
    result = solve_algebra(AlgebraSolveRequest(input="integral(expr=tìm tích phân của 2*x+1,var=x)", topic="calculus_integral"))

    assert result.status == "unsupported"
    assert result.normalized_input.startswith("integral(expr=")
    assert "integral(expr=integral" not in result.normalized_input


def test_calculus_interpreter_solves_sum_from_given_derivatives_without_nested_wrapping():
    input_text = (
        "Cho các hàm số (y=f(x)) và (y=g(x)) có đạo hàm trên tập số thực "
        "(\\mathbb{R}), thỏa mãn (f'(x)=x) và (g'(x)=x^2). "
        "Đạo hàm của hàm số (y=f(x)+g(x)) là:"
    )

    result = solve_algebra(AlgebraSolveRequest(input=input_text))
    replay = solve_algebra(AlgebraSolveRequest(input=result.normalized_input, input_format="structured"))

    assert result.status == replay.status == "solved"
    assert result.topic == replay.topic == "calculus_derivative"
    assert result.normalized_input == "derivative_sum(functions=f|g,values=x|x**2,var=x)"
    assert replay.normalized_input == result.normalized_input
    assert result.answer_latex == replay.answer_latex == "x^{2} + x"
    assert [step.title for step in result.steps[:3]] == [
        "Dùng quy tắc đạo hàm của tổng",
        "Thay các đạo hàm đã cho",
        "Rút gọn kết quả",
    ]


def test_calculus_interpreter_solves_sum_from_given_derivatives_without_nested_wrapping():
    input_text = (
        "Cho các hàm số (y=f(x)) và (y=g(x)) có đạo hàm trên tập số thực "
        "(\\mathbb{R}), thỏa mãn (f'(x)=x) và (g'(x)=x^2). "
        "Đạo hàm của hàm số (y=f(x)+g(x)) là:"
    )

    result = solve_algebra(AlgebraSolveRequest(input=input_text))
    replay = solve_algebra(AlgebraSolveRequest(input=result.normalized_input, input_format="structured"))

    assert result.status == replay.status == "solved"
    assert result.topic == replay.topic == "calculus_derivative"
    assert result.normalized_input == "derivative_sum(functions=f|g,values=x|x**2,var=x)"
    assert replay.normalized_input == result.normalized_input
    assert result.answer_latex == replay.answer_latex == "x^{2} + x"
    assert [step.title for step in result.steps[:3]] == [
        "Dùng quy tắc đạo hàm của tổng",
        "Thay các đạo hàm đã cho",
        "Rút gọn kết quả",
    ]


def test_calculus_derivative_explains_quotient_rule():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=(x^2+1)/(x-1),var=x)", topic="auto"))

    assert result.status == "solved"
    assert "Dùng quy tắc thương" in [step.title for step in result.steps]
    assert any(step.method == "quotient_rule" for step in result.steps)


def test_calculus_derivative_explains_logarithmic_differentiation():
    result = solve_algebra(AlgebraSolveRequest(input="derivative(expr=x^x,var=x)", topic="auto"))

    assert result.status == "solved"
    assert result.answer_latex == r"x^{x} \left(\log{\left(x \right)} + 1\right)"
    assert any(step.method == "logarithmic_differentiation" for step in result.steps)


def test_calculus_derivative_explains_trig_chain_rule_and_higher_order():
    chain = solve_algebra(AlgebraSolveRequest(input="derivative(expr=sin(x^2),var=x)", topic="auto"))
    higher = solve_algebra(AlgebraSolveRequest(input="derivative(expr=x^4,var=x,order=2)", topic="auto"))

    assert chain.answer_latex == r"2 x \cos{\left(x^{2} \right)}"
    assert any(step.method == "chain_rule" for step in chain.steps)
    assert higher.answer_latex == r"12 x^{2}"
    assert [step.method for step in higher.steps if step.method == "higher_order_derivative"] == ["higher_order_derivative", "higher_order_derivative"]


def test_calculus_limit_explains_conjugate_infinity_trig_and_lhospital():
    conjugate = solve_algebra(AlgebraSolveRequest(input="limit(expr=(sqrt(x+1)-1)/x,var=x,to=0)", topic="auto"))
    infinity = solve_algebra(AlgebraSolveRequest(input="limit(expr=(3*x^2+1)/(x^2-5),var=x,to=oo)", topic="auto"))
    trig = solve_algebra(AlgebraSolveRequest(input="limit(expr=sin(x)/x,var=x,to=0)", topic="auto"))
    lhospital = solve_algebra(AlgebraSolveRequest(input="limit(expr=(exp(x)-1)/x,var=x,to=0)", topic="auto"))

    assert conjugate.answer_latex == r"\frac{1}{2}"
    assert any(step.method == "conjugate_limit" for step in conjugate.steps)
    assert infinity.answer_latex == "3"
    assert any(step.method == "dominant_term_infinity" for step in infinity.steps)
    assert trig.answer_latex == "1"
    assert any(step.method == "standard_trig_limit" for step in trig.steps)
    assert lhospital.answer_latex == "1"
    assert any(step.method == "lhospital" for step in lhospital.steps)


def test_calculus_integral_explains_advanced_techniques():
    substitution = solve_algebra(AlgebraSolveRequest(input="integral(expr=2*x*cos(x^2),var=x)", topic="auto"))
    by_parts = solve_algebra(AlgebraSolveRequest(input="integral(expr=x*exp(x),var=x)", topic="auto"))
    partial = solve_algebra(AlgebraSolveRequest(input="integral(expr=1/(x^2-1),var=x)", topic="auto"))
    trig = solve_algebra(AlgebraSolveRequest(input="integral(expr=sin(x)^2,var=x)", topic="auto"))

    assert any(step.method == "u_substitution" for step in substitution.steps)
    assert any(step.method == "integration_by_parts" for step in by_parts.steps)
    assert any(step.method == "partial_fractions" for step in partial.steps)
    assert any(step.method == "trig_identity_integral" for step in trig.steps)


def test_calculus_solver_accepts_latex_derivative_and_definite_integral():
    derivative = solve_algebra(AlgebraSolveRequest(input=r"\frac{d}{dx}\left(\frac{x^2-2x}{x-1}\right)", input_format="latex", topic="auto"))
    integral = solve_algebra(AlgebraSolveRequest(input=r"\int_1^2 \frac{x^2-2x}{x-1} dx", input_format="latex", topic="auto"))

    assert derivative.status == "solved"
    assert derivative.topic == "calculus_derivative"
    assert any(step.method == "quotient_rule" for step in derivative.steps)
    assert integral.status == "solved"
    assert integral.topic == "calculus_integral"
    assert any(step.method == "improper_integral" for step in integral.steps)
    assert integral.answer_latex == r"-\infty"


def test_calculus_solver_accepts_mathquill_simple_definite_integral():
    result = solve_algebra(AlgebraSolveRequest(input=r"\int_{1}^{2}\left(2x\right)dx", input_format="latex", topic="calculus_integral"))
    styled_differential = solve_algebra(AlgebraSolveRequest(input=r"\int\limits_{1}^{2}\left(2x\right)\mathrm{d}x", input_format="latex", topic="calculus_integral"))

    assert result.status == "solved"
    assert result.topic == "calculus_integral"
    assert result.answer_latex == "3"
    assert styled_differential.status == "solved"
    assert styled_differential.answer_latex == "3"


def test_calculus_solver_overrides_stale_trig_topic_for_integral():
    result = solve_algebra(AlgebraSolveRequest(input=r"\int_{1}^{2}\left(2x\right)dx", input_format="latex", topic="trigonometry"))

    assert result.status == "solved"
    assert result.topic == "calculus_integral"
    assert result.answer_latex == "3"
