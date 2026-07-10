from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import sympy as sp

from app.services.function_domain import FunctionDomain, in_domain


@dataclass(frozen=True)
class RootEvidence:
    value: Any
    exact: bool
    residual: float
    error_bound: float | None

    def payload(self) -> dict[str, Any]:
        exact_value = str(sp.simplify(self.value)) if self.exact else None
        approximation = float(sp.N(self.value))
        return {
            "x": _format_number(approximation),
            "x_exact": exact_value,
            "x_latex": sp.latex(self.value) if self.exact else None,
            "x_approx": _format_number(approximation),
            "verification": "symbolic_exact" if self.exact else "numeric_verified",
            "residual": self.residual,
            "error_bound": self.error_bound,
        }


@dataclass(frozen=True)
class RootAnalysis:
    status: str
    method: str
    roots: tuple[RootEvidence, ...]
    families: tuple[dict[str, Any], ...]
    total_known: int | None
    truncated: bool
    max_points: int
    search_window: tuple[float, float] | None
    warnings: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "roots": [root.payload() for root in self.roots],
            "families": list(self.families),
            "total_known": self.total_known,
            "truncated": self.truncated,
            "max_points": self.max_points,
            "search_window": list(self.search_window) if self.search_window else None,
            "warnings": list(self.warnings),
        }


def analyze_real_roots(
    expr: Any,
    variable: Any,
    domain: FunctionDomain | None,
    *,
    max_points: int = 100,
    search_window: tuple[float, float] = (-20.0, 20.0),
    residual_tolerance: float = 1e-8,
) -> RootAnalysis:
    max_points = max(1, min(int(max_points), 500))
    domain_set = domain.set if domain is not None and domain.set is not None else sp.S.Reals

    try:
        polynomial = sp.Poly(expr, variable)
        if polynomial.free_symbols <= {variable}:
            solution_set = sp.FiniteSet(*polynomial.real_roots()).intersect(domain_set)
        else:
            raise sp.PolynomialError
    except (sp.PolynomialError, NotImplementedError, TypeError, ValueError, AttributeError):
        try:
            solution_set = sp.solveset(expr, variable, domain=sp.S.Reals).intersect(domain_set)
        except (NotImplementedError, TypeError, ValueError, AttributeError):
            solution_set = sp.ConditionSet(variable, sp.Eq(expr, 0), domain_set)

    if solution_set is sp.S.EmptySet:
        return RootAnalysis("complete", "symbolic_exact", (), (), 0, False, max_points, None, ())

    if isinstance(solution_set, sp.FiniteSet):
        validated, rejected = _validated_symbolic_roots(expr, variable, solution_set, domain)
        visible = tuple(validated[:max_points])
        truncated = len(validated) > max_points
        warnings: list[str] = []
        if rejected:
            warnings.append("Một số nghiệm symbolic không vượt qua kiểm tra miền hoặc residual.")
        if truncated:
            warnings.append("Danh sách nghiệm đã được giới hạn.")
        return RootAnalysis(
            "complete" if not rejected and not truncated else "partial",
            "symbolic_exact",
            visible,
            (),
            len(validated),
            truncated,
            max_points,
            None,
            tuple(warnings),
        )

    if not solution_set.has(sp.ConditionSet):
        family = {
            "set_exact": str(solution_set),
            "set_latex": sp.latex(solution_set),
            "parameter_domain": "Z" if solution_set.has(sp.ImageSet) else None,
        }
        return RootAnalysis("complete", "symbolic_exact", (), (family,), None, False, max_points, None, ())

    numeric = tuple(_adaptive_numeric_roots(expr, variable, domain, search_window, residual_tolerance))
    visible = numeric[:max_points]
    warnings = ["Không chứng minh được danh sách nghiệm đầy đủ; chỉ trả nghiệm số đã kiểm chứng trong cửa sổ khảo sát."]
    if len(numeric) > max_points:
        warnings.append("Danh sách nghiệm đã được giới hạn.")
    return RootAnalysis(
        "partial",
        "numeric_adaptive",
        visible,
        (),
        len(numeric),
        len(numeric) > max_points,
        max_points,
        search_window,
        tuple(warnings),
    )


def _validated_symbolic_roots(
    expr: Any,
    variable: Any,
    roots: Any,
    domain: FunctionDomain | None,
) -> tuple[list[RootEvidence], int]:
    validated: list[RootEvidence] = []
    rejected = 0
    for root in sorted(roots, key=sp.default_sort_key):
        try:
            candidate = sp.simplify(root)
            if candidate.is_real is False or not in_domain(domain, candidate):
                rejected += 1
                continue
            real_membership = sp.S.Reals.contains(candidate)
            if real_membership is not sp.S.true and sp.simplify(real_membership) is not sp.S.true:
                rejected += 1
                continue
            exact_residual = sp.simplify(expr.subs(variable, candidate))
            if exact_residual != 0:
                rejected += 1
                continue
            numeric_residual = abs(float(sp.N(exact_residual)))
            validated.append(RootEvidence(candidate, True, numeric_residual, 0.0))
        except (TypeError, ValueError, AttributeError, NotImplementedError):
            rejected += 1
    return validated, rejected


