"""
Lựa chọn 1: Khảo sát hàm số tự động (Function Analyzer).

Nhận biểu thức hàm số → dùng SymPy tính:
- Đạo hàm f'(x), f''(x)
- TXĐ, tập giá trị, tính chẵn lẻ
- Điểm cực trị, điểm uốn
- Khoảng đồng biến / nghịch biến, lồi / lõm
- Tiệm cận ngang / đứng / xiên
- Bảng biến thiên dạng text
- Điểm cắt trục Ox, Oy
"""
from __future__ import annotations

import re
import signal
import threading
from contextlib import contextmanager
from math import isfinite
from typing import Any, Mapping

import sympy as sp
from sympy import (
    S, Symbol, oo, simplify, diff, solve, limit,
    Rational, zoo, nan, latex,
    fraction, cancel,
    sin, cos, tan, cot, asin, acos, atan, log, exp, sqrt, pi, E, Abs,
    solveset, Interval, Poly, discriminant, Eq, FiniteSet, solve_univariate_inequality, default_sort_key,
)
from sympy.calculus.util import continuous_domain, function_range
from sympy.calculus.singularities import singularities

from app.services.function_analysis_capabilities import exact_approx_value, expression_capabilities
from app.services.function_analysis_steps import build_analysis_steps
from app.services.function_domain import DomainPartition, FunctionDomain, filter_domain_values, in_domain, intersect_domain, removable_holes
from app.services.function_roots import RootAnalysis, analyze_real_roots
from app.services.safe_math_parser import SafeMathComplexityError, SafeMathParseError, SafeMathParseResult, parse_safe_math_expression


x = Symbol("x", real=True)
m = Symbol("m", real=True)

_PARAMETER_RANGES = {"m": {"min": -10.0, "max": 10.0, "step": 0.1}}
_CLEAN_RE = re.compile(r"\s+")

ANALYZER_STAGE_TIMEOUT = "ANALYZER_STAGE_TIMEOUT"
_STAGE_TIMEOUT_SECONDS = {
    "parse": 1.0,
    "domain": 2.0,
    "range": 2.0,
    "simplify": 1.0,
    "derivative": 2.0,
    "root_solving": 3.0,
    "limits": 2.0,
    "interval_tool": 3.0,
    "line_tool": 3.0,
    "parameter_conditions": 3.0,
    "transform": 2.0,
}


class AnalyzerStageTimeout(TimeoutError):
    code = ANALYZER_STAGE_TIMEOUT

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Stage analyzer quá thời gian: {stage}.")


@contextmanager
def analyzer_stage_timeout(stage: str, seconds: float | None = None):
    timeout = seconds if seconds is not None else _STAGE_TIMEOUT_SECONDS.get(stage, 2.0)
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _raise_timeout(signum, frame):
        raise AnalyzerStageTimeout(stage)

    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def _record_stage_timeout(result: dict[str, Any], warnings: list[str], error: AnalyzerStageTimeout, *, core: bool = False) -> None:
    result.setdefault("stage_statuses", {})[error.stage] = {"status": "timeout", "error_code": error.code}
    warnings.append(str(error))
    if core:
        result["_skip_graph"] = True


def _record_stage_ok(result: dict[str, Any], stage: str) -> None:
    result.setdefault("stage_statuses", {})[stage] = {"status": "ok"}


def _parse_expr(expression: str) -> SafeMathParseResult:
    cleaned = _preprocess_expression(expression)
    try:
        parsed = parse_safe_math_expression(cleaned)
    except (SafeMathParseError, SafeMathComplexityError) as e:
        raise ValueError(f"Không thể phân tích biểu thức: {expression!r}. Lỗi: {e}") from e

    unsupported = parsed.expr.free_symbols - {x, m}
    if unsupported:
        names = ", ".join(sorted(str(symbol) for symbol in unsupported))
        raise ValueError(f"Chỉ hỗ trợ biến x và tham số m trong phiên bản này. Ký hiệu chưa hỗ trợ: {names}.")
    return parsed


