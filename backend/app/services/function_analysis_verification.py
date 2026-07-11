from __future__ import annotations

from typing import Any, Mapping

import sympy as sp

from app.services.function_domain import in_domain


Check = dict[str, Any]


def build_verification_report(data: Mapping[str, Any]) -> dict[str, Any]:
    checks = [
        _verify_domain(data),
        _verify_derivative(data),
        _verify_critical_membership(data),
        _verify_interval_signs(data),
        _verify_inflections(data),
        _verify_asymptotes(data),
        _verify_intercepts(data),
    ]
    if (data.get("line_analysis") or {}).get("mode") == "tangent_at":
        checks.append(_verify_tangent(data))
    if data.get("interval_analysis"):
        checks.append(_verify_extrema_attainment(data))
    checks.append(_verify_graph_domain(data))

    truncated = _has_truncation(data)
    possibly_incomplete = truncated or _has_incomplete_stage(data) or any(check["status"] in {"warn", "unknown"} for check in checks)
    if any(check["status"] == "fail" for check in checks):
        status = "failed"
    elif all(check["status"] == "unknown" for check in checks):
        status = "unverified"
    elif possibly_incomplete:
        status = "partially_verified"
    else:
        status = "verified"
    return {
        "status": status,
        "checks": checks,
        "truncated": truncated,
        "possibly_incomplete": possibly_incomplete,
    }


def _verify_domain(data: Mapping[str, Any]) -> Check:
    partition = data.get("domain_partition_v2") or {}
    domain_info = data.get("_domain_info")
    if domain_info is None or not partition:
        return _check("domain", "unknown", "unknown", "Không có domain evidence để kiểm chứng.")
    if partition.get("status") != "complete":
        return _check("domain", "warn", "fallback", "Domain partition chưa complete.")
    expected = len(getattr(domain_info, "components", []))
    actual = len(partition.get("components") or [])
    if expected != actual:
        return _check("domain", "fail", "symbolic", "Số domain component không khớp.")
    return _check("domain", "pass", "symbolic")


def _verify_derivative(data: Mapping[str, Any]) -> Check:
    expression = data.get("_evaluated_expr") or data.get("_parsed_expr")
    derivative = data.get("derivative")
    if expression is None or not derivative:
        return _check("derivative_backcheck", "unknown", "unknown", "Không có đạo hàm để backcheck.")
    try:
        variable = _variable(expression)
        derivative_expr = sp.sympify(derivative, locals={variable.name: variable})
        difference = sp.simplify(sp.diff(expression, variable) - derivative_expr)
    except Exception:
        return _check("derivative_backcheck", "unknown", "unknown", "Không backcheck được đạo hàm.")
    return _check("derivative_backcheck", "pass" if difference == 0 else "fail", "symbolic", None if difference == 0 else "Đạo hàm không khớp biểu thức.")


def _verify_critical_membership(data: Mapping[str, Any]) -> Check:
    points = data.get("critical_points_v2") or data.get("critical_points") or []
    domain_info = data.get("_domain_info")
    if domain_info is None:
        return _check("critical_point_membership", "unknown", "unknown", "Không có domain evidence.")
    try:
        outside = [point for point in points if not in_domain(domain_info, sp.sympify(point.get("x_exact") or point["x"]))]
    except Exception:
        return _check("critical_point_membership", "unknown", "unknown", "Không kiểm tra được membership.")
    return _check("critical_point_membership", "fail" if outside else "pass", "symbolic", "Có điểm tới hạn ngoài tập xác định." if outside else None)


def _verify_interval_signs(data: Mapping[str, Any]) -> Check:
    chart = data.get("monotonicity_v2") or {}
    segments = chart.get("segments") or []
    if not chart:
        return _check("monotonicity_components", "unknown", "unknown", "Không có sign chart.")
    if any(segment.get("verification") == "unknown" or segment.get("derivative_sign") == "unknown" for segment in segments):
        return _check("monotonicity_components", "warn", "fallback", "Có khoảng chưa xác định được dấu đạo hàm.")
    numeric = any(segment.get("verification") not in {"exact", "periodic_exact"} for segment in segments)
    return _check("monotonicity_components", "warn" if numeric else "pass", "numeric" if numeric else "symbolic", "Có khoảng dùng numeric evidence." if numeric else None)


def _verify_inflections(data: Mapping[str, Any]) -> Check:
    chart = data.get("concavity_v2") or {}
    if chart.get("status") == "unknown":
        return _check("inflection_sign_change", "unknown", "unknown", "Concavity analysis chưa xác định.")
    points = data.get("inflection_points_v2") or []
    invalid = [point for point in points if point.get("evidence") != "second_derivative_sign_change" or point.get("left_sign") == point.get("right_sign")]
    if invalid:
        return _check("inflection_sign_change", "fail", "symbolic", "Có điểm uốn thiếu sign change evidence.")
    if chart.get("status") == "partial":
        return _check("inflection_sign_change", "warn", "fallback", "Concavity analysis chưa complete.")
    return _check("inflection_sign_change", "pass", "symbolic")


def _verify_asymptotes(data: Mapping[str, Any]) -> Check:
    asymptotes = data.get("asymptotes_v2")
    limit_stage = (data.get("stage_statuses") or {}).get("limits") or {}
    if asymptotes is None:
        return _check("asymptote_limits", "unknown", "unknown", "Không có asymptote evidence.")
    if limit_stage.get("status") in {"timeout", "failed"}:
        return _check("asymptote_limits", "warn", "fallback", "Limit stage chưa hoàn tất.")
    vertical = asymptotes.get("vertical") or []
    invalid = [item for item in vertical if (item.get("left_limit") or {}).get("status") == "unknown" or (item.get("right_limit") or {}).get("status") == "unknown"]
    return _check("asymptote_limits", "warn" if invalid else "pass", "symbolic", "Có giới hạn tiệm cận chưa xác định." if invalid else None)


