from __future__ import annotations

import sympy as sp

from app.services.algebra.parser import ParsedAlgebraProblem


def classify_algebra_problem(problem: ParsedAlgebraProblem) -> str:
    if len(problem.relations) > 1:
        equalities = [isinstance(rel, sp.Equality) for rel in problem.relations]
        if all(equalities):
            return "system"
        if not any(equalities):
            # Multi-inequality / chained inequality → inequality solver intersection path
            return "inequality"
        # Mixed equality + inequality is not handled by system or inequality solvers.
        return "unsupported"
    if problem.relation is None:
        if problem.topic != "auto":
            return problem.topic
        normalized = problem.normalized_input.strip()
        if normalized.startswith(("arithmetic(", "arithmetic_sum(", "geometric(", "geometric_sum(")):
            return "sequence"
        if (
            normalized.startswith((
                "C(", "A(", "binomial(", "factorial(", "coefficient(",
                "P(", "P_not(", "P_and(", "Pcomb(",
                "probability(", "probability_not(", "probability_and(", "probability_comb(",
            ))
            or normalized.endswith("!")
        ):
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
    is_equality = isinstance(problem.relation, sp.Equality)
    if expression.has(sp.I) or problem.domain == "C":
        return "complex"
    has_exp_log = (
        expression.has(sp.log)
        or expression.has(sp.exp)
        or any(isinstance(power, sp.Pow) and power.exp.has(*expression.free_symbols) for power in expression.atoms(sp.Pow))
    )
    has_trig = any(expression.has(func) for func in (sp.sin, sp.cos, sp.tan, sp.cot))
    # Inequality with exp/log/trig → inequality solver (exp_log/trig solvers are equality-only).
    if has_exp_log:
        return "exponential_log" if is_equality else "inequality"
    if has_trig:
        return "trigonometry" if is_equality else "inequality"
    # Relation type wins over a coarse topic=equation/inequality hint (e.g. "!=" must not enter equation solver).
    if problem.topic not in {"auto", "equation", "inequality"}:
        return problem.topic
    return "equation" if is_equality else "inequality"