def _preprocess_expression(expression: str) -> str:
    cleaned = expression.strip()
    cleaned = _strip_math_delimiters(cleaned)
    cleaned = _strip_text_commands(cleaned)
    cleaned = cleaned.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    cleaned = _replace_latex_command_groups(cleaned, "\\frac", lambda groups: f"(({_preprocess_expression(groups[0])})/({_preprocess_expression(groups[1])}))", 2)
    cleaned = _replace_latex_command_groups(cleaned, "\\sqrt", _format_sqrt_groups, 1, optional_group=True)
    cleaned = _replace_latex_over(cleaned)
    cleaned = _replace_latex_power_groups(cleaned)
    cleaned = _replace_absolute_bars(cleaned)
    cleaned = cleaned.replace("\\left", "").replace("\\right", "")
    cleaned = cleaned.replace("\\cdot", "*").replace("\\times", "*").replace("·", "*").replace("×", "*")
    cleaned = cleaned.replace("−", "-").replace("–", "-").replace("÷", "/")
    cleaned = cleaned.replace("{", "(").replace("}", ")")
    cleaned = cleaned.replace("^", "**")
    replacements = {
        "\\arcsin": "asin",
        "\\arccos": "acos",
        "\\arctan": "atan",
        "\\sin": "sin",
        "\\cos": "cos",
        "\\tan": "tan",
        "\\tg": "tan",
        "\\cot": "cot",
        "\\ctg": "cot",
        "\\ln": "log",
        "\\log": "log",
        "\\lg": "log",
        "\\exp": "exp",
        "\\pi": "pi",
        "\\infty": "oo",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("π", "pi").replace("∞", "oo")
    cleaned = cleaned.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
    cleaned = re.sub(r"([xm\)])([0-9]+)", r"\1**\2", cleaned)
    cleaned = re.sub(r"\be\b", "E", cleaned)
    cleaned = re.sub(r"\bln\s*\(", "log(", cleaned)
    cleaned = re.sub(r"\btg\s*\(", "tan(", cleaned)
    cleaned = re.sub(r"\bctg\s*\(", "cot(", cleaned)
    cleaned = re.sub(r"\blog_\s*\(([^()]+)\)\s*\(([^()]+)\)", r"log(\2, \1)", cleaned)
    cleaned = re.sub(r"\blog_([0-9]+(?:\.[0-9]+)?)\s*\(([^()]+)\)", r"log(\2, \1)", cleaned)
    cleaned = _wrap_bare_function_arguments(cleaned)
    return cleaned


def _strip_math_delimiters(expression: str) -> str:
    text = expression.strip()
    for left, right in (("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)"), ("$", "$")):
        if text.startswith(left) and text.endswith(right):
            return text[len(left):len(text) - len(right)].strip()
    return text


def _strip_text_commands(expression: str) -> str:
    text = expression
    for command in ("\\operatorname", "\\mathrm", "\\text"):
        while command in text:
            start = text.find(command)
            group, end = _read_latex_group(text, start + len(command), command)
            text = f"{text[:start]}{group}{text[end:]}"
    return text


def _replace_latex_command_groups(expression: str, command: str, replacement, group_count: int, *, optional_group: bool = False) -> str:
    text = expression
    while command in text:
        start = text.find(command)
        cursor = start + len(command)
        groups: list[str] = []
        if optional_group:
            optional, optional_end = _try_read_latex_bracket_group(text, cursor)
            if optional is not None:
                groups.append(optional)
                cursor = optional_end
        for _ in range(group_count):
            group, cursor = _read_latex_group(text, cursor, command)
            groups.append(group)
        text = f"{text[:start]}{replacement(groups)}{text[cursor:]}"
    return text


def _format_sqrt_groups(groups: list[str]) -> str:
    if len(groups) == 1:
        return f"sqrt({_preprocess_expression(groups[0])})"
    return f"(({_preprocess_expression(groups[1])})**(1/({_preprocess_expression(groups[0])})))"


def _replace_latex_over(expression: str) -> str:
    text = expression
    while "\\over" in text:
        index = text.find("\\over")
        left_start = _find_fraction_side_start(text, index)
        right_end = _find_fraction_side_end(text, index + len("\\over"))
        numerator = text[left_start:index].strip()
        denominator = text[index + len("\\over"):right_end].strip()
        text = f"{text[:left_start]}(({_preprocess_expression(numerator)})/({_preprocess_expression(denominator)})){text[right_end:]}"
    return text


def _find_fraction_side_start(text: str, index: int) -> int:
    cursor = index - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    if cursor >= 0 and text[cursor] == "}":
        depth = 0
        for pos in range(cursor, -1, -1):
            if text[pos] == "}":
                depth += 1
            elif text[pos] == "{":
                depth -= 1
                if depth == 0:
                    return pos
    while cursor >= 0 and text[cursor] not in "+-*/(=":
        cursor -= 1
    return cursor + 1


def _find_fraction_side_end(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor < len(text) and text[cursor] == "{":
        _, end = _read_latex_group(text, cursor, "\\over")
        return end
    while cursor < len(text) and text[cursor] not in "+-*/)=":
        cursor += 1
    return cursor


def _replace_absolute_bars(expression: str) -> str:
    text = expression.replace("\\lvert", "|").replace("\\rvert", "|").replace("\\left|", "|").replace("\\right|", "|")
    result: list[str] = []
    open_abs = False
    for char in text:
        if char == "|":
            result.append("Abs(" if not open_abs else ")")
            open_abs = not open_abs
        else:
            result.append(char)
    return "".join(result)


def _wrap_bare_function_arguments(expression: str) -> str:
    functions = "sin|cos|tan|cot|asin|acos|atan|log|exp|sqrt|Abs"
    return re.sub(rf"\b({functions})\s+([A-Za-z0-9_.]+)", r"\1(\2)", expression)


def _replace_latex_power_groups(expression: str) -> str:
    text = expression
    index = 0
    while index < len(text):
        if text[index] == "^":
            cursor = index + 1
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor < len(text) and text[cursor] == "{":
                group, end = _read_latex_group(text, cursor, "lũy thừa")
                text = f"{text[:index]}**({_preprocess_expression(group)}){text[end:]}"
                index += 3
                continue
        index += 1
    return text


def _try_read_latex_bracket_group(text: str, start: int) -> tuple[str | None, int]:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "[":
        return None, start
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    raise ValueError("Thiếu dấu ] trong biểu thức LaTeX.")


def _read_latex_group(text: str, start: int, command: str) -> tuple[str, int]:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        raise ValueError(f"Cú pháp {command} cần nhóm trong dấu {{}}.")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    raise ValueError("Thiếu dấu } trong biểu thức LaTeX.")


def _fmt_sym(expr) -> str:
    try:
        return str(simplify(expr))
    except Exception:
        return str(expr)


def _fmt_num(val) -> str:
    try:
        f = float(val)
        s = f"{f:.4f}".rstrip("0").rstrip(".")
        return s or "0"
    except Exception:
        return str(val)


def _expr_payload(value) -> dict[str, Any]:
    exact = _fmt_sym(value)
    payload: dict[str, Any] = {"exact": exact, "latex": latex(value), "approx": None, "precision": None}
    try:
        numeric = float(sp.N(value))
        if isfinite(numeric):
            payload["approx"] = _fmt_num(numeric)
            payload["precision"] = "4dp"
    except Exception:
        pass
    return payload


def _limit_payload_v2(value) -> dict[str, Any]:
    if value == oo:
        return {"value": "+∞", "value_exact": "oo", "value_latex": r"\infty", "status": "infinite"}
    if value == -oo:
        return {"value": "-∞", "value_exact": "-oo", "value_latex": r"-\infty", "status": "infinite"}
    if value in (zoo, nan, S.NaN) or str(value).startswith("AccumBounds") or isinstance(value, sp.Limit):
        return {"value": None, "value_exact": None, "value_latex": None, "status": "dne"}
    try:
        simplified = simplify(value)
    except Exception:
        simplified = value
    payload = _expr_payload(simplified)
    return {"value": payload["approx"] or payload["exact"], "value_exact": payload["exact"], "value_latex": payload["latex"], "status": "finite"}


def _is_limit_finite(value) -> bool:
    return value not in (oo, -oo, zoo, nan, S.NaN) and not str(value).startswith("AccumBounds") and not isinstance(value, sp.Limit)


def _parameter_value(parameters: Mapping[str, Any] | None, name: str):
    if parameters is None or name not in parameters:
        raise ValueError(f"Cần nhập giá trị exact cho tham số {name}.")
    raw = parameters[name]
    try:
        parsed = parse_safe_math_expression(str(raw)).expr
    except (SafeMathParseError, SafeMathComplexityError) as error:
        raise ValueError(f"Tham số {name} không hợp lệ: {error}") from error
    if parsed.free_symbols or parsed.is_real is False or parsed.is_finite is not True:
        raise ValueError(f"Tham số {name} phải là biểu thức số thực hữu hạn, không chứa biến.")
    return simplify(parsed)


def _periodicity_payload(f_expr, domain_info: FunctionDomain | None) -> dict[str, Any] | None:
    if not any(f_expr.has(func) for func in (sin, cos, tan, cot)):
        return None
    try:
        period = sp.periodicity(f_expr, x)
    except Exception:
        period = None
    if period is None:
        return None
    payload = {
        "status": "periodic",
        "period": _fmt_sym(period),
        "period_latex": latex(period),
        "parameter": "k",
        "parameter_domain": "Z",
        "base_interval": {"left": "0", "left_exact": "0", "right": _fmt_sym(period), "right_exact": _fmt_sym(period)},
        "families": [],
        "warnings": [],
    }
    if f_expr.has(tan):
        payload["families"].append({"kind": "vertical_asymptote", "x_exact": "pi/2 + k*pi", "x_latex": r"\frac{\pi}{2}+k\pi", "parameter": "k", "domain": "Z"})
    if f_expr.has(cot):
        payload["families"].append({"kind": "vertical_asymptote", "x_exact": "k*pi", "x_latex": r"k\pi", "parameter": "k", "domain": "Z"})
    partition = domain_info.partition if domain_info is not None else None
    if partition is not None and partition.excluded_families and not payload["families"]:
        for family in partition.excluded_families:
            payload["families"].append({"kind": "excluded_domain", "x_exact": str(family.expression), "x_latex": latex(family.expression), "parameter": family.variable, "domain": family.domain})
    return payload


def _monotonicity_payload(chart: dict[str, Any], periodicity: dict[str, Any] | None = None) -> dict[str, Any]:
    segments = []
    for item in chart.get("segments", []):
        direction = "increasing" if item["sign"] == "+" else "decreasing" if item["sign"] == "-" else "constant"
        segments.append({**item, "direction": direction, "derivative_sign": item["sign"]})
    payload = {"status": chart["status"], "method": chart["method"], "segments": segments, "warnings": chart.get("warnings", [])}
    if periodicity is not None:
        payload["periodic"] = True
        payload["period"] = periodicity["period"]
        payload["base_interval"] = periodicity["base_interval"]
        payload["parameter"] = periodicity["parameter"]
    return payload


def _periodic_monotonicity_payload(f_expr, periodicity: dict[str, Any] | None) -> dict[str, Any] | None:
    if periodicity is None:
        return None
    try:
        simplified = simplify(f_expr)
    except Exception:
        simplified = f_expr
    period = periodicity["period"]
    segments: list[dict[str, Any]] = []

    def add(left: str, right: str, direction: str, sign: str) -> None:
        segments.append({
            "left": left,
            "right": right,
            "left_exact": left,
            "right_exact": right,
            "direction": direction,
            "derivative_sign": sign,
            "verification": "periodic_exact",
            "parameter": "k",
            "parameter_domain": "Z",
        })

    if simplify(simplified - sin(x)) == 0:
        add("-pi/2 + 2*k*pi", "pi/2 + 2*k*pi", "increasing", "+")
        add("pi/2 + 2*k*pi", "3*pi/2 + 2*k*pi", "decreasing", "-")
    elif simplify(simplified - cos(x)) == 0:
        add("2*k*pi", "pi + 2*k*pi", "decreasing", "-")
        add("pi + 2*k*pi", "2*pi + 2*k*pi", "increasing", "+")
    elif simplify(simplified - tan(x)) == 0:
        add("-pi/2 + k*pi", "pi/2 + k*pi", "increasing", "+")
    elif simplify(simplified - cot(x)) == 0:
        add("k*pi", "pi + k*pi", "decreasing", "-")
    else:
        return None
    return {"status": "complete", "method": "periodic_exact", "periodic": True, "period": period, "parameter": "k", "parameter_domain": "Z", "base_interval": periodicity["base_interval"], "segments": segments, "warnings": []}


def _concavity_payload(chart: dict[str, Any]) -> dict[str, Any]:
    segments = []
    for item in chart.get("segments", []):
        kind = "convex" if item["sign"] == "+" else "concave" if item["sign"] == "-" else "flat"
        segments.append({**item, "kind": kind, "second_derivative_sign": item["sign"]})
    return {"status": chart["status"], "method": chart["method"], "segments": segments, "warnings": chart.get("warnings", [])}


def _inflection_points_from_chart(f_expr, fpp_expr, domain_info: FunctionDomain | None, chart: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    points: list[dict[str, str]] = []
    points_v2: list[dict[str, Any]] = []
    try:
        roots, _exact = _solve_domain_roots(fpp_expr, domain_info)
    except Exception:
        roots = []
    try:
        singular_set = singularities(fpp_expr, x)
        if isinstance(singular_set, FiniteSet):
            roots.extend(list(singular_set))
    except Exception:
        pass

    seen: set[str] = set()
    for point in sorted(set(roots), key=default_sort_key):
        key = _fmt_sym(point)
        if key in seen or not in_domain(domain_info, point):
            continue
        seen.add(key)
        left_sign = _chart_side_sign(chart, point, "left")
        right_sign = _chart_side_sign(chart, point, "right")
        if left_sign is None or right_sign is None or left_sign == right_sign:
            continue
        try:
            if not _is_continuous_at(f_expr, point):
                continue
            y_val = simplify(f_expr.subs(x, point))
        except Exception:
            continue
        legacy = {"x": _fmt_num(point), "x_exact": key, "y": _fmt_num(y_val)}
        points.append(legacy)
        points_v2.append({**legacy, "y_exact": _fmt_sym(y_val), "kind": "inflection", "evidence": "second_derivative_sign_change", "left_sign": left_sign, "right_sign": right_sign, "verification": chart["method"]})
    return points, points_v2


def _is_continuous_at(f_expr, point) -> bool:
    try:
        left = limit(f_expr, x, point, dir="-")
        right = limit(f_expr, x, point, dir="+")
        value = simplify(f_expr.subs(x, point))
        return simplify(left - value) == 0 and simplify(right - value) == 0
    except Exception:
        return False


def _chart_side_sign(chart: dict[str, Any], point, side: str) -> str | None:
    try:
        p = sp.sympify(point)
    except Exception:
        return None
    for segment in chart.get("segments", []):
        try:
            left = sp.sympify(segment["left_exact"])
            right = sp.sympify(segment["right_exact"])
            if side == "left" and left < p <= right:
                return segment["sign"]
            if side == "right" and left <= p < right:
                return segment["sign"]
        except Exception:
            continue
    return None


def _critical_points_v2(points: list[dict[str, Any]], fprime_chart: dict[str, Any] | None, fpp_chart: dict[str, Any] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for point in points:
        raw = point.get("x_exact") or point.get("x")
        try:
            exact_point = sp.sympify(raw)
        except Exception:
            exact_point = raw
        left_sign = _chart_side_sign(fprime_chart or {}, exact_point, "left")
        right_sign = _chart_side_sign(fprime_chart or {}, exact_point, "right")
        kind = "unknown"
        evidence = "unknown"
        if left_sign == "-" and right_sign == "+":
            kind = "local_min"
            evidence = "first_derivative_sign_change"
        elif left_sign == "+" and right_sign == "-":
            kind = "local_max"
            evidence = "first_derivative_sign_change"
        elif left_sign in {"+", "-"} and left_sign == right_sign:
            fpp_left = _chart_side_sign(fpp_chart or {}, exact_point, "left")
            fpp_right = _chart_side_sign(fpp_chart or {}, exact_point, "right")
            if fpp_left is not None and fpp_right is not None and fpp_left != fpp_right:
                kind = "stationary_inflection"
                evidence = "second_derivative_sign_change"
            else:
                kind = "stationary_point"
                evidence = "no_first_derivative_sign_change"
        result.append({
            "x": point.get("x"),
            "x_exact": point.get("x_exact"),
            "x_latex": latex(exact_point) if not isinstance(exact_point, str) else point.get("x_exact"),
            "y": point.get("y"),
            "y_exact": point.get("y_exact") or point.get("y"),
            "kind": kind,
            "legacy_kind": point.get("kind"),
            "left_derivative_sign": left_sign,
            "right_derivative_sign": right_sign,
            "evidence": evidence,
            "verification": (fprime_chart or {}).get("method", "unknown"),
        })
    return result


def _asymptotes_v2(f_expr, domain_info: FunctionDomain | None, periodicity: dict[str, Any] | None) -> dict[str, Any]:
    try:
        analysis_expr = cancel(f_expr)
    except Exception:
        analysis_expr = f_expr
    vertical_points: list[Any] = []
    sources: dict[str, set[str]] = {}

    def add_point(point, source: str) -> None:
        try:
            simplified = simplify(point)
            if simplified in (oo, -oo) or simplified.is_real is False:
                return
            key = _fmt_sym(simplified)
        except Exception:
            return
        if any(hole.get("x_exact") == key for hole in []):
            return
        vertical_points.append(simplified)
        sources.setdefault(key, set()).add(source)

    try:
        _, denom_expr = fraction(cancel(f_expr))
        for root in solve(denom_expr, x):
            add_point(root, "denominator")
    except Exception:
        pass
    try:
        singular_set = singularities(f_expr, x)
        if isinstance(singular_set, FiniteSet):
            for point in singular_set:
                add_point(point, "singularity")
    except Exception:
        pass
    for component in list(domain_info.components) if domain_info is not None else []:
        if getattr(component.start, "is_finite", False):
            add_point(component.start, "domain_boundary")
        if getattr(component.end, "is_finite", False):
            add_point(component.end, "domain_boundary")

    vertical = []
    seen: set[str] = set()
    for point in sorted(set(vertical_points), key=default_sort_key):
        key = _fmt_sym(point)
        if key in seen:
            continue
        seen.add(key)
        try:
            left = limit(analysis_expr, x, point, dir="-")
        except Exception:
            left = None
        try:
            right = limit(analysis_expr, x, point, dir="+")
        except Exception:
            right = None
        left_payload = _limit_payload_v2(left) if left is not None else {"value": None, "value_exact": None, "value_latex": None, "status": "unknown"}
        right_payload = _limit_payload_v2(right) if right is not None else {"value": None, "value_exact": None, "value_latex": None, "status": "unknown"}
        if left_payload["status"] != "infinite" and right_payload["status"] != "infinite":
            continue
        expr_data = _expr_payload(point)
        vertical.append({
            "kind": "vertical",
            "x": expr_data["approx"] or expr_data["exact"],
            "x_exact": expr_data["exact"],
            "x_latex": expr_data["latex"],
            "x_value": exact_approx_value(point, method="symbolic_limit"),
            "approx": expr_data["approx"],
            "precision": expr_data["precision"],
            "left_limit": left_payload,
            "right_limit": right_payload,
            "source": sorted(sources.get(key, {"unknown"})),
        })

    horizontal = []
    for direction, target in (("+∞", oo), ("-∞", -oo)):
        try:
            value = limit(analysis_expr, x, target)
        except Exception:
            continue
        if not _is_limit_finite(value):
            continue
        data = _expr_payload(simplify(value))
        horizontal.append({"kind": "horizontal", "direction": direction, "value": data["approx"] or data["exact"], "value_exact": data["exact"], "value_latex": data["latex"], "value_v2": exact_approx_value(value, method="symbolic_limit"), "approx": data["approx"], "precision": data["precision"]})

    oblique = []
    for direction, target in (("+∞", oo), ("-∞", -oo)):
        try:
            slope = simplify(limit(analysis_expr / x, x, target))
            if not _is_limit_finite(slope) or slope == 0:
                continue
            intercept = simplify(limit(analysis_expr - slope * x, x, target))
            if not _is_limit_finite(intercept):
                continue
            validation = limit(analysis_expr - (slope * x + intercept), x, target)
            if validation != 0:
                continue
        except Exception:
            continue
        slope_data = _expr_payload(slope)
        intercept_data = _expr_payload(intercept)
        equation = slope * x + intercept
        oblique.append({
            "kind": "oblique",
            "direction": direction,
            "slope": slope_data["approx"] or slope_data["exact"],
            "slope_exact": slope_data["exact"],
            "slope_latex": slope_data["latex"],
            "slope_value": exact_approx_value(slope, method="symbolic_limit"),
            "intercept": intercept_data["approx"] or intercept_data["exact"],
            "intercept_exact": intercept_data["exact"],
            "intercept_latex": intercept_data["latex"],
            "intercept_value": exact_approx_value(intercept, method="symbolic_limit"),
            "equation": f"y = {_fmt_sym(equation)}",
            "equation_latex": f"y={latex(equation)}",
            "validation_limit": "0",
            "precision": slope_data["precision"] or intercept_data["precision"],
        })

    families = []
    if periodicity is not None:
        families = [family for family in periodicity.get("families", []) if family.get("kind") == "vertical_asymptote"]
    return {"vertical": vertical, "horizontal": horizontal, "oblique": oblique, "periodic_vertical_families": families}


def analyze_function(
    expression: str,
    parameters: Mapping[str, Any] | None = None,
    *,
    parameter_mode: str | None = None,
    interval: Mapping[str, float] | None = None,
    line: Mapping[str, float] | None = None,
    parameter_conditions: Mapping[str, Any] | None = None,
    transform: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    method_details: dict[str, str] = {}

    try:
        with analyzer_stage_timeout("parse"):
            parse_result = _parse_expr(expression)
        parsed = parse_result.expr
    except ValueError as e:
        code = getattr(e.__cause__, "code", "ANALYZER_PARSE_FAILED")
        return {"error": str(e), "error_code": code, "warnings": [str(e)]}
    except AnalyzerStageTimeout as e:
        return {"error": str(e), "error_code": e.code, "warnings": [str(e)], "stage_statuses": {e.stage: {"status": "timeout", "error_code": e.code}}}

    detected_parameters = ["m"] if m in parsed.free_symbols else []
    parameter_payload: dict[str, Any] = {
        "detected": detected_parameters,
        "active": {},
        "active_exact": {},
        "ranges": {name: dict(config) for name, config in _PARAMETER_RANGES.items() if name in detected_parameters},
    }
    if detected_parameters and parameter_mode is None:
        pending_result = {
            "expression": expression,
            "expression_latex": latex(parsed),
            "evaluated_expression": None,
            "evaluated_expression_latex": None,
            "analysis_mode": "requires_parameter_confirmation",
            "parameter_mode": None,
            "parameters": parameter_payload,
            "requires_parameter_confirmation": True,
            "requires_substitution_for_graph": True,
            "complexity_score": parse_result.complexity_score,
            "stage_statuses": {"parse": {"status": "ok"}, "graph": {"status": "skipped"}},
            "warnings": ["Chọn chế độ symbolic hoặc thay giá trị m trước khi phân tích."],
            "_parsed_expr": parsed,
            "_skip_graph": True,
        }
        capabilities = expression_capabilities(parsed, pending_result)
        pending_result["capabilities"] = capabilities
        pending_result["capabilities_v2"] = capabilities
        pending_result["analysis_steps"] = build_analysis_steps(pending_result)
        return pending_result
    if detected_parameters and parameter_mode == "symbolic":
        from app.services.function_parameter_analysis import analyze_parameter_cases

        parameter_analysis = analyze_parameter_cases(parsed, x, m)
        parameter_payload["provenance"] = {"mode": "symbolic", "source": "request", "exact": True}
        symbolic_result = {
            "expression": expression,
            "expression_latex": latex(parsed),
            "evaluated_expression": None,
            "evaluated_expression_latex": None,
            "analysis_mode": "safe_symbolic",
            "parameter_mode": "symbolic",
            "parameters": parameter_payload,
            "requires_parameter_confirmation": False,
            "requires_substitution_for_graph": True,
            "parameter_analysis_v2": parameter_analysis,
            "parameter_conditions": parameter_analysis.get("legacy_conditions", []),
            "complexity_score": parse_result.complexity_score,
            "stage_statuses": {"parse": {"status": "ok"}, "parameter_analysis": {"status": parameter_analysis["status"]}, "graph": {"status": "skipped"}},
            "warnings": parameter_analysis.get("warnings", []),
            "_parsed_expr": parsed,
            "_skip_graph": True,
        }
        capabilities = expression_capabilities(parsed, symbolic_result)
        symbolic_result["capabilities"] = capabilities
        symbolic_result["capabilities_v2"] = capabilities
        symbolic_result["analysis_steps"] = build_analysis_steps(symbolic_result)
        return symbolic_result

    f = parsed
    if detected_parameters:
        if parameter_mode != "substitute":
            return {"error": "Chế độ tham số không hợp lệ.", "warnings": ["Chế độ tham số không hợp lệ."]}
        try:
            m_value = _parameter_value(parameters, "m")
        except ValueError as e:
            return {"error": str(e), "warnings": [str(e)]}
        parameter_payload["active"]["m"] = float(sp.N(m_value))
        parameter_payload["active_exact"]["m"] = _fmt_sym(m_value)
        parameter_payload["provenance"] = {"mode": "substitute", "source": "request", "exact": True}
        f = f.subs(m, m_value)
        warnings.append(f"Kết quả khảo sát tại m = {_fmt_sym(m_value)}.")

    result: dict[str, Any] = {
        "expression": expression,
        "expression_latex": latex(parsed),
        "evaluated_expression": _fmt_sym(f),
        "evaluated_expression_latex": latex(f),
        "analysis_mode": "numeric_substituted" if detected_parameters else "symbolic",
        "parameter_mode": parameter_mode if detected_parameters else None,
        "parameters": parameter_payload,
        "requires_parameter_confirmation": False,
        "requires_substitution_for_graph": False,
        "complexity_score": parse_result.complexity_score,
        "stage_statuses": {"parse": {"status": "ok"}},
        "_parsed_expr": parsed,
        "_evaluated_expr": f,
    }

    domain_info = FunctionDomain.from_set(None)
    try:
        with analyzer_stage_timeout("domain"):
            dom = continuous_domain(f, x, S.Reals)
        domain_info = FunctionDomain.from_set(dom)
        result["domain"] = str(dom)
        result["domain_latex"] = latex(dom)
        result["_domain_set"] = dom
        result["_domain_info"] = domain_info
        result["domain_components"] = [str(component) for component in domain_info.components]
        _record_stage_ok(result, "domain")
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
        result["domain"] = None
        result["domain_latex"] = None
    except Exception as e:
        warnings.append(f"Không tính được tập xác định: {e}")
        result["domain"] = None
        result["domain_latex"] = None

    result["domain_partition_v2"] = domain_info.partition.model_payload() if domain_info.partition is not None else None
    result["periodicity"] = _periodicity_payload(f, domain_info)

    try:
        with analyzer_stage_timeout("range"):
            rng = function_range(simplify(f), x, S.Reals)
        result["range"] = str(rng)
        result["range_latex"] = latex(rng)
        _record_stage_ok(result, "range")
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
        result["range"] = None
        result["range_latex"] = None
    except Exception as e:
        warnings.append(f"Không tính được tập giá trị: {e}")
        result["range"] = None
        result["range_latex"] = None

    try:
        with analyzer_stage_timeout("simplify"):
            f_neg = simplify(f.subs(x, -x))
            if simplify(f_neg - f) == 0:
                result["parity"] = "even"
            elif simplify(f_neg + f) == 0:
                result["parity"] = "odd"
            else:
                result["parity"] = "neither"
        _record_stage_ok(result, "simplify")
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
        result["parity"] = "neither"
    except Exception:
        result["parity"] = "neither"

    try:
        with analyzer_stage_timeout("derivative"):
            fp = diff(f, x)
            fp_simplified = simplify(fp)
        result["derivative"] = _fmt_sym(fp_simplified)
        result["derivative_latex"] = latex(fp_simplified)
        _record_stage_ok(result, "derivative")
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e, core=True)
        fp_simplified = None
        result["derivative"] = None
        result["derivative_latex"] = None
    except Exception as e:
        warnings.append(f"Không tính được đạo hàm: {e}")
        fp_simplified = None
        result["derivative"] = None
        result["derivative_latex"] = None

    fpp_simplified = None
    if fp_simplified is not None:
        try:
            with analyzer_stage_timeout("derivative"):
                fpp_simplified = simplify(diff(fp_simplified, x))
            result["second_derivative"] = _fmt_sym(fpp_simplified)
            result["second_derivative_latex"] = latex(fpp_simplified)
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
        except Exception as e:
            warnings.append(f"Không tính được đạo hàm cấp 2: {e}")
    result.setdefault("second_derivative", None)
    result.setdefault("second_derivative_latex", None)

    try:
        simplified_for_holes = simplify(f)
        holes = removable_holes(f, simplified_for_holes, x, domain_info)
        result["removable_holes"] = [
            {
                "x": _fmt_num(hole["x"]),
                "x_exact": _fmt_sym(hole["x"]),
                "y": _fmt_num(hole["y"]),
                "y_exact": _fmt_sym(hole["y"]),
                "label": "điểm khuyết",
            }
            for hole in holes
        ]
        result["_graph_expr"] = str(f if result["removable_holes"] else simplified_for_holes)
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        result["removable_holes"] = []
        result["_graph_expr"] = str(f)

    critical_points: list[dict[str, Any]] = []
    if fp_simplified is not None:
        try:
            with analyzer_stage_timeout("root_solving"):
                stationary_candidates = _collect_stationary_candidates(f, fp_simplified, domain_info)
            for cp in stationary_candidates:
                try:
                    cp_float = float(cp.evalf())
                except Exception:
                    warnings.append(f"Bỏ qua điểm tới hạn không tính được: {cp}")
                    continue

                try:
                    kind, kind_label = _classify_stationary_point(
                        fp_simplified=fp_simplified,
                        cp=cp,
                        fpp_simplified=fpp_simplified,
                    )
                except Exception:
                    kind = "unknown"
                    kind_label = "Điểm đặc biệt"

                try:
                    y_expr = simplify(f.subs(x, cp))
                    y_val = float(y_expr.evalf())
                except Exception:
                    y_expr = None
                    y_val = None

                critical_points.append({
                    "x": _fmt_num(cp_float),
                    "x_exact": _fmt_sym(cp),
                    "x_value": exact_approx_value(cp, method="symbolic_exact"),
                    "y": _fmt_num(y_val) if y_val is not None else None,
                    "y_exact": _fmt_sym(y_expr) if y_expr is not None else None,
                    "y_value": exact_approx_value(y_expr, method="symbolic_exact") if y_expr is not None else None,
                    "kind": kind,
                    "kind_label": kind_label,
                })
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
        except Exception as e:
            warnings.append(f"Không giải được f'(x) = 0: {e}")

    result["critical_points"] = critical_points

    fpp_chart = None
    if fpp_simplified is not None:
        try:
            with analyzer_stage_timeout("root_solving"):
                fpp_chart = _sign_chart(fpp_simplified, domain_info, role="concavity")
                inflection_pts, inflection_pts_v2 = _inflection_points_from_chart(f, fpp_simplified, domain_info, fpp_chart)
            result["concavity_v2"] = _concavity_payload(fpp_chart)
            result["inflection_points"] = inflection_pts
            result["inflection_points_v2"] = inflection_pts_v2
            result["concave_up_intervals"] = _chart_intervals(fpp_chart, "+")
            result["concave_down_intervals"] = _chart_intervals(fpp_chart, "-")
            method_details["concavity"] = fpp_chart["method"]
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
            result["inflection_points"] = []
            result["inflection_points_v2"] = []
            result["concavity_v2"] = {"status": "unknown", "method": "unknown", "segments": [], "warnings": [str(e)]}
            result["concave_up_intervals"] = []
            result["concave_down_intervals"] = []
        except Exception as e:
            warnings.append(f"Không tính được điểm uốn: {e}")
            result["inflection_points"] = []
            result["inflection_points_v2"] = []
            result["concavity_v2"] = {"status": "unknown", "method": "unknown", "segments": [], "warnings": [str(e)]}
            result["concave_up_intervals"] = []
            result["concave_down_intervals"] = []
    else:
        result["inflection_points"] = []
        result["inflection_points_v2"] = []
        result["concavity_v2"] = {"status": "unknown", "method": "unknown", "segments": [], "warnings": ["Không có đạo hàm cấp 2."]}
        result["concave_up_intervals"] = []
        result["concave_down_intervals"] = []

    ha: list[dict] = []
    try:
        with analyzer_stage_timeout("limits"):
            lim_pos = limit(f, x, oo)
            lim_neg = limit(f, x, -oo)
        if lim_pos not in (oo, -oo, zoo, nan, S.NaN):
            ha.append({"direction": "+∞", "value": _fmt_num(lim_pos)})
        if lim_neg not in (oo, -oo, zoo, nan, S.NaN) and lim_neg != lim_pos:
            ha.append({"direction": "-∞", "value": _fmt_num(lim_neg)})
        _record_stage_ok(result, "limits")
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
    except Exception as e:
        warnings.append(f"Không tính được tiệm cận ngang: {e}")
    result["horizontal_asymptotes"] = ha

    va: list[dict] = []
    try:
        with analyzer_stage_timeout("limits"):
            _, denom_expr = fraction(cancel(f))
            denom_roots = solve(denom_expr, x)
        for z in denom_roots:
            try:
                z_f = float(z.evalf())
                with analyzer_stage_timeout("limits"):
                    lim_right = limit(f, x, z, "+")
                    lim_left = limit(f, x, z, "-")
                if lim_right in (oo, -oo, zoo) or lim_left in (oo, -oo, zoo):
                    va.append({
                        "x": _fmt_num(z_f),
                        "lim_right": _fmt_lim(lim_right),
                        "lim_left": _fmt_lim(lim_left),
                    })
            except Exception:
                pass
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
    except Exception as e:
        warnings.append(f"Không tính được tiệm cận đứng: {e}")
    result["vertical_asymptotes"] = va

    if fp_simplified is not None:
        mono_breakpoints = [sp.sympify(cp["x_exact"]) for cp in critical_points if cp.get("x_exact")]
        mono_breakpoints.extend(sp.sympify(item.get("x_exact") or item["x"]) for item in va if item.get("x_exact") or item.get("x"))
        monotonicity_chart = _sign_chart(fp_simplified, domain_info, role="monotonicity", known_breakpoints=mono_breakpoints)
        periodic_monotonicity = _periodic_monotonicity_payload(f, result.get("periodicity"))
        result["monotonicity_v2"] = periodic_monotonicity or _monotonicity_payload(monotonicity_chart, result.get("periodicity"))
        result["critical_points_v2"] = _critical_points_v2(critical_points, monotonicity_chart, fpp_chart)
        result["intervals_increasing"] = _chart_intervals(monotonicity_chart, "+")
        result["intervals_decreasing"] = _chart_intervals(monotonicity_chart, "-")
        method_details["monotonicity"] = result["monotonicity_v2"]["method"]
    else:
        result["monotonicity_v2"] = {"status": "unknown", "method": "unknown", "segments": [], "warnings": ["Không có đạo hàm."]}
        result["critical_points_v2"] = _critical_points_v2(critical_points, None, fpp_chart)
        result["intervals_increasing"] = []
        result["intervals_decreasing"] = []

    oblique = None
    try:
        with analyzer_stage_timeout("limits"):
            a_coef = limit(f / x, x, oo)
            if a_coef not in (oo, -oo, zoo, nan, S.NaN, S.Zero):
                b_coef = limit(f - a_coef * x, x, oo)
                if b_coef not in (oo, -oo, zoo, nan, S.NaN):
                    oblique = f"y = {_fmt_num(a_coef)}x + {_fmt_num(b_coef)}"
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
    except Exception:
        pass
    result["oblique_asymptote"] = oblique
    result["asymptotes_v2"] = _asymptotes_v2(f, domain_info, result.get("periodicity"))
    result["horizontal_asymptotes"] = [
        {"direction": item["direction"], "value": item["value"], "value_exact": item["value_exact"], "value_latex": item["value_latex"]}
        for item in result["asymptotes_v2"].get("horizontal", [])
    ]
    result["vertical_asymptotes"] = [
        {
            "x": item["x"],
            "lim_right": item["right_limit"].get("value") or "?",
            "lim_left": item["left_limit"].get("value") or "?",
        }
        for item in result["asymptotes_v2"].get("vertical", [])
    ]
    result["oblique_asymptote"] = result["asymptotes_v2"].get("oblique", [{}])[0].get("equation") if result["asymptotes_v2"].get("oblique") else None

    try:
        with analyzer_stage_timeout("root_solving"):
            intercept_analysis = analyze_real_roots(f, x, domain_info)
        result["x_intercepts_v2"] = intercept_analysis.payload()
        result["x_intercepts"] = [_fmt_num(sp.N(root.value)) for root in intercept_analysis.roots]
        warnings.extend(intercept_analysis.warnings)
    except AnalyzerStageTimeout as e:
        _record_stage_timeout(result, warnings, e)
        result["x_intercepts"] = []
        result["x_intercepts_v2"] = _unknown_root_payload(str(e))
    except Exception as e:
        result["x_intercepts"] = []
        result["x_intercepts_v2"] = _unknown_root_payload(f"Không giải được giao điểm Ox: {e}")

    y_intercept = None
    try:
        if in_domain(domain_info, S.Zero):
            y0 = float(f.subs(x, 0).evalf())
            y_intercept = _fmt_num(y0)
    except Exception:
        pass
    result["y_intercept"] = y_intercept

    if interval:
        try:
            with analyzer_stage_timeout("interval_tool"):
                result["interval_analysis"] = _analyze_interval(f, fp_simplified, interval, domain_info)
            _record_stage_ok(result, "interval_tool")
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không tính được GTLN/GTNN trên đoạn: {e}")

    if line:
        try:
            with analyzer_stage_timeout("line_tool"):
                result["line_analysis"] = _analyze_line_position(f, line, domain_info, method_details)
            _record_stage_ok(result, "line_tool")
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không xét được tương giao với đường thẳng: {e}")

    if parameter_conditions:
        try:
            with analyzer_stage_timeout("parameter_conditions"):
                result["parameter_conditions"] = _solve_parameter_conditions(parsed, parameter_conditions)
            _record_stage_ok(result, "parameter_conditions")
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
            result["parameter_conditions"] = []

    if transform:
        try:
            with analyzer_stage_timeout("transform"):
                result["transform_preview"] = _build_transform_preview(f, transform)
            _record_stage_ok(result, "transform")
        except AnalyzerStageTimeout as e:
            _record_stage_timeout(result, warnings, e)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không dựng được biến đổi đồ thị: {e}")

    result["variation_table"] = _build_variation_table(result, critical_points)
    result["variation_table_v2"] = _build_variation_table_v2(f, fp_simplified, domain_info, critical_points, result)
    capabilities = expression_capabilities(f, result)
    result["capabilities"] = capabilities
    result["capabilities_v2"] = capabilities
    result["method_used"] = method_details
    result["warnings"] = warnings
    result["analysis_steps"] = build_analysis_steps(result)

    return result


def analyze_function_tool_from_evidence(
    base_result: Mapping[str, Any],
    tool: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Chạy tool hẹp từ evidence JSON; không chạy lại full analyzer."""
    if tool == "parameter":
        parsed = _parse_expr(str(base_result.get("expression") or "")).expr
        return {"parameter_conditions": _solve_parameter_conditions(parsed, payload)}

    evaluated = base_result.get("evaluated_expression")
    if not isinstance(evaluated, str) or not evaluated:
        raise ValueError("Analysis session chưa có biểu thức đã xác nhận cho tool này.")
    f_expr = parse_safe_math_expression(evaluated).expr
    domain_info = _domain_from_serialized_evidence(base_result.get("domain_partition_v2"))

    if tool == "interval-extrema":
        derivative = base_result.get("derivative")
        if not isinstance(derivative, str) or not derivative:
            raise ValueError("Analysis session không có evidence đạo hàm.")
        fp_expr = parse_safe_math_expression(derivative).expr
        return {"interval_analysis": _analyze_interval(f_expr, fp_expr, payload, domain_info)}
    if tool in {"line", "tangent"}:
        line_payload = dict(payload)
        if tool == "tangent":
            line_payload["mode"] = "tangent_at"
        return {"line_analysis": _analyze_line_position(f_expr, line_payload, domain_info, {})}
    if tool == "transform":
        return {"transform_preview": _build_transform_preview(f_expr, payload)}
    raise ValueError("Công cụ analyzer không được hỗ trợ.")


def _domain_from_serialized_evidence(payload: Any) -> FunctionDomain:
    if not isinstance(payload, Mapping) or payload.get("status") != "complete":
        raise ValueError("Analysis session không có evidence miền đầy đủ.")
    intervals = []
    for component in payload.get("components") or []:
        if not isinstance(component, Mapping):
            raise ValueError("Evidence miền không hợp lệ.")
        start = simplify(parse_safe_math_expression(str(component["start"])).expr)
        end = simplify(parse_safe_math_expression(str(component["end"])).expr)
        intervals.append(Interval(
            start,
            end,
            left_open=bool(component.get("left_open", False)),
            right_open=bool(component.get("right_open", False)),
        ))
    if not intervals:
        raise ValueError("Analysis session không có thành phần miền.")
    return FunctionDomain.from_set(sp.Union(*intervals))


def _analyze_interval(f_expr, fp_expr, interval: Mapping[str, Any], domain_info: FunctionDomain | None = None) -> dict[str, Any]:
    a = _finite_float(interval.get("a", -10), "a")
    b = _finite_float(interval.get("b", 10), "b")
    open_a = bool(interval.get("open_a", False))
    open_b = bool(interval.get("open_b", False))
    if a >= b:
        raise ValueError("Đoạn khảo sát không hợp lệ: cần a < b.")

    exact_a = sp.Rational(str(a))
    exact_b = sp.Rational(str(b))
    requested = Interval(exact_a, exact_b, left_open=open_a, right_open=open_b)
    domain_set = domain_info.set if domain_info is not None and domain_info.set is not None else S.Reals
    active_set = requested.intersect(domain_set)
    components = _iter_intervals(active_set)
    if not components:
        raise ValueError("Khoảng khảo sát không giao với tập xác định của hàm số.")

    active_domain = FunctionDomain.from_set(active_set)
    boundary_evidence = _interval_boundary_evidence(f_expr, components)
    extrema_inside = _interval_critical_points(f_expr, fp_expr, active_domain, a, b)
    value_range, range_warnings = _range_on_components(f_expr, components)
    if value_range is None:
        raise ValueError("Không chứng minh được tập giá trị trên phần miền đang khảo sát.")

    supremum = _extreme_bound_payload(f_expr, active_set, value_range.sup, "supremum", boundary_evidence)
    infimum = _extreme_bound_payload(f_expr, active_set, value_range.inf, "infimum", boundary_evidence)
    status = "complete" if not range_warnings and supremum["status"] != "unknown" and infimum["status"] != "unknown" else "partial"

    return {
        "a": _fmt_num(a),
        "b": _fmt_num(b),
        "open_a": open_a,
        "open_b": open_b,
        "fa": _requested_boundary_value(f_expr, a, "+", open_a),
        "fb": _requested_boundary_value(f_expr, b, "-", open_b),
        "domain_intersection_exact": _fmt_sym(active_set),
        "domain_components": [_interval_component_payload(component) for component in components],
        "range_exact": _fmt_sym(value_range),
        "range_latex": latex(value_range),
        "status": status,
        "method": "symbolic_range",
        "warnings": range_warnings,
        "boundary_evidence": boundary_evidence,
        "extrema_inside": extrema_inside,
        "supremum": supremum,
        "infimum": infimum,
        "max_point": _legacy_extreme_point(supremum),
        "min_point": _legacy_extreme_point(infimum),
        "conclusion": "; ".join((_extreme_conclusion(supremum, True), _extreme_conclusion(infimum, False))) + ".",
    }


def _interval_boundary_evidence(f_expr, components: list[Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, component in enumerate(components):
        for point, side, is_open in (
            (component.start, "+", bool(component.left_open)),
            (component.end, "-", bool(component.right_open)),
        ):
            if point in (-oo, oo):
                value = limit(f_expr, x, point)
                attained = False
            elif is_open:
                value = limit(f_expr, x, point, dir=side)
                attained = False
            else:
                value = simplify(f_expr.subs(x, point))
                attained = True
            evidence.append({
                "component": index,
                "x": _fmt_boundary(point),
                "x_exact": _fmt_sym(point),
                "side": side,
                "kind": "endpoint" if attained else "one_sided_limit",
                "attained": attained,
                "value": _value_payload(value),
            })
    return evidence


def _interval_critical_points(f_expr, fp_expr, active_domain: FunctionDomain, a: float, b: float) -> list[dict[str, Any]]:
    if fp_expr is None:
        return []
    points: list[dict[str, Any]] = []
    for point in _collect_stationary_candidates(f_expr, fp_expr, active_domain):
        try:
            numeric = float(sp.N(point))
            value = simplify(f_expr.subs(x, point))
            if not a < numeric < b or not _is_finite_real(value):
                continue
        except (TypeError, ValueError, AttributeError):
            continue
        points.append({
            "x": _fmt_num(numeric),
            "x_exact": _fmt_sym(point),
            "x_latex": latex(point),
            "y": _fmt_num(value),
            "y_exact": _fmt_sym(value),
            "y_latex": latex(value),
            "kind": "critical",
            "label": "Điểm tới hạn trong miền khảo sát",
            "attained": True,
        })
    return points


def _range_on_components(f_expr, components: list[Any]) -> tuple[Any | None, list[str]]:
    ranges: list[Any] = []
    warnings: list[str] = []
    for component in components:
        try:
            component_range = function_range(f_expr, x, component)
        except Exception as error:
            warnings.append(f"Không tính được tập giá trị trên {_fmt_sym(component)}: {error}")
            continue
        if component_range.has(sp.ConditionSet):
            warnings.append(f"Tập giá trị trên {_fmt_sym(component)} chưa giải được hoàn toàn.")
            continue
        ranges.append(component_range)
    if len(ranges) != len(components):
        return None, warnings
    return sp.Union(*ranges), warnings


def _extreme_bound_payload(f_expr, active_set, value, kind: str, boundary_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if value in (oo, -oo):
        status = "unbounded_above" if kind == "supremum" else "unbounded_below"
        return {
            "status": status,
            "value": "+∞" if value == oo else "-∞",
            "value_exact": _fmt_sym(value),
            "value_latex": latex(value),
            "value_v2": exact_approx_value(value, method="symbolic_range"),
            "attained": False,
            "attainment_set_exact": None,
            "attainment_set_latex": None,
            "points": [],
            "evidence": _matching_boundary_evidence(boundary_evidence, value),
        }

    try:
        attainment_set = solveset(simplify(f_expr - value), x, domain=active_set)
    except Exception:
        attainment_set = sp.ConditionSet(x, Eq(f_expr, value), active_set)
    complete = not attainment_set.has(sp.ConditionSet)
    attained = complete and attainment_set is not S.EmptySet
    points = []
    if isinstance(attainment_set, FiniteSet):
        points = [_point_value_payload(f_expr, point) for point in sorted(attainment_set, key=default_sort_key)]
    return {
        "status": ("maximum" if kind == "supremum" else "minimum") if attained else kind if complete else "unknown",
        "value": _expr_payload(value)["approx"] or _fmt_sym(value),
        "value_exact": _fmt_sym(value),
        "value_latex": latex(value),
        "value_v2": exact_approx_value(value, method="symbolic_range"),
        "attained": attained,
        "attainment_set_exact": _fmt_sym(attainment_set) if complete else None,
        "attainment_set_latex": latex(attainment_set) if complete else None,
        "points": points,
        "evidence": _matching_boundary_evidence(boundary_evidence, value),
    }


def _matching_boundary_evidence(evidence: list[dict[str, Any]], value) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in evidence:
        raw = item["value"].get("value_exact")
        try:
            if sp.sympify(raw) == value or simplify(sp.sympify(raw) - value) == 0:
                matches.append(item)
        except (TypeError, ValueError, AttributeError, sp.SympifyError):
            continue
    return matches


def _point_value_payload(f_expr, point) -> dict[str, Any]:
    value = simplify(f_expr.subs(x, point))
    return {
        "x": _expr_payload(point)["approx"] or _fmt_sym(point),
        "x_exact": _fmt_sym(point),
        "x_latex": latex(point),
        "x_value": exact_approx_value(point, method="symbolic_range"),
        "y": _expr_payload(value)["approx"] or _fmt_sym(value),
        "y_exact": _fmt_sym(value),
        "y_latex": latex(value),
        "y_value": exact_approx_value(value, method="symbolic_range"),
    }


def _interval_component_payload(component) -> dict[str, Any]:
    return {
        "start": _fmt_boundary(component.start),
        "start_exact": _fmt_sym(component.start),
        "start_approx": exact_approx_value(component.start, method="domain_intersection")["approx"],
        "end": _fmt_boundary(component.end),
        "end_exact": _fmt_sym(component.end),
        "end_approx": exact_approx_value(component.end, method="domain_intersection")["approx"],
        "left_open": bool(component.left_open),
        "right_open": bool(component.right_open),
    }


def _value_payload(value) -> dict[str, Any]:
    if value in (oo, -oo):
        return {
            "status": "infinite",
            "value": "+∞" if value == oo else "-∞",
            "value_exact": _fmt_sym(value),
            "value_latex": latex(value),
            "approx": None,
        }
    if not _is_finite_real(value):
        return {"status": "unknown", "value": None, "value_exact": None, "value_latex": None, "approx": None}
    data = _expr_payload(value)
    return {
        "status": "finite",
        "value": data["approx"] or data["exact"],
        "value_exact": data["exact"],
        "value_latex": data["latex"],
        "approx": data["approx"],
    }


def _is_finite_real(value) -> bool:
    if value in (oo, -oo, zoo, nan, S.NaN) or getattr(value, "is_real", None) is False:
        return False
    try:
        return isfinite(float(sp.N(value)))
    except (TypeError, ValueError, AttributeError):
        return False


def _requested_boundary_value(f_expr, point: float, direction: str, is_open: bool) -> str:
    try:
        value = limit(f_expr, x, point, dir=direction) if is_open else simplify(f_expr.subs(x, point))
    except Exception:
        return "?"
    payload = _value_payload(value)
    return str(payload.get("value") or "?")


def _legacy_extreme_point(extreme: dict[str, Any]) -> dict[str, str]:
    if extreme["points"]:
        point = extreme["points"][0]
        return {"x": point["x"], "y": point["y"], "label": "Điểm đạt"}
    return {
        "x": extreme.get("attainment_set_exact") or (extreme["evidence"][0]["x"] if extreme["evidence"] else "?"),
        "y": extreme["value"],
        "label": "Tập điểm đạt" if extreme["attained"] else "Cận không đạt",
    }


def _extreme_conclusion(extreme: dict[str, Any], upper: bool) -> str:
    if extreme["status"] == "unbounded_above":
        return "Hàm số không bị chặn trên"
    if extreme["status"] == "unbounded_below":
        return "Hàm số không bị chặn dưới"
    if extreme["status"] == "unknown":
        return "Chưa xác định được cận trên" if upper else "Chưa xác định được cận dưới"
    label = "GTLN" if upper else "GTNN"
    if extreme["attained"]:
        return f"{label} = {extreme['value']} trên tập {extreme['attainment_set_exact']}"
    bound = "Supremum" if upper else "Infimum"
    return f"Không có {label}; {bound} = {extreme['value']}"


def _unknown_root_payload(warning: str) -> dict[str, Any]:
    return RootAnalysis("unknown", "unknown", (), (), None, False, 100, None, (warning,)).payload()


def _analyze_line_position(f_expr, line: Mapping[str, Any], domain_info: FunctionDomain | None = None, method_details: dict[str, str] | None = None) -> dict[str, Any]:
    mode = str(line.get("mode", "intersect"))

    if mode == "tangent_at":
        return _analyze_tangent(f_expr, line, domain_info)
    if mode == "tangent_at_point":
        return _analyze_tangent_at_point(f_expr, line, domain_info)
    if mode == "normal_at":
        return _analyze_normal(f_expr, line, domain_info)
    if mode in {"tangent_parallel", "tangent_perpendicular", "tangent_through_point"}:
        return _analyze_tangent_family(f_expr, line, domain_info, mode)

    k = _finite_float(line.get("k", 0), "k")
    b_val = _finite_float(line.get("b", 0), "b")
    line_expr = sp.Rational(str(k)) * x + sp.Rational(str(b_val))
    difference = simplify(f_expr - line_expr)
    root_analysis = analyze_real_roots(difference, x, domain_info)
    intersections = [_intersection_payload(root, line_expr, difference) for root in root_analysis.roots]
    split_points = [root.value for root in root_analysis.roots]
    above, below = _sign_intervals(difference, split_points, domain_info, method_details, "line_position")
    area = _area_between_intersections(difference, root_analysis, domain_info)
    count = root_analysis.total_known if root_analysis.status == "complete" and not root_analysis.families else None

    return {
        "mode": "intersect",
        "k": _fmt_num(k),
        "b": _fmt_num(b_val),
        "equation": f"y = {_fmt_num(k)}x + {_fmt_num(b_val)}",
        "equation_exact": f"y = {_fmt_sym(line_expr)}",
        "equation_latex": f"y={latex(line_expr)}",
        "graph_expression": _fmt_sym(line_expr),
        "intersection_count": count,
        "intersection_count_status": "complete" if count is not None else "unknown",
        "intersections": intersections,
        "roots_v2": root_analysis.payload(),
        "relative_intervals": {"above": above, "below": below},
        "area_between_curves": area.get("total_approx") if area["status"] == "complete" else None,
        "area_v2": area,
        "warnings": list(root_analysis.warnings),
    }


def _intersection_payload(root, line_expr, difference) -> dict[str, Any]:
    root_payload = root.payload()
    y_value = simplify(line_expr.subs(x, root.value))
    y_payload = _expr_payload(y_value)
    multiplicity = _exact_root_multiplicity(difference, root.value) if root.exact else None
    return {
        **root_payload,
        "x": _fmt_num(sp.N(root.value)),
        "y": y_payload["approx"] or y_payload["exact"],
        "y_exact": y_payload["exact"],
        "y_latex": y_payload["latex"],
        "multiplicity": multiplicity,
        "contact_kind": "tangent" if multiplicity is not None and multiplicity >= 2 else "crossing" if multiplicity == 1 else "unknown",
    }


def _exact_root_multiplicity(expression, root) -> int | None:
    try:
        polynomial = sp.Poly(expression, x)
    except (sp.PolynomialError, TypeError, ValueError):
        return None
    derivative = polynomial.as_expr()
    for multiplicity in range(1, polynomial.degree() + 1):
        if simplify(derivative.subs(x, root)) != 0:
            return multiplicity - 1
        derivative = diff(derivative, x)
    return polynomial.degree()


def _area_between_intersections(difference, roots: RootAnalysis, domain_info: FunctionDomain | None) -> dict[str, Any]:
    if roots.status != "complete" or roots.truncated or roots.families or roots.total_known is None:
        return {
            "status": "unavailable",
            "method": "exact_piecewise",
            "components": [],
            "total_exact": None,
            "total_latex": None,
            "total_approx": None,
            "warnings": ["Chưa có tập giao điểm đầy đủ nên không tính diện tích."],
        }
    ordered = sorted((root.value for root in roots.roots), key=default_sort_key)
    if len(ordered) < 2:
        return {
            "status": "unavailable",
            "method": "exact_piecewise",
            "components": [],
            "total_exact": None,
            "total_latex": None,
            "total_approx": None,
            "warnings": ["Cần ít nhất hai giao điểm để tạo miền kín."],
        }

    domain_set = domain_info.set if domain_info is not None and domain_info.set is not None else S.Reals
    components: list[dict[str, Any]] = []
    warnings: list[str] = []
    total = S.Zero
    for left, right in zip(ordered, ordered[1:]):
        closed_interval = Interval(left, right)
        try:
            continuous = continuous_domain(difference, x, S.Reals)
            if closed_interval.intersect(domain_set).intersect(continuous) != closed_interval:
                warnings.append(f"Bỏ qua ({_fmt_sym(left)}, {_fmt_sym(right)}): hàm không liên tục trên miền kín.")
                continue
            probe = (left + right) / 2
            sign = _safe_expr_sign(difference, probe)
            if sign is None:
                warnings.append(f"Bỏ qua ({_fmt_sym(left)}, {_fmt_sym(right)}): chưa xác định được dấu giữa hai giao điểm.")
                continue
            exact_area = simplify(sp.integrate(difference if sign > 0 else -difference, (x, left, right)))
            if exact_area.has(sp.Integral) or not _is_finite_real(exact_area) or exact_area < 0:
                warnings.append(f"Bỏ qua ({_fmt_sym(left)}, {_fmt_sym(right)}): tích phân không hội tụ hoặc chưa tính được.")
                continue
        except Exception as error:
            warnings.append(f"Bỏ qua ({_fmt_sym(left)}, {_fmt_sym(right)}): {error}")
            continue
        total += exact_area
        data = _expr_payload(exact_area)
        components.append({
            "left": _expr_payload(left)["approx"] or _fmt_sym(left),
            "left_exact": _fmt_sym(left),
            "left_latex": latex(left),
            "right": _expr_payload(right)["approx"] or _fmt_sym(right),
            "right_exact": _fmt_sym(right),
            "right_latex": latex(right),
            "area": data["approx"] or data["exact"],
            "area_exact": data["exact"],
            "area_latex": data["latex"],
            "area_approx": data["approx"],
            "verification": "continuous_between_consecutive_exact_intersections",
        })

    complete = len(components) == len(ordered) - 1 and not warnings
    total_data = _expr_payload(simplify(total)) if complete else None
    return {
        "status": "complete" if complete else "partial",
        "method": "exact_piecewise",
        "components": components,
        "total_exact": total_data["exact"] if total_data else None,
        "total_latex": total_data["latex"] if total_data else None,
        "total_approx": (total_data["approx"] or total_data["exact"]) if total_data else None,
        "warnings": warnings,
    }


def _analyze_tangent(f_expr, line: Mapping[str, Any], domain_info: FunctionDomain | None) -> dict[str, Any]:
    x0 = _finite_float(line.get("x0", 0), "x0")
    point = simplify(line["_x0_exact"]) if "_x0_exact" in line else sp.Rational(str(x0))
    if not in_domain(domain_info, point):
        raise ValueError(f"x0={_fmt_num(x0)} không thuộc tập xác định.")
    y0 = simplify(f_expr.subs(x, point))
    if not _is_finite_real(y0):
        raise ValueError(f"f({_fmt_num(x0)}) không phải giá trị hữu hạn.")

    quotient = simplify((f_expr - y0) / (x - point))
    side_slopes: dict[str, Any] = {}
    try:
        if _domain_side_available(domain_info, point, "-"):
            side_slopes["left"] = limit(quotient, x, point, dir="-")
        if _domain_side_available(domain_info, point, "+"):
            side_slopes["right"] = limit(quotient, x, point, dir="+")
    except Exception as error:
        raise ValueError(f"Không chứng minh được đạo hàm tại x0={_fmt_num(x0)}: {error}") from error
    if not side_slopes:
        raise ValueError(f"x0={_fmt_num(x0)} không có lân cận thuộc tập xác định.")

    base = {
        "mode": "tangent_at",
        "x0": _fmt_num(x0),
        "x0_exact": _fmt_sym(point),
        "y0": _expr_payload(y0)["approx"] or _fmt_sym(y0),
        "y0_exact": _fmt_sym(y0),
        "left_slope": _value_payload(side_slopes["left"]) if "left" in side_slopes else {"status": "unavailable", "value": None, "value_exact": None, "value_latex": None, "approx": None},
        "right_slope": _value_payload(side_slopes["right"]) if "right" in side_slopes else {"status": "unavailable", "value": None, "value_exact": None, "value_latex": None, "approx": None},
    }
    slopes = list(side_slopes.values())
    if all(slope in (oo, -oo) for slope in slopes) and (len(slopes) == 1 or all(slope == slopes[0] for slope in slopes[1:])):
        equation = f"x = {_fmt_num(x0)}"
        verification = "one_sided_infinite_slope" if len(slopes) == 1 else "matching_infinite_one_sided_slopes"
        return {**base, "status": "vertical_tangent", "kind": "vertical", "equation": equation, "equation_exact": equation, "verification": verification, "conclusion": f"Tiếp tuyến đứng tại điểm ({_fmt_num(x0)}, {_fmt_num(y0)}) là: {equation}"}
    finite_slopes = all(_is_finite_real(slope) for slope in slopes)
    matching_slopes = len(slopes) == 1 or all(simplify(slope - slopes[0]) == 0 for slope in slopes[1:])
    if not finite_slopes or not matching_slopes:
        kind = "cusp" if len(slopes) == 2 and all(slope in (oo, -oo) for slope in slopes) else "corner_or_nondifferentiable"
        return {**base, "status": "nondifferentiable", "kind": kind, "equation": "Không tồn tại", "equation_exact": None, "verification": "one_sided_slopes_disagree", "conclusion": f"Không có tiếp tuyến đạo hàm thông thường tại x = {_fmt_num(x0)} vì đạo hàm hai phía không trùng nhau."}

    slope = simplify(slopes[0])
    intercept = simplify(y0 - slope * point)
    equation_expr = simplify(slope * x + intercept)
    contact_direction = "+" if set(side_slopes) == {"right"} else "-" if set(side_slopes) == {"left"} else "+-"
    contact = limit((f_expr - equation_expr) / (x - point), x, point, dir=contact_direction)
    equation = f"y = {_fmt_sym(equation_expr)}"
    slope_data = _expr_payload(slope)
    return {
        **base,
        "status": "regular_tangent",
        "kind": "regular",
        "k": slope_data["approx"] or slope_data["exact"],
        "k_exact": slope_data["exact"],
        "k_latex": slope_data["latex"],
        "b": _expr_payload(intercept)["approx"] or _fmt_sym(intercept),
        "b_exact": _fmt_sym(intercept),
        "equation": equation,
        "equation_exact": equation,
        "equation_latex": f"y={latex(equation_expr)}",
        "graph_expression": _fmt_sym(equation_expr),
        "verification": "difference_quotient_one_sided" if len(slopes) == 1 else "difference_quotient_two_sided",
        "contact_limit": _fmt_sym(contact),
        "conclusion": f"Tiếp tuyến tại điểm ({_fmt_num(x0)}, {_fmt_num(y0)}) là: {equation}",
    }


def _analyze_tangent_at_point(f_expr, line: Mapping[str, Any], domain_info: FunctionDomain | None) -> dict[str, Any]:
    point_x = sp.Rational(str(_finite_float(line.get("x0", 0), "x0")))
    requested_y = sp.Rational(str(_finite_float(line.get("y0", 0), "y0")))
    if not in_domain(domain_info, point_x):
        raise ValueError(f"x={_fmt_sym(point_x)} không thuộc tập xác định.")
    actual_y = simplify(f_expr.subs(x, point_x))
    if simplify(actual_y - requested_y) != 0:
        return {
            "mode": "tangent_at_point",
            "status": "point_not_on_graph",
            "kind": "invalid_contact_point",
            "x0": _fmt_sym(point_x),
            "x0_exact": _fmt_sym(point_x),
            "y0": _fmt_sym(requested_y),
            "y0_exact": _fmt_sym(requested_y),
            "actual_y_exact": _fmt_sym(actual_y),
            "equation": "Không tồn tại",
            "equation_exact": None,
            "graph_expression": None,
            "verification": "exact_point_substitution",
            "warnings": ["Điểm yêu cầu không thuộc đồ thị."],
            "conclusion": f"Điểm ({_fmt_sym(point_x)}, {_fmt_sym(requested_y)}) không thuộc đồ thị; f({_fmt_sym(point_x)}) = {_fmt_sym(actual_y)}.",
        }
    tangent = _analyze_tangent(f_expr, {"x0": float(point_x), "_x0_exact": point_x}, domain_info)
    return {
        **tangent,
        "mode": "tangent_at_point",
        "requested_point": {"x_exact": _fmt_sym(point_x), "y_exact": _fmt_sym(requested_y)},
        "point_verification": "exact_point_substitution",
    }


def _analyze_tangent_family(
    f_expr,
    line: Mapping[str, Any],
    domain_info: FunctionDomain | None,
    mode: str,
) -> dict[str, Any]:
    derivative = simplify(diff(f_expr, x))
    condition: Any
    condition_label: str
    if mode == "tangent_parallel":
        target_slope = sp.Rational(str(_finite_float(line.get("k", 0), "k")))
        condition = simplify(derivative - target_slope)
        condition_label = f"f'(x) = {_fmt_sym(target_slope)}"
    elif mode == "tangent_perpendicular":
        reference_slope = sp.Rational(str(_finite_float(line.get("k", 0), "k")))
        if reference_slope == 0:
            return {
                "mode": mode,
                "status": "unsupported",
                "equation": "Chưa xác định",
                "equation_exact": None,
                "graph_expression": None,
                "graph_expressions": [],
                "tangents": [],
                "warnings": ["Đường thẳng tham chiếu nằm ngang cần tìm tiếp tuyến đứng; mode này chưa chứng minh được tiếp tuyến đứng toàn cục."],
            }
        target_slope = simplify(-1 / reference_slope)
        condition = simplify(derivative - target_slope)
        condition_label = f"f'(x) = {_fmt_sym(target_slope)}"
    else:
        point_x = sp.Rational(str(_finite_float(line.get("x0", 0), "x0")))
        point_y = sp.Rational(str(_finite_float(line.get("b", 0), "b")))
        condition = simplify(f_expr + derivative * (point_x - x) - point_y)
        condition_label = f"f(x) + f'(x)*({_fmt_sym(point_x)} - x) = {_fmt_sym(point_y)}"

    roots = analyze_real_roots(condition, x, domain_info)
    tangents: list[dict[str, Any]] = []
    warnings = list(roots.warnings)
    for root in roots.roots[:12]:
        try:
            tangent = _analyze_tangent(f_expr, {"x0": float(sp.N(root.value)), "_x0_exact": root.value}, domain_info)
        except (TypeError, ValueError, AttributeError) as error:
            warnings.append(f"Bỏ qua tiếp điểm {_fmt_sym(root.value)}: {error}")
            continue
        if tangent["status"] != "regular_tangent":
            warnings.append(f"Ứng viên {_fmt_sym(root.value)} không cho tiếp tuyến hữu hạn phù hợp.")
            continue
        tangents.append({
            "x0": tangent["x0"],
            "x0_exact": _fmt_sym(root.value),
            "y0": tangent["y0"],
            "y0_exact": tangent["y0_exact"],
            "equation": tangent["equation"],
            "equation_exact": tangent["equation_exact"],
            "equation_latex": tangent["equation_latex"],
            "graph_expression": tangent["graph_expression"],
            "verification": tangent["verification"],
        })
    truncated = len(roots.roots) > 12 or roots.truncated
    complete = roots.status == "complete" and not truncated and not warnings
    equations = [item["graph_expression"] for item in tangents]
    return {
        "mode": mode,
        "status": "complete" if complete else "partial" if tangents else roots.status,
        "condition_exact": condition_label,
        "candidate_roots_v2": roots.payload(),
        "tangent_count": len(tangents) if complete else None,
        "tangent_count_known": len(tangents),
        "tangents": tangents,
        "equation": tangents[0]["equation"] if len(tangents) == 1 else f"{len(tangents)} tiếp tuyến đã xác nhận",
        "equation_exact": tangents[0]["equation_exact"] if len(tangents) == 1 else None,
        "equation_latex": tangents[0]["equation_latex"] if len(tangents) == 1 else None,
        "graph_expression": equations[0] if len(equations) == 1 else None,
        "graph_expressions": equations,
        "warnings": warnings + (["Danh sách tiếp tuyến bị giới hạn ở 12 kết quả."] if truncated else []),
    }


def _analyze_normal(f_expr, line: Mapping[str, Any], domain_info: FunctionDomain | None) -> dict[str, Any]:
    tangent = _analyze_tangent(f_expr, line, domain_info)
    base = {
        "mode": "normal_at",
        "x0": tangent["x0"],
        "x0_exact": tangent["x0_exact"],
        "y0": tangent["y0"],
        "y0_exact": tangent["y0_exact"],
        "source_tangent_status": tangent["status"],
        "source_tangent_equation_exact": tangent.get("equation_exact"),
    }
    if tangent["status"] == "nondifferentiable":
        return {
            **base,
            "status": "nondifferentiable",
            "kind": tangent["kind"],
            "equation": "Không tồn tại",
            "equation_exact": None,
            "graph_expression": None,
            "verification": tangent["verification"],
            "conclusion": "Không xác định pháp tuyến vì hàm không khả vi tại điểm đã chọn.",
        }

    point = parse_safe_math_expression(tangent["x0_exact"]).expr
    y0 = parse_safe_math_expression(tangent["y0_exact"]).expr
    if tangent["status"] == "vertical_tangent":
        equation_expr = simplify(y0)
        equation = f"y = {_fmt_sym(equation_expr)}"
        return {
            **base,
            "status": "regular_normal",
            "kind": "horizontal",
            "k_exact": "0",
            "b_exact": _fmt_sym(y0),
            "equation": equation,
            "equation_exact": equation,
            "equation_latex": f"y={latex(equation_expr)}",
            "graph_expression": _fmt_sym(equation_expr),
            "verification": "perpendicular_to_vertical_tangent",
            "conclusion": f"Pháp tuyến tại ({tangent['x0']}, {tangent['y0']}) là: {equation}",
        }

    tangent_slope = parse_safe_math_expression(str(tangent["k_exact"])).expr
    if simplify(tangent_slope) == 0:
        equation = f"x = {_fmt_sym(point)}"
        return {
            **base,
            "status": "vertical_normal",
            "kind": "vertical",
            "equation": equation,
            "equation_exact": equation,
            "graph_expression": None,
            "verification": "perpendicular_to_horizontal_tangent",
            "conclusion": f"Pháp tuyến đứng tại ({tangent['x0']}, {tangent['y0']}) là: {equation}",
        }

    slope = simplify(-1 / tangent_slope)
    intercept = simplify(y0 - slope * point)
    equation_expr = simplify(slope * x + intercept)
    equation = f"y = {_fmt_sym(equation_expr)}"
    return {
        **base,
        "status": "regular_normal",
        "kind": "regular",
        "k": _expr_payload(slope)["approx"] or _fmt_sym(slope),
        "k_exact": _fmt_sym(slope),
        "b": _expr_payload(intercept)["approx"] or _fmt_sym(intercept),
        "b_exact": _fmt_sym(intercept),
        "equation": equation,
        "equation_exact": equation,
        "equation_latex": f"y={latex(equation_expr)}",
        "graph_expression": _fmt_sym(equation_expr),
        "verification": "negative_reciprocal_of_verified_tangent",
        "conclusion": f"Pháp tuyến tại ({tangent['x0']}, {tangent['y0']}) là: {equation}",
    }


def _domain_side_available(domain_info: FunctionDomain | None, point, side: str) -> bool:
    domain_set = domain_info.set if domain_info is not None and domain_info.set is not None else S.Reals
    for component in _iter_intervals(domain_set):
        try:
            if side == "-" and _truth(component.start < point) and _truth(point <= component.end):
                return True
            if side == "+" and _truth(component.start <= point) and _truth(point < component.end):
                return True
        except (TypeError, ValueError, AttributeError):
            continue
    return False


def _truth(value) -> bool:
    return value is sp.S.true or value is True or sp.simplify(value) is sp.S.true


def _solve_parameter_conditions(parsed, options: Mapping[str, Any]) -> list[dict[str, Any]]:
    targets = options.get("targets") or []
    results: list[dict[str, Any]] = []
    if m not in parsed.free_symbols:
        return [{"label": "Tham số m", "solution": "Biểu thức không chứa m.", "solution_latex": "\\varnothing", "warnings": []}]
    try:
        fp = simplify(diff(parsed, x))
        poly = Poly(fp, x)
    except Exception:
        return [{"label": "Điều kiện tham số", "solution": "Chỉ hỗ trợ đạo hàm đa thức theo x trong phiên bản này.", "solution_latex": "", "warnings": ["Không đưa được f'(x) về đa thức theo x."]}]

    for target in targets:
        if target == "increasing_r":
            solution = _solve_polynomial_nonnegative(poly)
            results.append({"label": "Đồng biến trên R", "condition_latex": latex(fp) + r" \ge 0,\ \forall x\in\mathbb{R}", "solution": str(solution), "solution_latex": latex(solution), "warnings": []})
        elif target == "decreasing_r":
            solution = _solve_polynomial_nonnegative(Poly(-fp, x))
            results.append({"label": "Nghịch biến trên R", "condition_latex": latex(fp) + r" \le 0,\ \forall x\in\mathbb{R}", "solution": str(solution), "solution_latex": latex(solution), "warnings": []})
        elif target == "extrema_count":
            expected = int(options.get("extrema_count", 1))
            result = _solve_extrema_count(poly, expected)
            results.append(result)
    return results


def _build_transform_preview(f_expr, transform: Mapping[str, Any]) -> dict[str, Any]:
    transform_type = str(transform.get("type", "vertical_shift"))
    value = _finite_float(transform.get("value", 0), "giá trị biến đổi")
    
    steps = []
    if transform_type == "vertical_shift":
        transformed = f_expr + value
        label = f"f(x) {'+' if value >= 0 else '-'} {_fmt_num(abs(value))}"
        dir_text = "lên trên" if value > 0 else "xuống dưới"
        steps.append(f"Tịnh tiến đồ thị ban đầu {dir_text} {_fmt_num(abs(value))} đơn vị theo trục tung.")
        
    elif transform_type == "horizontal_shift":
        transformed = f_expr.subs(x, x - value)
        label = f"f(x {'-' if value >= 0 else '+'} {_fmt_num(abs(value))})"
        dir_text = "sang phải" if value > 0 else "sang trái"
        steps.append(f"Tịnh tiến đồ thị ban đầu {dir_text} {_fmt_num(abs(value))} đơn vị theo trục hoành.")
        
    elif transform_type == "vertical_scale":
        transformed = value * f_expr
        label = f"{_fmt_num(value)}f(x)"
        steps.append(f"Kéo dãn/co đồ thị theo phương thẳng đứng với hệ số {_fmt_num(value)}.")
        
    elif transform_type == "horizontal_scale":
        transformed = f_expr.subs(x, value * x)
        label = f"f({_fmt_num(value)}x)"
        steps.append(f"Kéo dãn/co đồ thị theo phương ngang với hệ số {_fmt_num(value)}.")
        
    elif transform_type == "reflect_x":
        transformed = -f_expr
        label = "-f(x)"
        steps.append("Lấy đối xứng toàn bộ đồ thị qua trục hoành.")
        
    elif transform_type == "reflect_y":
        transformed = f_expr.subs(x, -x)
        label = "f(-x)"
        steps.append("Lấy đối xứng toàn bộ đồ thị qua trục tung.")
        
    elif transform_type == "absolute_all":
        transformed = Abs(f_expr)
        label = "|f(x)|"
        steps.append("Bước 1: Giữ nguyên phần đồ thị phía trên trục hoành.")
        steps.append("Bước 2: Lấy đối xứng phần đồ thị phía dưới trục hoành qua trục hoành.")
        steps.append("Bước 3: Xóa bỏ phần đồ thị ban đầu nằm dưới trục hoành.")
        
    elif transform_type == "absolute_x":
        transformed = f_expr.subs(x, Abs(x))
        label = "f(|x|)"
        steps.append("Bước 1: Giữ nguyên phần đồ thị bên phải trục tung (x ≥ 0).")
        steps.append("Bước 2: Bỏ đi phần đồ thị bên trái trục tung (x < 0).")
        steps.append("Bước 3: Lấy đối xứng phần đồ thị bên phải trục tung sang bên trái.")
        
    else:
        transformed = f_expr
        label = "f(x)"
        steps.append("Không có biến đổi nào được áp dụng.")

    transformed = simplify(transformed)
    requires_value = transform_type in {"vertical_shift", "horizontal_shift", "vertical_scale", "horizontal_scale"}
    transformed_domain = None
    transformed_range = None
    try:
        transformed_domain_set = continuous_domain(transformed, x, S.Reals)
        transformed_domain = _fmt_sym(transformed_domain_set)
        transformed_range = _fmt_sym(function_range(transformed, x, transformed_domain_set))
    except Exception:
        pass
    return {
        "type": transform_type,
        "value": _fmt_num(value),
        "label": label,
        "expression": _fmt_sym(transformed),
        "expression_latex": latex(transformed),
        "convention": _transform_convention(transform_type),
        "expression_template": _transform_template(transform_type),
        "requires_value": requires_value,
        "transformed_domain": transformed_domain,
        "transformed_range": transformed_range,
        "invariants": _transform_invariants(transform_type),
        "anchors": _transform_anchors(f_expr, transform_type, value),
        "pedagogical_steps": steps,
    }


def _transform_convention(transform_type: str) -> str:
    return {
        "vertical_shift": "a>0: dịch lên; a<0: dịch xuống",
        "horizontal_shift": "g(x)=f(x-a); a>0: dịch phải; a<0: dịch trái",
        "vertical_scale": "|a| co/kéo dọc; a<0 đối xứng qua Ox; a=0 cho hàm hằng 0",
        "horizontal_scale": "|a| co/kéo ngang theo 1/|a|; a<0 đối xứng qua Oy; a=0 cho hàm hằng f(0) nếu xác định",
        "reflect_x": "đối xứng qua Ox",
        "reflect_y": "đối xứng qua Oy",
        "absolute_all": "phần y<0 đối xứng lên trên",
        "absolute_x": "nửa phải phản chiếu qua Oy",
    }[transform_type]


def _transform_template(transform_type: str) -> str:
    return {
        "vertical_shift": "g(x)=f(x)+a",
        "horizontal_shift": "g(x)=f(x-a)",
        "vertical_scale": "g(x)=a*f(x)",
        "horizontal_scale": "g(x)=f(a*x)",
        "reflect_x": "g(x)=-f(x)",
        "reflect_y": "g(x)=f(-x)",
        "absolute_all": "g(x)=|f(x)|",
        "absolute_x": "g(x)=f(|x|)",
    }[transform_type]


def _transform_invariants(transform_type: str) -> list[str]:
    return {
        "vertical_shift": ["domain", "shape"],
        "horizontal_shift": ["range", "shape"],
        "vertical_scale": ["domain", "x_coordinates"],
        "horizontal_scale": ["range"],
        "reflect_x": ["domain", "x_coordinates"],
        "reflect_y": ["range", "y_coordinates"],
        "absolute_all": ["domain", "x_coordinates", "zeros"],
        "absolute_x": ["even_symmetry"],
    }[transform_type]


def _transform_anchors(f_expr, transform_type: str, value: float) -> list[dict[str, float]]:
    anchors: list[dict[str, float]] = []
    for source_x in (-1.0, 0.0, 1.0):
        source_y = _eval_float(f_expr, source_x)
        if source_y is None:
            continue
        if transform_type == "vertical_shift":
            target_x, target_y = source_x, source_y + value
        elif transform_type == "horizontal_shift":
            target_x, target_y = source_x + value, source_y
        elif transform_type == "vertical_scale":
            target_x, target_y = source_x, source_y * value
        elif transform_type == "horizontal_scale":
            if value == 0:
                continue
            target_x, target_y = source_x / value, source_y
        elif transform_type == "reflect_x":
            target_x, target_y = source_x, -source_y
        elif transform_type == "reflect_y":
            target_x, target_y = -source_x, source_y
        elif transform_type == "absolute_all":
            target_x, target_y = source_x, abs(source_y)
        else:
            target_x, target_y = abs(source_x), source_y
        anchors.append({"source_x": source_x, "source_y": source_y, "target_x": target_x, "target_y": target_y})
    return anchors


def _solve_polynomial_nonnegative(poly) -> Any:
    expr = poly.as_expr()
    degree = poly.degree()
    if degree == 0:
        return solve_univariate_inequality(expr >= 0, m, relational=False)
    if degree == 1:
        slope_zero = solve_univariate_inequality(Eq(poly.nth(1), 0), m, relational=False)
        intercept_ok = solve_univariate_inequality(poly.nth(0) >= 0, m, relational=False)
        return slope_zero.intersect(intercept_ok)
    if degree == 2:
        a = poly.nth(2)
        delta = discriminant(expr, x)
        return solve_univariate_inequality(a > 0, m, relational=False).intersect(solve_univariate_inequality(delta <= 0, m, relational=False))
    return "Chỉ hỗ trợ bậc 0, 1, 2 cho điều kiện mọi x."


def _solve_extrema_count(poly, expected: int) -> dict[str, Any]:
    expr = poly.as_expr()
    degree = poly.degree()
    warnings: list[str] = []
    if degree == 2:
        delta = discriminant(expr, x)
        if expected == 2:
            solution = solve_univariate_inequality(delta > 0, m, relational=False)
        elif expected == 1:
            solution = solve_univariate_inequality(delta == 0, m, relational=False)
        else:
            solution = solve_univariate_inequality(delta < 0, m, relational=False)
        return {"label": f"Có {expected} cực trị", "condition_latex": latex(delta) + (r" > 0" if expected == 2 else r" = 0" if expected == 1 else r" < 0"), "solution": str(solution), "solution_latex": latex(solution), "warnings": warnings}
    warnings.append("Đếm cực trị hiện hỗ trợ tốt nhất khi f'(x) là tam thức bậc hai.")
    return {"label": f"Có {expected} cực trị", "solution": "Chưa hỗ trợ dạng này.", "solution_latex": "", "warnings": warnings}


def _solve_domain_roots(expr, domain_info: FunctionDomain | None = None) -> tuple[list[Any], bool]:
    try:
        solution_set = intersect_domain(solveset(expr, x, domain=S.Reals), domain_info)
    except (NotImplementedError, TypeError, ValueError, AttributeError):
        return filter_domain_values(_solve_real_roots(expr)[:12], domain_info), False
    if solution_set is S.EmptySet:
        return [], True
    if isinstance(solution_set, FiniteSet):
        roots = []
        for root in solution_set:
            try:
                simplified = simplify(root)
                if simplified.is_real is False:
                    continue
                float(simplified.evalf())
                roots.append(simplified)
            except Exception:
                continue
        return sorted(roots, key=default_sort_key), True
    return filter_domain_values(_solve_real_roots(expr)[:12], domain_info), False


def _solve_real_roots(expr) -> list:
    try:
        polynomial = Poly(expr, x)
        roots = polynomial.real_roots()
    except Exception:
        roots = None
    if roots is None:
        try:
            solution_set = solveset(expr, x, domain=S.Reals)
        except Exception:
            solution_set = S.EmptySet
        if isinstance(solution_set, FiniteSet):
            roots = list(solution_set)
        else:
            try:
                roots = solve(expr, x)
            except Exception:
                roots = []
    result: list = []
    seen: set[str] = set()
    for root in roots:
        try:
            simplified = simplify(root)
            if simplified.is_real is False:
                continue
            float(simplified.evalf())
        except Exception:
            continue
        key = str(simplified)
        if key in seen:
            continue
        seen.add(key)
        result.append(simplified)
    return sorted(result, key=default_sort_key)


def _numeric_roots(expr) -> list[float]:
    roots: list[float] = []
    last_x = -20.0
    last_y = _eval_float(expr, last_x)
    for i in range(1, 801):
        cur_x = -20.0 + i * 0.05
        cur_y = _eval_float(expr, cur_x)
        if last_y is not None and cur_y is not None and last_y * cur_y <= 0:
            roots.append((last_x + cur_x) / 2)
        last_x, last_y = cur_x, cur_y
    unique: list[float] = []
    for root in roots:
        if all(abs(root - existing) > 0.1 for existing in unique):
            unique.append(root)
    return unique[:12]


def _finite_float(value, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} phải là số hữu hạn.") from e
    if not isfinite(parsed):
        raise ValueError(f"{name} phải là số hữu hạn.")
    return parsed


def _eval_float(expr, x_value: float) -> float | None:
    try:
        val = float(expr.subs(x, x_value).evalf())
    except Exception:
        return None
    if not isfinite(val):
        return None
    return val


def _point_result(item: Mapping[str, Any]) -> dict[str, str]:
    return {"x": _fmt_num(item["x"]), "y": _fmt_num(item["y"]), "label": str(item.get("label", ""))}


def _sign_chart(
    expr,
    domain_info: FunctionDomain | None = None,
    *,
    role: str = "sign",
    known_breakpoints: list[Any] | None = None,
) -> dict[str, Any]:
    if expr is None:
        return {"status": "unknown", "method": "unknown", "segments": [], "positive_intervals": [], "negative_intervals": [], "zero_points": [], "singular_points": [], "warnings": ["Không có biểu thức để xét dấu."]}

    domain_set = domain_info.set if domain_info is not None else S.Reals
    warnings: list[str] = []
    try:
        simplified = simplify(expr)
        if simplified == 0:
            intervals = _domain_interval_payloads(domain_set)
            return {"status": "complete", "method": "symbolic_exact", "segments": [{**interval, "sign": "0", "verification": "exact"} for interval in intervals], "positive_intervals": [], "negative_intervals": [], "zero_points": [], "singular_points": [], "warnings": []}
        positive_set = intersect_domain(solveset(simplified > 0, x, domain=S.Reals), domain_info)
        negative_set = intersect_domain(solveset(simplified < 0, x, domain=S.Reals), domain_info)
        zero_set = intersect_domain(solveset(simplified, x, domain=S.Reals), domain_info)
        if not positive_set.has(sp.ConditionSet) and not negative_set.has(sp.ConditionSet):
            positive = _set_interval_payloads(positive_set, "+")
            negative = _set_interval_payloads(negative_set, "-")
            zero_points = _finite_set_payloads(zero_set)
            segments = [*positive, *negative]
            segments.sort(key=lambda item: _variation_order_key(item["left_exact"]))
            return {"status": "complete", "method": "symbolic_exact", "segments": segments, "positive_intervals": positive, "negative_intervals": negative, "zero_points": zero_points, "singular_points": [], "warnings": []}
    except (NotImplementedError, TypeError, ValueError, AttributeError):
        pass

    sampled = _adaptive_sign_chart(expr, domain_info, known_breakpoints or [])
    sampled["warnings"] = [*sampled.get("warnings", []), f"{role}: chưa chứng minh được dấu bằng symbolic, dùng adaptive sampling."]
    return sampled


def _adaptive_sign_chart(expr, domain_info: FunctionDomain | None, known_breakpoints: list[Any]) -> dict[str, Any]:
    components = list(domain_info.components) if domain_info is not None else [Interval(-oo, oo)]
    if not components:
        return {"status": "unknown", "method": "unknown", "segments": [], "positive_intervals": [], "negative_intervals": [], "zero_points": [], "singular_points": [], "warnings": ["Không có miền liên thông hữu hạn để sampling."]}

    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    warnings: list[str] = []
    sample_count = 0
    for component in components:
        points = [component.start, *[point for point in known_breakpoints if _point_inside_interval(point, component)], component.end]
        points = sorted(set(points), key=default_sort_key)
        for left, right in zip(points, points[1:]):
            probe_points = _adaptive_probe_points(left, right)
            if not probe_points:
                warnings.append(f"Bỏ qua khoảng ({_fmt_boundary(left)}; {_fmt_boundary(right)}) vì không có điểm kiểm chứng ổn định.")
                continue
            signs: list[int] = []
            for probe in probe_points:
                sign = _safe_expr_sign(expr, probe)
                sample_count += 1
                if sign is not None:
                    signs.append(sign)
            if not signs or any(sign != signs[0] for sign in signs):
                warnings.append(f"Dấu chưa ổn định trên ({_fmt_boundary(left)}; {_fmt_boundary(right)}).")
                continue
            segment = _interval_payload(left, right, "+" if signs[0] > 0 else "-", "sampled", error_bound=_sampling_error_bound(probe_points))
            if signs[0] > 0:
                positive.append(segment)
            else:
                negative.append(segment)
    segments = [*positive, *negative]
    segments.sort(key=lambda item: _variation_order_key(item["left_exact"]))
    status = "partial" if segments else "unknown"
    return {"status": status, "method": "numeric_adaptive" if segments else "unknown", "segments": segments, "positive_intervals": positive, "negative_intervals": negative, "zero_points": [], "singular_points": [], "sample_count": sample_count, "warnings": _unique_texts(warnings)}


def _safe_expr_sign(expr, value) -> int | None:
    try:
        numeric = float(expr.subs(x, value).evalf())
    except Exception:
        return None
    if not isfinite(numeric) or abs(numeric) < 1e-12:
        return None
    return 1 if numeric > 0 else -1


def _adaptive_probe_points(left, right) -> list[Any]:
    try:
        if left in (-oo, oo) or right in (-oo, oo):
            if left == -oo and right == oo:
                return [S.Zero, S.One, -S.One]
            if left == -oo:
                return [right - 1, right - 2, right - 4]
            if right == oo:
                return [left + 1, left + 2, left + 4]
            return []
        span = right - left
        return [left + span / 4, left + span / 2, left + 3 * span / 4]
    except (TypeError, ValueError, AttributeError):
        return []


def _sampling_error_bound(points: list[Any]) -> str | None:
    try:
        numeric = [abs(float(sp.N(point))) for point in points]
    except Exception:
        return None
    scale = max([1.0, *numeric])
    return f"<= {scale * 1e-12:.3g} quanh mẫu"


def _point_inside_interval(point, interval) -> bool:
    try:
        if point == interval.start or point == interval.end:
            return False
        return interval.contains(point) is S.true
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return False


def _domain_interval_payloads(domain_set) -> list[dict[str, Any]]:
    return [_interval_payload(part.start, part.end, "0", "exact") for part in _iter_intervals(domain_set)]


def _set_interval_payloads(value_set, sign: str) -> list[dict[str, Any]]:
    return [_interval_payload(part.start, part.end, sign, "exact") for part in _iter_intervals(value_set)]


def _iter_intervals(value_set) -> list[Any]:
    if value_set in (S.EmptySet, None):
        return []
    if value_set == S.Reals:
        return [Interval(-oo, oo)]
    if isinstance(value_set, Interval):
        return [value_set]
    if isinstance(value_set, sp.Union):
        return [part for part in value_set.args if isinstance(part, Interval)]
    return []


def _interval_payload(left, right, sign: str, verification: str, *, error_bound: str | None = None) -> dict[str, Any]:
    payload = {
        "left": _fmt_boundary(left),
        "right": _fmt_boundary(right),
        "left_exact": _fmt_sym(left),
        "right_exact": _fmt_sym(right),
        "sign": sign,
        "verification": verification,
    }
    if error_bound:
        payload["error_bound"] = error_bound
    return payload


def _finite_set_payloads(value_set) -> list[dict[str, Any]]:
    if not isinstance(value_set, FiniteSet):
        return []
    result: list[dict[str, Any]] = []
    for item in sorted(value_set, key=default_sort_key):
        result.append({"x": _fmt_num(item), "x_exact": _fmt_sym(item), "x_latex": latex(item)})
    return result


def _chart_intervals(chart: dict[str, Any], sign: str) -> list[str]:
    key = "positive_intervals" if sign == "+" else "negative_intervals"
    return [f"({_format_chart_bound(item['left_exact'])}; {_format_chart_bound(item['right_exact'])})" for item in chart.get(key, [])]


def _format_chart_bound(value: str) -> str:
    if value in {"-oo", "-∞"}:
        return "-∞"
    if value in {"oo", "+∞", "∞"}:
        return "+∞"
    return value


def _sign_intervals(
    expr,
    breakpoints: list[float],
    domain_info: FunctionDomain | None = None,
    method_details: dict[str, str] | None = None,
    method_key: str | None = None,
) -> tuple[list[str], list[str]]:
    chart = _sign_chart(expr, domain_info, role=method_key or "sign", known_breakpoints=breakpoints)
    if method_details is not None and method_key:
        method_details[method_key] = chart["method"]
    return _chart_intervals(chart, "+"), _chart_intervals(chart, "-")


def _format_real_interval_set(value_set) -> list[str]:
    result: list[str] = []
    parts = value_set.args if isinstance(value_set, sp.Union) else [value_set]
    for part in parts:
        if not isinstance(part, sp.Interval):
            continue
        a_str = _bound_label(float(part.start)) if part.start.is_finite else ("-∞" if part.start == -sp.oo else "+∞")
        b_str = _bound_label(float(part.end)) if part.end.is_finite else ("-∞" if part.end == -sp.oo else "+∞")
        left = "(" if part.left_open else "["
        right = ")" if part.right_open else "]"
        result.append(f"{left}{a_str}; {b_str}{right}")
    return result


def _periodic_variation_table_v2(result: dict[str, Any]) -> dict[str, Any] | None:
    monotonicity = result.get("monotonicity_v2") or {}
    if not monotonicity.get("periodic"):
        return None
    segments = monotonicity.get("segments", [])
    if not segments:
        return None
    nodes_by_key: dict[str, dict[str, Any]] = {}
    table_segments: list[dict[str, Any]] = []
    for segment in segments:
        for side in ("left", "right"):
            value = segment.get(side)
            exact = segment.get(f"{side}_exact") or value
            if not value:
                continue
            nodes_by_key.setdefault(str(exact), {"kind": "boundary", "x": str(value), "x_exact": str(exact), "label": "mốc chu kỳ"})
        table_segments.append({
            "left": str(segment.get("left")),
            "right": str(segment.get("right")),
            "direction": segment.get("direction", "unknown"),
            "verification": segment.get("verification", monotonicity.get("method", "unknown")),
            "derivative_sign": segment.get("derivative_sign", "unknown"),
        })
    return {
        "status": "complete",
        "warnings": ["Bảng biến thiên biểu diễn theo một chu kỳ, với k ∈ Z."],
        "nodes": list(nodes_by_key.values()),
        "segments": table_segments,
    }


def _build_variation_table_v2(f_expr, fp_expr, domain_info: FunctionDomain, cps: list[dict], result: dict[str, Any]) -> dict[str, Any]:
    periodic_table = _periodic_variation_table_v2(result)
    if periodic_table is not None:
        return periodic_table
    warnings: list[str] = []
    components = list(domain_info.components)
    if not components:
        return {"status": "unknown", "warnings": ["Chưa phân rã được tập xác định thành các miền liên thông."], "nodes": [], "segments": []}

    vertical_map = {item.get("x"): item for item in result.get("vertical_asymptotes", [])}
    critical_by_x = {item.get("x_exact") or item.get("x"): item for item in cps}
    holes_by_x = {item.get("x_exact") or item.get("x"): item for item in result.get("removable_holes", [])}
    nodes_by_key: dict[str, dict[str, Any]] = {}
    segments: list[dict[str, Any]] = []

    sign_sets = _derivative_sign_sets(fp_expr, domain_info)
    if sign_sets["verification"] == "unknown":
        warnings.append("Chưa chứng minh được dấu đạo hàm trên toàn bộ miền; một số khoảng được đánh dấu chưa xác định.")

    def add_node(node: dict[str, Any]) -> None:
        key = node["x_exact"] or node["x"]
        existing = nodes_by_key.get(key)
        if existing is None or _node_priority(node["kind"]) >= _node_priority(existing["kind"]):
            merged = {**(existing or {}), **node}
            if existing and existing.get("left_limit") and not merged.get("left_limit"):
                merged["left_limit"] = existing["left_limit"]
            if existing and existing.get("right_limit") and not merged.get("right_limit"):
                merged["right_limit"] = existing["right_limit"]
            nodes_by_key[key] = merged

    for component in components:
        split_points = _component_split_points(component, critical_by_x, vertical_map, holes_by_x)
        ordered = [component.start, *split_points, component.end]
        for index, point in enumerate(ordered):
            add_node(_variation_node_for_point(f_expr, point, component, index, len(ordered), critical_by_x, vertical_map, holes_by_x))
        for left, right in zip(ordered, ordered[1:]):
            if left == right:
                continue
            segment = _variation_segment(fp_expr, left, right, sign_sets)
            segments.append(segment)
            if segment["direction"] == "unknown":
                warnings.append(f"Chưa xác định được chiều biến thiên trên ({segment['left']}; {segment['right']}).")

    nodes = sorted(nodes_by_key.values(), key=lambda node: _variation_order_key(node.get("x_exact") or node["x"]))
    status = "complete" if not warnings else "partial"
    return {"status": status, "warnings": _unique_texts(warnings), "nodes": nodes, "segments": segments}


def _node_priority(kind: str) -> int:
    return {"boundary": 1, "critical": 2, "min": 3, "max": 3, "hole": 4, "asymptote": 5}.get(kind, 0)


def _component_split_points(component, critical_by_x: dict[str, dict], vertical_map: dict[str, dict], holes_by_x: dict[str, dict]) -> list[Any]:
    points: list[Any] = []
    for data in list(critical_by_x.values()) + list(vertical_map.values()) + list(holes_by_x.values()):
        raw = data.get("x_exact") or data.get("x")
        try:
            point = sp.sympify(raw)
        except (TypeError, ValueError, AttributeError, sp.SympifyError):
            continue
        try:
            if point == component.start or point == component.end:
                continue
            if component.contains(point) is sp.S.true:
                points.append(point)
        except (TypeError, ValueError, AttributeError, NotImplementedError):
            continue
    return sorted(set(points), key=default_sort_key)


def _variation_node_for_point(
    f_expr,
    point,
    component,
    index: int,
    total: int,
    critical_by_x: dict[str, dict],
    vertical_map: dict[str, dict],
    holes_by_x: dict[str, dict],
) -> dict[str, Any]:
    key = _fmt_sym(point)
    if key in vertical_map:
        data = vertical_map[key]
        node = {
            "kind": "asymptote",
            "x": data.get("x", key),
            "x_exact": key,
            "label": "tiệm cận đứng",
        }
        if index > 0:
            node["left_limit"] = _limit_from_text(data.get("lim_left"))
        if index < total - 1:
            node["right_limit"] = _limit_from_text(data.get("lim_right"))
        return node
    if key in holes_by_x:
        data = holes_by_x[key]
        return {
            "kind": "hole",
            "x": data.get("x", key),
            "x_exact": key,
            "y": data.get("y"),
            "y_exact": data.get("y_exact") or data.get("y"),
            "label": data.get("label", "điểm khuyết"),
        }
    if key in critical_by_x:
        data = critical_by_x[key]
        return {
            "kind": data.get("kind", "critical"),
            "x": data.get("x", key),
            "x_exact": key,
            "y": data.get("y"),
            "y_exact": data.get("y") or data.get("y_exact"),
            "label": data.get("kind_label"),
        }

    node: dict[str, Any] = {
        "kind": "boundary",
        "x": _fmt_boundary(point),
        "x_exact": key,
        "label": "biên miền",
        "open": bool(component.left_open if index == 0 else component.right_open),
    }
    if index == 0:
        node["right_limit"] = _limit_payload(f_expr, point, "+")
    if index == total - 1:
        node["left_limit"] = _limit_payload(f_expr, point, "-")
    return node


def _derivative_sign_sets(fp_expr, domain_info: FunctionDomain) -> dict[str, Any]:
    if fp_expr is None:
        return {"verification": "unknown", "positive": S.EmptySet, "negative": S.EmptySet, "zero": S.EmptySet}
    try:
        if simplify(fp_expr) == 0:
            return {"verification": "exact", "positive": S.EmptySet, "negative": S.EmptySet, "zero": domain_info.set or S.Reals}
        positive = intersect_domain(sp.solveset(fp_expr > 0, x, domain=S.Reals), domain_info)
        negative = intersect_domain(sp.solveset(fp_expr < 0, x, domain=S.Reals), domain_info)
        zero = intersect_domain(sp.solveset(fp_expr, x, domain=S.Reals), domain_info)
        if positive.has(sp.ConditionSet) or negative.has(sp.ConditionSet):
            raise NotImplementedError
        return {"verification": "exact", "positive": positive, "negative": negative, "zero": zero}
    except (NotImplementedError, TypeError, ValueError, AttributeError):
        return {"verification": "unknown", "positive": S.EmptySet, "negative": S.EmptySet, "zero": S.EmptySet}


def _variation_segment(fp_expr, left, right, sign_sets: dict[str, Any]) -> dict[str, Any]:
    mid = _segment_probe(left, right)
    direction = "unknown"
    derivative_sign = "unknown"
    verification = sign_sets["verification"]
    if mid is not None and verification == "exact":
        if _set_contains(sign_sets["positive"], mid):
            direction = "increasing"
            derivative_sign = "+"
        elif _set_contains(sign_sets["negative"], mid):
            direction = "decreasing"
            derivative_sign = "-"
        elif sign_sets["zero"] != S.EmptySet and _set_contains(sign_sets["zero"], mid):
            direction = "constant"
            derivative_sign = "0"
    if direction == "unknown" and fp_expr is not None and mid is not None:
        try:
            val = float(fp_expr.subs(x, mid).evalf())
            if isfinite(val) and abs(val) >= 1e-12:
                direction = "increasing" if val > 0 else "decreasing"
                derivative_sign = "+" if val > 0 else "-"
                verification = "sampled"
        except Exception:
            pass
    if direction == "unknown":
        verification = "unknown"
    return {"left": _fmt_boundary(left), "right": _fmt_boundary(right), "direction": direction, "verification": verification, "derivative_sign": derivative_sign}


def _segment_probe(left, right):
    try:
        if left == -oo and right == oo:
            return S.Zero
        if left == -oo:
            return right - 1
        if right == oo:
            return left + 1
        return (left + right) / 2
    except (TypeError, ValueError, AttributeError):
        return None


def _set_contains(value_set, point) -> bool:
    try:
        membership = value_set.contains(point)
        return membership is sp.S.true or sp.simplify(membership) is sp.S.true
    except (TypeError, ValueError, AttributeError, NotImplementedError):
        return False


def _limit_payload(f_expr, point, direction: str) -> dict[str, str | None]:
    try:
        if point == -oo:
            value = limit(f_expr, x, -oo)
        elif point == oo:
            value = limit(f_expr, x, oo)
        else:
            value = limit(f_expr, x, point, dir=direction)
    except Exception:
        return {"value": None, "status": "unknown"}
    return _limit_from_value(value)


def _limit_from_text(value: str | None) -> dict[str, str | None]:
    if value is None:
        return {"value": None, "status": "unknown"}
    if value in {"+∞", "∞", "oo"}:
        return {"value": "+∞", "status": "infinite"}
    if value in {"-∞", "-oo"}:
        return {"value": "-∞", "status": "infinite"}
    return {"value": value, "status": "finite"}


def _limit_from_value(value) -> dict[str, str | None]:
    if value == oo:
        return {"value": "+∞", "status": "infinite"}
    if value == -oo:
        return {"value": "-∞", "status": "infinite"}
    if value in (zoo, nan, S.NaN) or str(value).startswith("AccumBounds"):
        return {"value": None, "status": "dne"}
    try:
        simplified = simplify(value)
    except Exception:
        simplified = value
    return {"value": _fmt_sym(simplified), "status": "finite"}


def _fmt_boundary(value) -> str:
    if value == -oo:
        return "-∞"
    if value == oo:
        return "+∞"
    return _fmt_sym(value)


def _variation_order_key(value: str):
    if value in {"-∞", "-oo"}:
        return (0, 0.0)
    if value in {"+∞", "∞", "oo"}:
        return (2, 0.0)
    try:
        return (1, float(sp.N(sp.sympify(value))))
    except (TypeError, ValueError, AttributeError, sp.SympifyError):
        return (1, 0.0)


def _unique_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_variation_table(result: dict, cps: list[dict]) -> list[dict]:
    rows: list[dict] = []
    markers: list[dict[str, Any]] = []
    for cp in cps:
        if _is_numeric(cp.get("x", "")):
            markers.append({"x": cp["x"], "y": cp.get("y"), "kind": cp["kind"], "order": float(cp["x"])})
    for va in result.get("vertical_asymptotes", []):
        if _is_numeric(va.get("x", "")):
            markers.append({"x": va["x"], "y": None, "kind": "asymptote", "order": float(va["x"])})
    markers.sort(key=lambda item: item["order"])

    all_x = [{"x": "-∞", "y": None, "kind": "boundary"}] + markers + [{"x": "+∞", "y": None, "kind": "boundary"}]

    for i, pt in enumerate(all_x):
        row: dict[str, Any] = {
            "x": pt["x"],
            "y": pt["y"],
            "kind": pt["kind"],
        }
        if i < len(all_x) - 1:
            row["arrow_to_next"] = _arrow_between(pt["x"], all_x[i + 1]["x"], result.get("intervals_increasing", []), result.get("intervals_decreasing", []))
        rows.append(row)

    return rows


def _arrow_between(lo: str, hi: str, inc: list[str], dec: list[str]) -> str:
    try:
        lo_f = -1e10 if lo in ("-∞", "-inf") else float(lo)
        hi_f = 1e10 if hi in ("+∞", "+inf", "∞") else float(hi)
        mid = (lo_f + hi_f) / 2
        for interval in inc:
            bounds = _parse_interval(interval)
            if bounds and bounds[0] <= mid <= bounds[1]:
                return "↗"
        for interval in dec:
            bounds = _parse_interval(interval)
            if bounds and bounds[0] <= mid <= bounds[1]:
                return "↘"
    except Exception:
        pass
    return "→"


def _parse_interval(s: str) -> tuple[float, float] | None:
    m = re.findall(r"[-+]?\d*\.?\d+|[+-]?∞|[+-]?inf", s, re.IGNORECASE)
    if len(m) < 2:
        return None

    def to_f(v: str) -> float:
        if "∞" in v or "inf" in v.lower():
            return -1e10 if "-" in v else 1e10
        return float(v)

    return to_f(m[0]), to_f(m[1])


def _bound_label(val: float) -> str:
    if val <= -1e8:
        return "-∞"
    if val >= 1e8:
        return "+∞"
    s = f"{val:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def _is_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def _fmt_lim(val) -> str:
    if val == oo:
        return "+∞"
    if val == -oo:
        return "-∞"
    try:
        return _fmt_num(float(val.evalf()))
    except Exception:
        return str(val)


def _classify_stationary_point(fp_simplified, cp, fpp_simplified=None) -> tuple[str, str]:
    """
    Phân loại điểm dừng bằng phương pháp giải tích chính xác.
    """
    # 1. Analytical: Evaluate limits exactly
    try:
        left_lim = sp.limit(fp_simplified, x, cp, dir='-')
        right_lim = sp.limit(fp_simplified, x, cp, dir='+')
        
        if left_lim.is_real and right_lim.is_real:
            left_sign = 1 if left_lim > 0 else (-1 if left_lim < 0 else None)
            right_sign = 1 if right_lim > 0 else (-1 if right_lim < 0 else None)
            
            if left_sign is not None and right_sign is not None:
                if left_sign < 0 < right_sign:
                    return "min", "CT"
                if left_sign > 0 > right_sign:
                    return "max", "CĐ"
                if left_sign == right_sign:
                    return "unknown", "Điểm dừng"
    except Exception:
        pass

    # 2. Fallback f''(cp)
    if fpp_simplified is not None:
        try:
            fpp_val = float(fpp_simplified.subs(x, cp).evalf())
            if isfinite(fpp_val):
                if fpp_val > 1e-10:
                    return "min", "CT"
                if fpp_val < -1e-10:
                    return "max", "CĐ"
        except Exception:
            pass

    # 3. Fallback sampling
    try:
        cp_f = float(cp.evalf())
        left_sign, right_sign = _sample_derivative_signs(fp_simplified, cp_f)
        if left_sign is not None and right_sign is not None:
            if left_sign < 0 < right_sign:
                return "min", "CT"
            if left_sign > 0 > right_sign:
                return "max", "CĐ"
            if left_sign == right_sign:
                return "unknown", "Điểm dừng"
    except Exception:
        pass

    return "unknown", "Điểm dừng"


def _sample_derivative_signs(fp_simplified, cp_f: float) -> tuple[int | None, int | None]:
    """
    Lấy dấu f'(x0-eps), f'(x0+eps) với nhiều eps để tăng độ bền.
    Trả về -1/1 hoặc None nếu không xác định được.
    """
    for eps in (1e-3, 1e-4, 1e-2, 1e-5):
        left = _safe_derivative_sign(fp_simplified, cp_f - eps)
        right = _safe_derivative_sign(fp_simplified, cp_f + eps)
        if left is not None and right is not None:
            return left, right
    return None, None


def _safe_derivative_sign(fp_simplified, x_val: float) -> int | None:
    try:
        val = float(fp_simplified.subs(x, x_val).evalf())
    except Exception:
        return None
    if not isfinite(val) or abs(val) < 1e-12:
        return None
    return 1 if val > 0 else -1


def _collect_stationary_candidates(f_expr, fp_expr, domain_info: FunctionDomain | None = None) -> list:
    """
    Gom ứng viên điểm tới hạn:
    1) nghiệm f'(x)=0
    2) điểm làm f'(x) không xác định nhưng f(x) vẫn xác định
    """
    candidates: list = []

    # (1) Nghiệm f'(x)=0
    try:
        candidates.extend(solve(fp_expr, x, dict=False))
    except Exception:
        pass

    # (2) Điểm singular của f'(x)
    try:
        singular_set = singularities(fp_expr, x)
        if hasattr(singular_set, "__iter__"):
            candidates.extend(list(singular_set))
    except Exception:
        pass

    # Backup: nghiệm mẫu số của f'(x) sau khi rút gọn
    try:
        _, denom_expr = fraction(cancel(fp_expr))
        candidates.extend(solve(denom_expr, x, dict=False))
    except Exception:
        pass

    unique: list = []
    seen = set()
    for cp in candidates:
        try:
            cp_s = simplify(cp)
            key = str(cp_s)
            if key in seen:
                continue
            if not in_domain(domain_info, cp_s):
                continue
            # Chỉ giữ điểm mà hàm gốc f(x) xác định hữu hạn
            f_at_cp = f_expr.subs(x, cp_s).evalf()
            if f_at_cp in (oo, -oo, zoo, nan, S.NaN):
                continue
            float(cp_s.evalf())  # đảm bảo lấy được giá trị thực để xét dấu
            seen.add(key)
            unique.append(cp_s)
        except Exception:
            continue

    return unique
