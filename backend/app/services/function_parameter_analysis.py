from __future__ import annotations

from typing import Any

import sympy as sp


MAX_PARAMETER_BOUNDARIES = 16


def analyze_parameter_cases(expr: Any, variable: Any, parameter: Any) -> dict[str, Any]:
    boundaries, boundary_warnings, supported = _parameter_boundaries(expr, variable, parameter)
    if not supported:
        return {
            "status": "partial",
            "parameter": str(parameter),
            "boundaries": [],
            "cases": [{
                "condition_exact": "Reals",
                "condition_latex": r"m \in \mathbb{R}",
                "status": "unknown",
                "verification": "unsupported_symbolic_family",
                "degree": None,
                "domain_exact": None,
                "stationary_root_count": None,
                "extrema_count": None,
                "root_count": None,
                "vertical_asymptote_count": None,
                "warnings": ["Chưa chứng minh được phân hoạch tham số cho họ hàm này."],
            }],
            "legacy_conditions": [],
            "warnings": boundary_warnings or ["Chế độ symbolic chỉ kết luận các case đại số chứng minh được."],
        }

    cases = [
        _case_payload(expr, variable, parameter, condition, probe, is_boundary)
        for condition, probe, is_boundary in _case_probes(boundaries, parameter)
    ]
    complete = bool(cases) and all(case["status"] == "complete" for case in cases)
    warnings = list(boundary_warnings)
    if not complete:
        warnings.append("Một số case tham số chưa chứng minh được đầy đủ.")
    return {
        "status": "complete" if complete else "partial",
        "parameter": str(parameter),
        "boundaries": [_number_payload(value) for value in boundaries],
        "cases": cases,
        "legacy_conditions": _legacy_conditions(cases),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _legacy_conditions(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": case["condition_exact"],
            "condition_latex": case["condition_latex"],
            "solution": f"degree={case['degree']}, extrema={case['extrema_count']}",
            "warnings": list(case["warnings"]),
        }
        for case in cases
        if case["status"] == "complete"
    ]


def _parameter_boundaries(expr: Any, variable: Any, parameter: Any) -> tuple[list[Any], list[str], bool]:
    try:
        numerator, denominator = sp.fraction(sp.together(expr))
        derivative_numerator, derivative_denominator = sp.fraction(sp.together(sp.diff(expr, variable)))
        polynomials = [
            sp.Poly(numerator, variable),
            sp.Poly(denominator, variable),
            sp.Poly(derivative_numerator, variable),
            sp.Poly(derivative_denominator, variable),
        ]
    except (sp.PolynomialError, TypeError, ValueError):
        return [], ["Họ hàm không phải đại số hữu tỉ theo x."], False

    equations: list[Any] = []
    for polynomial in polynomials:
        if polynomial.is_zero:
            continue
        leading = sp.simplify(polynomial.LC())
        if parameter in leading.free_symbols:
            equations.append(leading)
        if polynomial.degree() >= 2:
            try:
                discriminant = sp.simplify(sp.discriminant(polynomial.as_expr(), variable))
            except (sp.PolynomialError, TypeError, ValueError):
                continue
            if parameter in discriminant.free_symbols:
                equations.append(discriminant)

    for first, second in ((derivative_numerator, denominator), (numerator, denominator)):
        try:
            resultant = sp.simplify(sp.resultant(first, second, variable))
        except (sp.PolynomialError, TypeError, ValueError):
            continue
        if resultant != 0 and parameter in resultant.free_symbols:
            equations.append(resultant)

    boundaries: list[Any] = []
    warnings: list[str] = []
    for equation in equations:
        try:
            roots = sp.solveset(equation, parameter, domain=sp.S.Reals)
        except (TypeError, ValueError, NotImplementedError):
            warnings.append(f"Không giải được boundary tham số: {sp.sstr(equation)} = 0.")
            continue
        if not isinstance(roots, sp.FiniteSet):
            warnings.append(f"Boundary tham số chưa hữu hạn: {sp.sstr(equation)} = 0.")
            continue
        boundaries.extend(root for root in roots if root.is_real is True and root.is_finite is True)

    unique = sorted(set(boundaries), key=lambda value: float(sp.N(value)))
    if len(unique) > MAX_PARAMETER_BOUNDARIES:
        return [], [f"Số boundary tham số vượt quá {MAX_PARAMETER_BOUNDARIES}."], False
    return unique, warnings, True


def _case_probes(boundaries: list[Any], parameter: Any) -> list[tuple[Any, Any, bool]]:
    if not boundaries:
        return [(sp.S.Reals, sp.Integer(0), False)]

    cases: list[tuple[Any, Any, bool]] = []
    first = boundaries[0]
    cases.append((sp.Interval.open(-sp.oo, first), _outside_probe(first, -1), False))
    for index, boundary in enumerate(boundaries):
        cases.append((sp.FiniteSet(boundary), boundary, True))
        if index + 1 < len(boundaries):
            right = boundaries[index + 1]
            cases.append((sp.Interval.open(boundary, right), sp.simplify((boundary + right) / 2), False))
    last = boundaries[-1]
    cases.append((sp.Interval.open(last, sp.oo), _outside_probe(last, 1), False))
    return cases


