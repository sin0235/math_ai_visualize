import sympy as sp

from app.services.algebra.notation import algebra_latex, algebra_text


def test_notation_prints_natural_log_as_ln():
    x = sp.Symbol("x")

    assert algebra_latex(sp.log(x)) == r"\ln{\left(x \right)}"
    assert algebra_text(sp.log(x)) == "ln(x)"


def test_notation_prints_change_of_base_as_explicit_base_log():
    x = sp.Symbol("x")
    expression = sp.log(x) / sp.log(10)

    assert algebra_latex(expression) == r"\log_{10}{\left(x \right)}"
    assert algebra_text(expression) == "log_10(x)"


def test_notation_preserves_log_base_inside_larger_expression():
    x = sp.Symbol("x")
    expression = x**2 * sp.log(x) / (2 * sp.log(10)) - x**2 / (4 * sp.log(10))

    assert r"\frac{x^{2} \log_{10}{\left(x \right)}}{2}" in algebra_latex(expression)
    assert r"\ln{\left(10 \right)}" in algebra_latex(expression)
    assert "log_10(x)" in algebra_text(expression)
