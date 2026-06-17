from __future__ import annotations

import sympy as sp
from sympy.calculus.util import continuous_domain

def compute_domain(expression: sp.Expr, variable: sp.Symbol, base_domain: sp.Set = sp.S.Reals) -> sp.Set:
    """Computes the continuous domain of an expression."""
    try:
        return continuous_domain(expression, variable, base_domain)
    except Exception:
        return base_domain

def format_domain(domain: sp.Set, variable: sp.Symbol) -> str:
    """Formats a SymPy Set into a readable LaTeX string."""
    if domain == sp.S.Reals:
        return f"{sp.latex(variable)} \\in \\mathbb{{R}}"
    elif domain == sp.S.EmptySet:
        return f"{sp.latex(variable)} \\in \\emptyset"
    else:
        return f"{sp.latex(variable)} \\in {sp.latex(domain)}"

def domain_assumptions_from_expression(expression: sp.Expr, variable: sp.Symbol) -> list[str]:
    """
    Extracts the domain assumptions from an expression.
    Now uses rigorous SymPy Set computations.
    """
    domain = compute_domain(expression, variable)
    
    # If the domain is Reals, no assumptions needed.
    if domain == sp.S.Reals:
        return []
    
    # If it's a ConditionSet or contains one, continuous_domain couldn't simplify it. Fallback to heuristic.
    if domain.has(sp.ConditionSet):
        return _fallback_assumptions(expression, variable)
        
    return [format_domain(domain, variable)]


def _fallback_assumptions(expression: sp.Expr, variable: sp.Symbol) -> list[str]:
    assumptions: list[str] = []
    denominator = sp.denom(expression)
    if denominator != 1 and denominator.has(variable):
        assumptions.extend(_nonzero_assumptions(denominator, variable))
    for power in expression.atoms(sp.Pow):
        exponent = power.exp
        base = power.base
        if base.has(variable) and exponent.is_Rational and exponent.q % 2 == 0:
            assumptions.append(f"{sp.sstr(base)} >= 0")
    for log_expr in expression.atoms(sp.log):
        arg = log_expr.args[0]
        if arg.has(variable):
            assumptions.append(f"{sp.sstr(_normalize_domain_expression(arg))} > 0")
        if len(log_expr.args) > 1:
            base = log_expr.args[1]
            if base.has(variable):
                assumptions.append(f"{sp.sstr(_normalize_domain_expression(base))} > 0 và {sp.sstr(_normalize_domain_expression(base))} != 1")
    return _unique(assumptions)

def _normalize_domain_expression(expression: sp.Expr) -> sp.Expr:
    numerator, denominator = sp.fraction(sp.factor(expression))
    if denominator.is_positive:
        return numerator
    return sp.factor(expression)

def _nonzero_assumptions(expression: sp.Expr, variable: sp.Symbol) -> list[str]:
    factors = sp.factor_list(expression)[1]
    parts = [base for base, _power in factors if base.has(variable)]
    if not parts:
        return [f"{sp.sstr(expression)} khác 0"]
    return [f"{sp.sstr(part)} khác 0" for part in parts]

def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
