from __future__ import annotations

import sympy as sp


def format_solution_set(solution_set: sp.Set) -> str:
    if solution_set is sp.EmptySet:
        return "Vô nghiệm."
    if isinstance(solution_set, sp.FiniteSet):
        values = sorted(solution_set, key=sp.default_sort_key)
        return "Tập nghiệm: {" + "; ".join(sp.sstr(value) for value in values) + "}"
    return f"Tập nghiệm: {sp.sstr(solution_set)}"


def format_interval_set(solution_set: sp.Set) -> str:
    if solution_set is sp.EmptySet:
        return "Vô nghiệm."
    return f"Tập nghiệm: {_format_set(solution_set)}"


def _format_set(solution_set: sp.Set) -> str:
    if isinstance(solution_set, sp.Interval):
        return _format_interval(solution_set)
    if isinstance(solution_set, sp.Union):
        return " ∪ ".join(_format_set(arg) for arg in solution_set.args)
    if isinstance(solution_set, sp.FiniteSet):
        values = sorted(solution_set, key=sp.default_sort_key)
        return "{" + "; ".join(sp.sstr(value) for value in values) + "}"
    return sp.sstr(solution_set)


def _format_interval(interval: sp.Interval) -> str:
    left = "(" if interval.left_open else "["
    right = ")" if interval.right_open else "]"
    return f"{left}{_format_bound(interval.start)}; {_format_bound(interval.end)}{right}"


def _format_bound(value: sp.Expr) -> str:
    if value is sp.oo:
        return "+∞"
    if value is -sp.oo:
        return "-∞"
    return sp.sstr(value)


def solution_values(solution_set: sp.Set) -> list[sp.Expr] | None:
    if solution_set is sp.EmptySet:
        return []
    if isinstance(solution_set, sp.FiniteSet):
        return sorted(list(solution_set), key=sp.default_sort_key)
    return None
