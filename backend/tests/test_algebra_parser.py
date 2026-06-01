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


def test_parser_parses_equation():
    problem = parse_algebra_problem("x^2 - 5*x + 6 = 0")
    assert problem.topic == "equation"
    assert isinstance(problem.relation, sp.Equality)


def test_parser_parses_inequality():
    problem = parse_algebra_problem("x^2 - 1 >= 0")
    assert problem.topic == "inequality"
    assert problem.relation is not None
