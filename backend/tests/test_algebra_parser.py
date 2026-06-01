import sympy as sp

from app.services.algebra.normalizer import normalize_algebra_input
from app.services.algebra.parser import parse_algebra_problem


def test_normalizer_handles_basic_latex_fraction():
    assert normalize_algebra_input(r"\frac{x+1}{2}=3") == "((x+1)/(2))=3"


def test_normalizer_handles_unicode_superscript_and_inequality():
    assert normalize_algebra_input("x² − 1 ≥ 0") == "x**2 - 1 >= 0"


def test_parser_parses_equation():
    problem = parse_algebra_problem("x^2 - 5*x + 6 = 0")
    assert problem.topic == "equation"
    assert isinstance(problem.relation, sp.Equality)


def test_parser_parses_inequality():
    problem = parse_algebra_problem("x^2 - 1 >= 0")
    assert problem.topic == "inequality"
    assert problem.relation is not None
