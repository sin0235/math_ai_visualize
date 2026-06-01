from __future__ import annotations

import sympy as sp

from app.services.algebra.parser import ParsedAlgebraProblem


def classify_algebra_problem(problem: ParsedAlgebraProblem) -> str:
    if len(problem.relations) > 1:
        return "system"
    if problem.relation is None:
        if problem.expression is not None and (problem.expression.has(sp.I) or problem.domain == "C"):
            return "complex"
        return problem.topic if problem.topic != "auto" else "expression"
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
