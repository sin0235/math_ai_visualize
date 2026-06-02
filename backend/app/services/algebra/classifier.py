from __future__ import annotations

import sympy as sp

from app.services.algebra.parser import ParsedAlgebraProblem


def classify_algebra_problem(problem: ParsedAlgebraProblem) -> str:
    if len(problem.relations) > 1:
        return "system"
    if problem.relation is None:
        if problem.topic != "auto":
            return problem.topic
        normalized = problem.normalized_input.strip()
        if normalized.startswith(("arithmetic(", "arithmetic_sum(", "geometric(", "geometric_sum(")):
            return "sequence"
        if normalized.startswith(("C(", "A(", "binomial(", "factorial(", "coefficient(")) or normalized.endswith("!"):
            return "combinatorics_probability"
        if normalized.startswith(("quadratic_double_root(", "quadratic_has_two_roots(", "quadratic_has_real_root(", "quadratic_no_real_root(", "quadratic_positive_all(")):
            return "parameter"
        if normalized.startswith("derivative("):
            return "calculus_derivative"
        if normalized.startswith("limit("):
            return "calculus_limit"
        if normalized.startswith("integral("):
            return "calculus_integral"
        if problem.expression is not None and (problem.expression.has(sp.I) or problem.domain == "C"):
            return "complex"
        return "expression"
    expression = problem.relation.lhs - problem.relation.rhs
    if expression.has(sp.I) or problem.domain == "C":
        return "complex"
    if expression.has(sp.log) or expression.has(sp.exp) or any(isinstance(power, sp.Pow) and power.exp.has(*expression.free_symbols) for power in expression.atoms(sp.Pow)):
        return "exponential_log"
    if any(expression.has(func) for func in (sp.sin, sp.cos, sp.tan, sp.cot)):
        return "trigonometry"
    if problem.topic != "auto":
        return problem.topic
    return "equation" if isinstance(problem.relation, sp.Equality) else "inequality"