def _outside_probe(boundary: Any, direction: int) -> Any:
    numeric = float(sp.N(boundary))
    step = max(1, abs(numeric) * 0.5)
    return sp.Rational(str(numeric + direction * step))


def _case_payload(
    expr: Any,
    variable: Any,
    parameter: Any,
    condition: Any,
    probe: Any,
    is_boundary: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    substituted = sp.simplify(expr.subs(parameter, probe))
    try:
        numerator, _ = sp.fraction(sp.together(substituted))
        degree = int(sp.Poly(numerator, variable).degree())
    except (sp.PolynomialError, TypeError, ValueError, OverflowError):
        degree = None
        warnings.append("Không xác định được bậc theo x.")

    domain = None
    try:
        sampled_domain = sp.calculus.util.continuous_domain(substituted, variable, sp.S.Reals)
        symbolic_domain = None if is_boundary else _rational_symbolic_domain(expr, variable)
        domain = symbolic_domain if symbolic_domain is not None else sampled_domain
        domain_exact = sp.sstr(domain)
    except (TypeError, ValueError, NotImplementedError):
        domain_exact = None
        warnings.append("Không xác định được tập xác định của case.")

    derivative = sp.simplify(sp.diff(substituted, variable))
    stationary_count, extrema_count = _stationary_counts(derivative, variable)
    root_count, vertical_asymptote_count = _case_feature_counts(substituted, variable)
    if stationary_count is None:
        warnings.append("Không chứng minh được số nghiệm thực của đạo hàm.")
    if root_count is None:
        warnings.append("Không chứng minh được số nghiệm thực của hàm trong case.")
    if vertical_asymptote_count is None:
        warnings.append("Không chứng minh được số tiệm cận đứng trong case.")

    return {
        "condition_exact": sp.sstr(condition),
        "condition_latex": sp.latex(condition),
        "sample_exact": sp.sstr(probe),
        "status": "complete" if not warnings else "unknown",
        "verification": "exact_boundary" if is_boundary else "algebraic_invariant_interval",
        "degree": degree,
        "domain_exact": domain_exact,
        "stationary_root_count": stationary_count,
        "extrema_count": extrema_count,
        "root_count": root_count,
        "vertical_asymptote_count": vertical_asymptote_count,
        "warnings": warnings,
    }


def _rational_symbolic_domain(expr: Any, variable: Any):
    try:
        _, denominator = sp.fraction(sp.together(expr))
        excluded = sp.solveset(denominator, variable, domain=sp.S.Reals)
    except (TypeError, ValueError, NotImplementedError):
        return None
    if isinstance(excluded, sp.FiniteSet) or excluded is sp.S.EmptySet:
        return sp.S.Reals - excluded
    try:
        roots = sp.solve(denominator, variable)
    except (TypeError, ValueError, NotImplementedError):
        return None
    if all(variable not in root.free_symbols for root in roots):
        return sp.S.Reals - sp.FiniteSet(*roots)
    return None


def _case_feature_counts(expr: Any, variable: Any) -> tuple[int | None, int | None]:
    try:
        domain = sp.calculus.util.continuous_domain(expr, variable, sp.S.Reals)
        roots = sp.solveset(expr, variable, domain=domain)
        root_count = len(roots) if isinstance(roots, sp.FiniteSet) else None
    except (TypeError, ValueError, NotImplementedError):
        root_count = None

    try:
        _, denominator = sp.fraction(sp.cancel(expr))
        candidates = sp.solveset(denominator, variable, domain=sp.S.Reals)
        if candidates is sp.S.EmptySet:
            return root_count, 0
        if not isinstance(candidates, sp.FiniteSet):
            return root_count, None
        asymptote_count = 0
        for point in candidates:
            left = sp.limit(expr, variable, point, dir="-")
            right = sp.limit(expr, variable, point, dir="+")
            if left in (sp.oo, -sp.oo) or right in (sp.oo, -sp.oo):
                asymptote_count += 1
    except (TypeError, ValueError, NotImplementedError):
        return root_count, None
    return root_count, asymptote_count


def _stationary_counts(derivative: Any, variable: Any) -> tuple[int | None, int | None]:
    try:
        roots = sp.solveset(derivative, variable, domain=sp.S.Reals)
    except (TypeError, ValueError, NotImplementedError):
        return None, None
    if roots is sp.S.EmptySet:
        return 0, 0
    if not isinstance(roots, sp.FiniteSet):
        return None, None

    ordered = sorted(roots, key=lambda value: float(sp.N(value)))
    extrema = 0
    for root in ordered:
        distances = [
            abs(float(sp.N(root - neighbor)))
            for neighbor in ordered
            if neighbor != root
        ]
        epsilon = sp.Rational(str(min(distances) / 3)) if distances else sp.Rational(1, 10)
        try:
            left = sp.sign(sp.N(derivative.subs(variable, root - epsilon)))
            right = sp.sign(sp.N(derivative.subs(variable, root + epsilon)))
        except (TypeError, ValueError):
            continue
        if left != right and left != 0 and right != 0:
            extrema += 1
    return len(ordered), extrema


def _number_payload(value: Any) -> dict[str, Any]:
    return {
        "exact": sp.sstr(value),
        "latex": sp.latex(value),
        "approx": float(sp.N(value)),
    }