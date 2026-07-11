from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

import sympy as sp

from app.services.function_domain import FunctionDomain


DEFAULT_MAX_POINTS = 500
MIN_POINTS_PER_COMPONENT = 17
MAX_ADAPTIVE_DEPTH = 10


def build_graph_analysis(
    expr: Any,
    variable: Any,
    domain: FunctionDomain | None,
    analysis: Mapping[str, Any],
    *,
    requested_interval: Mapping[str, Any] | None = None,
    plot_window: tuple[float, float] | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> dict[str, Any]:
    point_cap = max(32, min(int(max_points), 2_000))
    window = _resolve_window(analysis, domain, plot_window)
    active_set = _active_domain(domain, requested_interval, window)
    singular_points = _singular_points(analysis, window)
    components = _graph_components(expr, variable, active_set, singular_points)
    feature_points = _feature_points(analysis, window)
    warnings: list[str] = []
    if not components:
        return {
            "status": "unknown",
            "method": "adaptive_domain_components",
            "window": _window_payload(window),
            "max_points": point_cap,
            "point_count": 0,
            "segments": [],
            "singularities": [_number_payload(point) for point in singular_points],
            "warnings": ["Không có thành phần miền xác định trong cửa sổ vẽ."],
        }

    budget_per_component = max(MIN_POINTS_PER_COMPONENT, point_cap // len(components))
    segments: list[dict[str, Any]] = []
    total_points = 0
    for index, (component, branch_expr) in enumerate(components):
        remaining = max(2, point_cap - total_points)
        budget = min(budget_per_component, remaining)
        points, reached_cap = _adaptive_component_points(
            branch_expr,
            variable,
            component,
            feature_points,
            budget,
        )
        if len(points) < 2:
            warnings.append(f"Không đủ điểm hữu hạn trên thành phần {sp.sstr(component)}.")
            continue
        total_points += len(points)
        if reached_cap:
            warnings.append(f"Thành phần {index + 1} đạt giới hạn điểm sampling.")
        segments.append({
            "component_id": f"domain-{index + 1}",
            "expression_exact": sp.sstr(branch_expr),
            "expression_latex": sp.latex(branch_expr),
            "start": _bound_payload(component.start),
            "end": _bound_payload(component.end),
            "left_open": bool(component.left_open),
            "right_open": bool(component.right_open),
            "left_endpoint": _endpoint_payload(branch_expr, variable, component.start, bool(component.left_open), "+"),
            "right_endpoint": _endpoint_payload(branch_expr, variable, component.end, bool(component.right_open), "-"),
            "points": points,
            "sample_count": len(points),
            "verification": "domain_component_adaptive",
        })
        if total_points >= point_cap:
            warnings.append("Đã đạt giới hạn tổng số điểm đồ thị.")
            break

    return {
        "status": "complete" if segments and not warnings else "partial" if segments else "unknown",
        "method": "adaptive_domain_components",
        "window": _window_payload(window),
        "max_points": point_cap,
        "point_count": total_points,
        "segments": segments,
        "singularities": [_number_payload(point) for point in singular_points],
        "features": [_number_payload(point) for point in feature_points],
        "warnings": _unique(warnings),
    }


def flatten_graph_points(graph_analysis: Mapping[str, Any] | None) -> list[dict[str, float]]:
    if not graph_analysis:
        return []
    return [
        {"x": float(point["x"]), "y": float(point["y"])}
        for segment in graph_analysis.get("segments", [])
        for point in segment.get("points", [])
    ]


def _resolve_window(
    analysis: Mapping[str, Any],
    domain: FunctionDomain | None,
    requested: tuple[float, float] | None,
) -> tuple[float, float]:
    if requested is not None:
        left, right = sorted((float(requested[0]), float(requested[1])))
        if isfinite(left) and isfinite(right) and left < right:
            return left, right

    anchors = _numeric_feature_values(analysis)
    if domain is not None:
        for component in domain.components:
            for bound in (component.start, component.end):
                value = _finite_float(bound)
                if value is not None:
                    anchors.append(value)
    if anchors:
        left = min([0.0, *anchors])
        right = max([0.0, *anchors])
        span = max(right - left, 2.0)
        margin = max(1.0, span * 0.3)
        return left - margin, right + margin

    periodicity = analysis.get("periodicity") or {}
    period = _finite_float(periodicity.get("period"))
    if period is not None and period > 0:
        return -period, period
    return -6.0, 6.0


def _active_domain(
    domain: FunctionDomain | None,
    requested_interval: Mapping[str, Any] | None,
    window: tuple[float, float],
):
    domain_set = domain.set if domain is not None and domain.set is not None else sp.S.Reals
    left, right = (sp.Rational(str(window[0])), sp.Rational(str(window[1])))
    active = domain_set.intersect(sp.Interval(left, right))
    if requested_interval:
        a = sp.Rational(str(requested_interval.get("a", left)))
        b = sp.Rational(str(requested_interval.get("b", right)))
        requested = sp.Interval(
            a,
            b,
            left_open=bool(requested_interval.get("open_a", False)),
            right_open=bool(requested_interval.get("open_b", False)),
        )
        active = active.intersect(requested)
    return active


def _graph_components(
    expr: Any,
    variable: Any,
    active_set: Any,
    singular_points: list[Any],
) -> list[tuple[Any, Any]]:
    branch_domains = _piecewise_branch_domains(expr, variable, active_set)
    return [
        (component, branch_expr)
        for branch_domain, branch_expr in branch_domains
        for component in _split_components(branch_domain, singular_points)
    ]


def _piecewise_branch_domains(expr: Any, variable: Any, active_set: Any) -> list[tuple[Any, Any]]:
    if not isinstance(expr, sp.Piecewise):
        return [(active_set, expr)]

    covered = sp.S.EmptySet
    branches: list[tuple[Any, Any]] = []
    for branch_expr, condition in expr.args:
        if condition is True or condition is sp.S.true:
            condition_set = sp.S.Reals - covered
        elif set(condition.free_symbols) <= {variable}:
            try:
                condition_set = condition.as_set() - covered
            except (TypeError, ValueError, AttributeError, NotImplementedError):
                continue
        else:
            continue
        branch_domain = active_set.intersect(condition_set)
        if branch_domain is not sp.S.EmptySet:
            branches.append((branch_domain, branch_expr))
        covered = covered.union(condition_set)
    return branches


def _split_components(active_set: Any, singular_points: list[Any]) -> list[Any]:
    intervals = _iter_intervals(active_set)
    result: list[Any] = []
    for interval in intervals:
        inside = [point for point in singular_points if _contains_interior(interval, point)]
        bounds = [interval.start, *sorted(set(inside), key=sp.default_sort_key), interval.end]
        for index, (left, right) in enumerate(zip(bounds, bounds[1:])):
            if left == right:
                continue
            result.append(sp.Interval(
                left,
                right,
                left_open=bool(interval.left_open) if index == 0 else True,
                right_open=bool(interval.right_open) if index == len(bounds) - 2 else True,
            ))
    return result


def _iter_intervals(value_set: Any) -> list[Any]:
    if value_set is sp.S.EmptySet:
        return []
    if isinstance(value_set, sp.Interval):
        return [value_set]
    if isinstance(value_set, sp.Union):
        return [part for part in value_set.args if isinstance(part, sp.Interval)]
    return []


def _singular_points(analysis: Mapping[str, Any], window: tuple[float, float]) -> list[Any]:
    points: list[Any] = []
    for item in (analysis.get("asymptotes_v2") or {}).get("vertical", []):
        _append_exact_point(points, item.get("x_exact") or item.get("x"), window)
    for item in analysis.get("removable_holes", []):
        _append_exact_point(points, item.get("x_exact") or item.get("x"), window)
    for family in (analysis.get("asymptotes_v2") or {}).get("periodic_vertical_families", []):
        raw = family.get("x_exact")
        if not raw:
            continue
        k = sp.Symbol("k", integer=True)
        try:
            family_expr = sp.sympify(raw, locals={"k": k, "pi": sp.pi})
        except (TypeError, ValueError, sp.SympifyError):
            continue
        for index in range(-64, 65):
            _append_exact_point(points, family_expr.subs(k, index), window)
    return sorted(set(points), key=sp.default_sort_key)


def _feature_points(analysis: Mapping[str, Any], window: tuple[float, float]) -> list[Any]:
    points: list[Any] = []
    for item in analysis.get("critical_points_v2", []):
        _append_exact_point(points, item.get("x_exact") or item.get("x"), window)
    roots = (analysis.get("x_intercepts_v2") or {}).get("roots", [])
    for item in roots:
        _append_exact_point(points, item.get("x_exact") or item.get("x"), window)
    for item in analysis.get("removable_holes", []):
        _append_exact_point(points, item.get("x_exact") or item.get("x"), window)
    points.extend(_singular_points(analysis, window))
    return sorted(set(points), key=sp.default_sort_key)


def _append_exact_point(points: list[Any], raw: Any, window: tuple[float, float]) -> None:
    try:
        point = sp.sympify(raw)
        numeric = float(sp.N(point))
    except (TypeError, ValueError, AttributeError, sp.SympifyError):
        return
    if isfinite(numeric) and window[0] <= numeric <= window[1]:
        points.append(sp.simplify(point))


def _numeric_feature_values(analysis: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    groups = [
        analysis.get("critical_points_v2", []),
        (analysis.get("x_intercepts_v2") or {}).get("roots", []),
        analysis.get("removable_holes", []),
        (analysis.get("asymptotes_v2") or {}).get("vertical", []),
    ]
    for group in groups:
        for item in group:
            value = _finite_float(item.get("x_exact") or item.get("x"))
            if value is not None:
                values.append(value)
    return values


def _adaptive_component_points(
    expr: Any,
    variable: Any,
    component: Any,
    features: list[Any],
    budget: int,
) -> tuple[list[dict[str, float]], bool]:
    left = float(sp.N(component.start))
    right = float(sp.N(component.end))
    span = right - left
    margin = max(1e-9, span * 1e-7)
    sample_left = left + margin if component.left_open else left
    sample_right = right - margin if component.right_open else right
    if sample_left >= sample_right:
        return [], False

    seeds = [sample_left, sample_right]
    seeds.extend(
        numeric
        for point in features
        if (numeric := _finite_float(point)) is not None and sample_left < numeric < sample_right
    )
    seeds.extend(sample_left + span * index / 16 for index in range(1, 16))
    seeds = sorted(set(seeds))
    values = {value: _evaluate(expr, variable, value) for value in seeds}
    reached_cap = False

    def refine(a: float, b: float, depth: int) -> None:
        nonlocal reached_cap
        if len(values) >= budget:
            reached_cap = True
            return
        fa = values.get(a)
        fb = values.get(b)
        middle = (a + b) / 2
        fm = _evaluate(expr, variable, middle)
        values[middle] = fm
        if depth >= MAX_ADAPTIVE_DEPTH or fa is None or fb is None or fm is None:
            return
        linear_middle = (fa + fb) / 2
        scale = max(1.0, abs(fa), abs(fb), abs(fm))
        curvature_error = abs(fm - linear_middle) / scale
        slope_change = abs((fm - fa) - (fb - fm)) / scale
        if curvature_error > 0.008 or slope_change > 0.02:
            refine(a, middle, depth + 1)
            refine(middle, b, depth + 1)

    for a, b in zip(seeds, seeds[1:]):
        refine(a, b, 0)
        if reached_cap:
            break

    points = [
        {"x": round(value, 10), "y": round(y_value, 10)}
        for value in sorted(values)
        if (y_value := values[value]) is not None
    ]
    return points[:budget], reached_cap or len(points) > budget


def _evaluate(expr: Any, variable: Any, value: float) -> float | None:
    try:
        numeric = float(sp.N(expr.subs(variable, value)))
    except (TypeError, ValueError, AttributeError, OverflowError, ZeroDivisionError):
        return None
    return numeric if isfinite(numeric) else None


def _endpoint_payload(expr: Any, variable: Any, point: Any, is_open: bool, direction: str) -> dict[str, Any]:
    payload = {**_bound_payload(point), "open": is_open, "attained": not is_open}
    if point in (-sp.oo, sp.oo):
        payload["y"] = None
        return payload
    if is_open:
        try:
            one_sided = sp.limit(expr, variable, point, dir=direction)
            payload["y"] = _finite_float(one_sided)
        except (TypeError, ValueError, AttributeError, NotImplementedError):
            payload["y"] = None
        return payload
    payload["y"] = _evaluate(expr, variable, float(sp.N(point)))
    return payload


def _bound_payload(value: Any) -> dict[str, Any]:
    if value == -sp.oo:
        return {"exact": "-oo", "latex": r"-\infty", "approx": None}
    if value == sp.oo:
        return {"exact": "oo", "latex": r"\infty", "approx": None}
    return {"exact": sp.sstr(value), "latex": sp.latex(value), "approx": _finite_float(value)}


def _number_payload(value: Any) -> dict[str, Any]:
    return {"exact": sp.sstr(value), "latex": sp.latex(value), "approx": _finite_float(value)}


def _window_payload(window: tuple[float, float]) -> dict[str, float]:
    return {"x_min": window[0], "x_max": window[1]}


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(sp.N(sp.sympify(value)))
    except (TypeError, ValueError, AttributeError, sp.SympifyError):
        return None
    return numeric if isfinite(numeric) else None


def _contains_interior(interval: Any, point: Any) -> bool:
    try:
        return sp.simplify(interval.start < point) is sp.S.true and sp.simplify(point < interval.end) is sp.S.true
    except (TypeError, ValueError, AttributeError):
        return False


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))