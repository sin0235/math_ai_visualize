import sympy as sp

from app.services.algebra.normalizer import normalize_algebra_input
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.algebra.parser import parse_algebra_problem
from app.schemas.algebra import AlgebraSolveRequest


def test_normalizer_handles_basic_latex_fraction():
    assert normalize_algebra_input(r"\frac{x+1}{2}=3") == "((x+1)/(2))=3"


def test_normalizer_handles_unicode_superscript_and_inequality():
    assert normalize_algebra_input("x² − 1 ≥ 0") == "x**2 - 1>=0"


def test_normalizer_handles_mathquill_log_base_and_relation():
    assert normalize_algebra_input(r"\log_2(x)+\log_2(x-2)\le 3") == "log(x, 2)+log(x-2, 2)<=3"


def test_normalizer_handles_log_base_with_nested_fraction_argument():
    assert normalize_algebra_input(r"\log_3((x-3)/(x-2)^2)=22") == "log((x-3)/(x-2)**2, 3)=22"
    assert normalize_algebra_input(r"\log_{3}\left((x-3)/(x-2)^2\right)=22") == "log((x-3)/(x-2)**2, 3)=22"
    assert normalize_algebra_input("log_3((x-3)/(x-2)^2)=22") == "log((x-3)/(x-2)**2, 3)=22"


def test_normalizer_handles_nested_latex_fraction():
    assert normalize_algebra_input(r"\frac{\frac{x+1}{2}}{3}=1") == "((((x+1)/(2)))/(3))=1"


def test_normalizer_handles_latex_sqrt_and_trig_fraction():
    assert normalize_algebra_input(r"\sin(x)=\frac{1}{2}") == "sin(x)=((1)/(2))"
    assert normalize_algebra_input(r"\sqrt{x+1}=2") == "sqrt(x+1)=2"


def test_normalizer_handles_latex_cases_system():
    assert normalize_algebra_input(r"\begin{cases}x+y=0\\x-y=0\end{cases}") == "x+y=0; x-y=0"


def test_normalizer_converts_latex_calculus_templates():
    assert normalize_algebra_input(r"\frac{d}{dx}\left(\frac{x^2-2x}{x-1}\right)") == "derivative(expr=((x**2-2*x)/(x-1)),var=x)"
    assert normalize_algebra_input(r"\int_1^2 \frac{x^2-2x}{x-1} dx") == "integral(expr=((x**2-2*x)/(x-1)),var=x,a=1,b=2)"
    assert normalize_algebra_input(r"\int_1^2\left(2x+1\right)dx") == "integral(expr=(2*x+1),var=x,a=1,b=2)"
    assert normalize_algebra_input(r"\int_{1}^{2}\left(2x\right)dx") == "integral(expr=(2*x),var=x,a=1,b=2)"
    assert normalize_algebra_input(r"\int\limits_{1}^{2}\left(2x\right)\mathrm{d}x") == "integral(expr=(2*x),var=x,a=1,b=2)"
    assert normalize_algebra_input(r"\lim_{x\to0}\left(\frac{\sin(x)}{x}\right)") == "limit(expr=((sin(x))/(x)),var=x,to=0)"


def test_normalizer_converts_latex_inverse_trig():
    assert normalize_algebra_input(r"\tan^{-1}\left(1\right)") == "atan(1)"
    assert normalize_algebra_input(r"\sin^{-1}\left(\frac{1}{2}\right)") == "asin(((1)/(2)))"
    assert normalize_algebra_input(r"\arctan\left(1\right)") == "atan(1)"


def test_interpreter_uses_structured_latex_calculus_as_canonical_input():
    derivative = interpret_algebra_input(AlgebraSolveRequest(input=r"\frac{d}{dx}\left(\frac{x^2-2x}{x-1}\right)", input_format="latex"))
    integral = interpret_algebra_input(AlgebraSolveRequest(input=r"\int_1^2 \frac{x^2-2x}{x-1} dx", input_format="latex"))
    limit = interpret_algebra_input(AlgebraSolveRequest(input=r"\lim_{x\to0}\left(\frac{3x}{x-1}\right)", input_format="latex"))

    assert derivative.canonical_input == "derivative(expr=((x**2-2*x)/(x-1)),var=x)"
    assert derivative.topic_hint == "calculus_derivative"
    assert integral.canonical_input == "integral(expr=((x**2-2*x)/(x-1)),var=x,a=1,b=2)"
    assert integral.topic_hint == "calculus_integral"
    assert limit.canonical_input == "limit(expr=((3*x)/(x-1)),var=x,to=0)"
    assert limit.topic_hint == "calculus_limit"


def test_interpreter_converts_vietnamese_equation_to_canonical_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Giải phương trình x bình phương - 5x + 6 bằng 0"))
    assert interpretation.detected_format == "mixed"
    assert interpretation.canonical_input == "x^2-5*x+6=0"
    assert interpretation.topic_hint == "equation"
    assert interpretation.variables == ["x"]


def test_interpreter_converts_vietnamese_inequality_to_canonical_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Tìm x thỏa mãn (x-1)/(x+2) nhỏ hơn 0"))
    assert interpretation.canonical_input == "(x-1)/(x+2)<0"
    assert interpretation.topic_hint == "inequality"


def test_interpreter_converts_vietnamese_combination_to_structured_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Tính tổ hợp chập 3 của 10"))
    assert interpretation.canonical_input == "C(10,3)"
    assert interpretation.topic_hint == "combinatorics_probability"


def test_interpreter_converts_vietnamese_factorial_to_structured_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Tính 5 giai thừa"))
    assert interpretation.canonical_input == "5!"
    assert interpretation.topic_hint == "combinatorics_probability"


def test_interpreter_converts_vietnamese_sequence_to_structured_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Cấp số cộng u1=2 d=3 n=10 tìm số hạng thứ n"))
    assert interpretation.canonical_input == "arithmetic(u1=2,d=3,n=10)"
    assert interpretation.topic_hint == "sequence"


def test_interpreter_converts_sequence_term_index_to_structured_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Cấp số cộng u1=2 d=3 tìm u10"))

    assert interpretation.canonical_input == "arithmetic(u1=2,d=3,n=10)"
    assert interpretation.topic_hint == "sequence"


def test_interpreter_converts_sequence_sum_text_to_structured_input():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="Tính tổng 10 số hạng đầu của cấp số nhân u1=3 q=2"))

    assert interpretation.canonical_input == "geometric_sum(u1=3,q=2,n=10)"
    assert interpretation.topic_hint == "sequence"


def test_interpreter_detects_arithmetic_sequence_from_list():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="dãy 2,5,8,... tìm số hạng thứ 20"))

    assert interpretation.canonical_input == "arithmetic(u1=2,d=3,n=20)"
    assert interpretation.topic_hint == "sequence"


def test_interpreter_detects_geometric_sum_from_list():
    interpretation = interpret_algebra_input(AlgebraSolveRequest(input="dãy 3,6,12,... tính S5"))

    assert interpretation.canonical_input == "geometric_sum(u1=3,q=2,n=5)"
    assert interpretation.topic_hint == "sequence"


def test_parser_parses_equation():
    problem = parse_algebra_problem("x^2 - 5*x + 6 = 0")
    assert problem.topic == "equation"
    assert isinstance(problem.relation, sp.Equality)


def test_parser_parses_inequality():
    problem = parse_algebra_problem("x^2 - 1 >= 0")
    assert problem.topic == "inequality"
    assert problem.relation is not None