def _adaptive_numeric_roots(
    expr: Any,
    variable: Any,
    domain: FunctionDomain | None,
    window: tuple[float, float],
    tolerance: float,
):
    left_window, right_window = sorted((float(window[0]), float(window[1])))
    if not isfinite(left_window) or not isfinite(right_window) or left_window >= right_window:
        return

    pieces = _numeric_domain_pieces(expr, variable, domain, left_window, right_window)
    candidates: list[RootEvidence] = []
    for left, right in pieces:
        width = right - left
        if width <= 0:
            continue
        previous_count: int | None = None
        stable_rounds = 0
        for sample_count in (32, 64, 128, 256):
            step = width / sample_count
            samples = [(left + step * index, _eval(expr, variable, left + step * index)) for index in range(sample_count + 1)]
            for (a, fa), (b, fb) in zip(samples, samples[1:]):
                if fa is None or fb is None:
                    continue
                if abs(fa) <= tolerance:
                    candidates.append(RootEvidence(a, False, abs(fa), step))
                if fa * fb < 0:
                    root, error = _bisect(expr, variable, a, b, fa, fb, tolerance)
                    residual = _eval(expr, variable, root)
                    if residual is not None and abs(residual) <= tolerance:
                        candidates.append(RootEvidence(root, False, abs(residual), error))
            current_count = len(_deduplicate(candidates))
            stable_rounds = stable_rounds + 1 if current_count == previous_count else 0
            previous_count = current_count
            if stable_rounds >= 2:
                break
        candidates.extend(_tangency_candidates(expr, variable, domain, left, right, tolerance))

    for candidate in _deduplicate(candidates):
        if in_domain(domain, candidate.value):
            yield candidate


def _numeric_domain_pieces(expr: Any, variable: Any, domain: FunctionDomain | None, left: float, right: float) -> list[tuple[float, float]]:
    domain_set = domain.set if domain is not None and domain.set is not None else sp.S.Reals
    window_set = sp.Interval(left, right)
    try:
        active = domain_set.intersect(window_set)
    except (TypeError, AttributeError, NotImplementedError):
        active = window_set
    intervals = active.args if isinstance(active, sp.Union) else (active,)
    pieces: list[tuple[float, float]] = []
    for interval in intervals:
        if not isinstance(interval, sp.Interval):
            continue
        try:
            a = float(interval.start)
            b = float(interval.end)
        except (TypeError, ValueError):
            continue
        margin = max(1e-9, (b - a) * 1e-10)
        pieces.append((a + margin if interval.left_open else a, b - margin if interval.right_open else b))
    return pieces


def _tangency_candidates(expr: Any, variable: Any, domain: FunctionDomain | None, left: float, right: float, tolerance: float) -> list[RootEvidence]:
    try:
        derivative_roots = sp.solveset(sp.diff(expr, variable), variable, domain=sp.Interval(left, right))
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return []
    if not isinstance(derivative_roots, sp.FiniteSet):
        return []
    result: list[RootEvidence] = []
    for point in derivative_roots:
        try:
            numeric = float(sp.N(point))
            residual = _eval(expr, variable, numeric)
        except (TypeError, ValueError, AttributeError):
            continue
        if residual is not None and abs(residual) <= tolerance and in_domain(domain, point):
            result.append(RootEvidence(numeric, False, abs(residual), tolerance))
    return result


def _bisect(expr: Any, variable: Any, left: float, right: float, f_left: float, f_right: float, tolerance: float) -> tuple[float, float]:
    for _ in range(80):
        middle = (left + right) / 2
        f_middle = _eval(expr, variable, middle)
        if f_middle is None:
            break
        if abs(f_middle) <= tolerance or right - left <= tolerance:
            return middle, (right - left) / 2
        if f_left * f_middle <= 0:
            right, f_right = middle, f_middle
        else:
            left, f_left = middle, f_middle
    return (left + right) / 2, (right - left) / 2


def _deduplicate(candidates: list[RootEvidence]) -> list[RootEvidence]:
    ordered = sorted(candidates, key=lambda item: float(sp.N(item.value)))
    result: list[RootEvidence] = []
    for candidate in ordered:
        value = float(sp.N(candidate.value))
        threshold = max(candidate.error_bound or 0.0, 1e-7)
        if result and abs(value - float(sp.N(result[-1].value))) <= max(threshold, result[-1].error_bound or 0.0, 1e-7):
            if candidate.residual < result[-1].residual:
                result[-1] = candidate
            continue
        result.append(candidate)
    return result


def _eval(expr: Any, variable: Any, value: float) -> float | None:
    try:
        numeric = float(sp.N(expr.subs(variable, value)))
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None
    return numeric if isfinite(numeric) else None


def _format_number(value: float) -> str:
    text = f"{value:.10g}"
    return "0" if text in {"-0", "-0.0"} else text
