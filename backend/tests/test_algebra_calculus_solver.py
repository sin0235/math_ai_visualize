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


def test_calculus_interpreter_detects_vietnamese_natural_inputs():
    derivative = solve_algebra(AlgebraSolveRequest(input="đạo hàm (x^2+1)^3"))
    limit = solve_algebra(AlgebraSolveRequest(input="giới hạn (x^2-1)/(x-1) khi x tới 1"))
    integral = solve_algebra(AlgebraSolveRequest(input="tích phân 2*x từ 0 đến 1"))

    assert derivative.topic == "calculus_derivative"
    assert limit.topic == "calculus_limit"
    assert integral.topic == "calculus_integral"
    assert derivative.status == limit.status == integral.status == "solved"