def _verify_intercepts(data: Mapping[str, Any]) -> Check:
    roots = data.get("x_intercepts_v2")
    expression = data.get("_evaluated_expr") or data.get("_parsed_expr")
    if not roots or expression is None:
        return _check("intercept_substitution", "unknown", "unknown", "Không có root evidence.")
    variable = _variable(expression)
    numeric = False
    try:
        for root in roots.get("roots") or []:
            if root.get("verification") == "symbolic_exact" and root.get("x_exact"):
                if sp.simplify(expression.subs(variable, sp.sympify(root["x_exact"]))) != 0:
                    return _check("intercept_substitution", "fail", "symbolic", "Có nghiệm exact không triệt tiêu biểu thức.")
            else:
                numeric = True
                residual = float(root.get("residual", float("inf")))
                error_bound = root.get("error_bound")
                if not sp.Float(residual).is_finite or error_bound is None or residual > max(float(error_bound), 1e-8):
                    return _check("intercept_substitution", "fail", "numeric", "Có nghiệm numeric vượt residual bound.")
    except Exception:
        return _check("intercept_substitution", "unknown", "unknown", "Không backcheck được nghiệm.")
    if roots.get("status") != "complete" or roots.get("truncated"):
        return _check("intercept_substitution", "warn", "numeric" if numeric else "symbolic", "Tập nghiệm có thể chưa đầy đủ.")
    return _check("intercept_substitution", "pass", "numeric" if numeric else "symbolic")


def _verify_tangent(data: Mapping[str, Any]) -> Check:
    tangent = data.get("line_analysis") or {}
    verification = str(tangent.get("verification") or "")
    if tangent.get("status") == "nondifferentiable":
        return _check("tangent", "pass", "symbolic")
    if verification.startswith(("difference_quotient_", "matching_infinite_", "one_sided_infinite_")):
        return _check("tangent", "pass", "symbolic")
    return _check("tangent", "warn", "fallback", "Tiếp tuyến thiếu difference-quotient evidence.")


def _verify_extrema_attainment(data: Mapping[str, Any]) -> Check:
    analysis = data.get("interval_analysis") or {}
    expression = data.get("_evaluated_expr") or data.get("_parsed_expr")
    domain_info = data.get("_domain_info")
    if expression is None or domain_info is None:
        return _check("extrema_attainment", "unknown", "unknown", "Không có expression/domain evidence.")
    variable = _variable(expression)
    try:
        for key in ("supremum", "infimum"):
            extreme = analysis.get(key) or {}
            if not extreme.get("attained"):
                continue
            expected = sp.sympify(extreme["value_exact"])
            points = extreme.get("points") or []
            if not points:
                return _check("extrema_attainment", "fail", "symbolic", "Extremum attained nhưng thiếu attainment point.")
            for point in points:
                x_value = sp.sympify(point["x_exact"])
                if not in_domain(domain_info, x_value) or sp.simplify(expression.subs(variable, x_value) - expected) != 0:
                    return _check("extrema_attainment", "fail", "symbolic", "Attainment point không khớp domain/value.")
    except Exception:
        return _check("extrema_attainment", "unknown", "unknown", "Không backcheck được attainment.")
    return _check("extrema_attainment", "pass", "symbolic")


def _verify_graph_domain(data: Mapping[str, Any]) -> Check:
    graph = data.get("graph_analysis_v2")
    domain_info = data.get("_domain_info")
    if not graph or domain_info is None:
        return _check("graph_domain_consistency", "unknown", "unknown", "Graph bị bỏ qua hoặc thiếu domain evidence.")
    try:
        for segment in graph.get("segments") or []:
            for point in segment.get("points") or []:
                if not in_domain(domain_info, sp.Rational(str(point["x"]))):
                    return _check("graph_domain_consistency", "fail", "numeric", "Graph chứa điểm ngoài tập xác định.")
    except Exception:
        return _check("graph_domain_consistency", "unknown", "unknown", "Không kiểm tra được graph/domain.")
    status = graph.get("status")
    return _check("graph_domain_consistency", "pass" if status == "complete" else "warn", "numeric", None if status == "complete" else "Graph sampling partial hoặc truncated.")


def _has_truncation(data: Mapping[str, Any]) -> bool:
    roots = data.get("x_intercepts_v2") or {}
    graph = data.get("graph_analysis_v2") or {}
    line_roots = (data.get("line_analysis") or {}).get("roots_v2") or {}
    return bool(roots.get("truncated") or line_roots.get("truncated") or graph.get("status") == "partial")


def _has_incomplete_stage(data: Mapping[str, Any]) -> bool:
    return any(
        isinstance(payload, Mapping) and payload.get("status") in {"timeout", "failed"}
        for payload in (data.get("stage_statuses") or {}).values()
    )


def _variable(expression: Any):
    symbols = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
    return next((symbol for symbol in symbols if symbol.name == "x"), sp.Symbol("x", real=True))


def _check(name: str, status: str, method: str, detail: str | None = None) -> Check:
    result: Check = {"name": name, "status": status, "method": method}
    if detail:
        result["detail"] = detail
    return result