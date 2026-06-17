import pytest
import sympy as sp

from app.services.algebra.domain import (
    compute_domain,
    format_domain,
    domain_assumptions_from_expression,
)

def test_compute_domain_polynomial():
    x = sp.Symbol('x')
    expr = x**2 + 2*x + 1
    domain = compute_domain(expr, x)
    assert domain == sp.S.Reals

def test_compute_domain_rational():
    x = sp.Symbol('x')
    expr = 1 / (x - 2)
    domain = compute_domain(expr, x)
    assert domain == sp.Union(sp.Interval.open(-sp.oo, 2), sp.Interval.open(2, sp.oo))

def test_compute_domain_sqrt():
    x = sp.Symbol('x')
    expr = sp.sqrt(x - 1)
    domain = compute_domain(expr, x)
    assert domain == sp.Interval(1, sp.oo)

def test_compute_domain_log():
    x = sp.Symbol('x')
    expr = sp.log(x + 3)
    domain = compute_domain(expr, x)
    assert domain == sp.Interval.open(-3, sp.oo)

def test_format_domain():
    x = sp.Symbol('x')
    assert format_domain(sp.S.Reals, x) == r"x \in \mathbb{R}"
    assert format_domain(sp.S.EmptySet, x) == r"x \in \emptyset"
    
    interval = sp.Interval.open(0, sp.oo)
    assert format_domain(interval, x) == r"x \in \left(0, \infty\right)"

def test_domain_assumptions_from_expression_reals():
    x = sp.Symbol('x')
    expr = x**3 - x
    assumptions = domain_assumptions_from_expression(expr, x)
    assert assumptions == []

def test_domain_assumptions_from_expression_formatted():
    x = sp.Symbol('x')
    expr = 1 / x
    assumptions = domain_assumptions_from_expression(expr, x)
    # Output should be formatted as a list with one latex string
    assert len(assumptions) == 1
    assert r"x \in \left(-\infty, 0\right) \cup \left(0, \infty\right)" in assumptions[0]

def test_domain_assumptions_fallback():
    # If continuous_domain returns ConditionSet or we force it, it should fallback to heuristics.
    # To simulate this, we can use an expression that continuous_domain struggles with,
    # or just trust the logic since we test the fallback logic implicitly via the expression
    # but a very complex expression might just work. 
    # Let's test the fallback logic directly with a complex nested function that returns ConditionSet.
    x = sp.Symbol('x')
    # a transcendental equation denominator
    expr = 1 / (x**x - 2)
    assumptions = domain_assumptions_from_expression(expr, x)
    # the fallback string will include "khác 0"
    assert any("khác 0" in a for a in assumptions)
