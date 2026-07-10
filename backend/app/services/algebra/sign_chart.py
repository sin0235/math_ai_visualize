from __future__ import annotations

import sympy as sp


def sign_chart_summary(expression: sp.Expr, variable: sp.Symbol) -> str | None:
    """Build a textual sign chart using SymPy real roots / solveset (stdlib-free)."""
    numerator, denominator = sp.fraction(sp.factor(expression))
    candidates: set[sp.Expr] = set()
    for part in (numerator, denominator):
        for root in _real_critical_points(part, variable):
            if root.is_real is False:
                continue
            candidates.add(sp.simplify(root))
    if not candidates:
        return None
    ordered = sorted(candidates, key=sp.default_sort_key)
    intervals = _sample_intervals(ordered)
    signs = []
    for start, end, sample in intervals:
        sign = _sign_at(expression, variable, sample)
        if sign is None:
            continue
        signs.append(f"{_format_interval_label(start, end)}: {sign}")
    summary = "Các mốc xét dấu: " + "; ".join(sp.sstr(item) for item in ordered)
    if signs:
        summary += ". Dấu trên từng khoảng: " + "; ".join(signs)
    return summary


def _real_critical_points(part: sp.Expr, variable: sp.Symbol) -> list[sp.Expr]:
    if part == 0 or part == 1 or not part.has(variable):
        return []
    try:
        poly = sp.Poly(sp.together(part).as_numer_denom()[0], variable)
        return [sp.simplify(r) for r in poly.real_roots()]
    except Exception:
        pass
    try:
        sol = sp.solveset(part, variable, domain=sp.S.Reals)
        if isinstance(sol, sp.FiniteSet):
            return [sp.simplify(r) for r in sol]
    except Exception:
        pass
    try:
        return [sp.simplify(r) for r in sp.solve(sp.Eq(part, 0), variable) if r.is_real is not False]
    except Exception:
        return []


def _sample_intervals(points: list[sp.Expr]) -> list[tuple[sp.Expr, sp.Expr, sp.Expr]]:
    intervals: list[tuple[sp.Expr, sp.Expr, sp.Expr]] = []
    for index in range(len(points) + 1):
        start = -sp.oo if index == 0 else points[index - 1]
        end = sp.oo if index == len(points) else points[index]
        if start is -sp.oo:
            sample = end - 1
        elif end is sp.oo:
            sample = start + 1
        else:
            sample = (start + end) / 2
        intervals.append((start, end, sample))
    return intervals


def _sign_at(expression: sp.Expr, variable: sp.Symbol, sample: sp.Expr) -> str | None:
    try:
        value = sp.simplify(expression.subs(variable, sample))
        if value.is_positive:
            return "+"
        if value.is_negative:
            return "-"
        if value.is_zero:
            return "0"
    except Exception:
        return None
    return None


def _format_interval_label(start: sp.Expr, end: sp.Expr) -> str:
    return f"({_format_bound(start)}; {_format_bound(end)})"


def _format_bound(value: sp.Expr) -> str:
    if value is sp.oo:
        return "+∞"
    if value is -sp.oo:
        return "-∞"
    return sp.sstr(value)
