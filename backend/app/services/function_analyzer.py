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

from app.services.safe_math_parser import SafeMathComplexityError, SafeMathParseError, SafeMathParseResult, parse_safe_math_expression


x = Symbol("x", real=True)
m = Symbol("m", real=True)

_PARAMETER_RANGES = {"m": {"min": -10.0, "max": 10.0, "step": 0.1}}
_CLEAN_RE = re.compile(r"\s+")


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


def _parameter_value(parameters: Mapping[str, float] | None, name: str) -> float:
    raw = 1.0 if parameters is None else parameters.get(name, 1.0)
    try:
        value = float(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Tham số {name} không hợp lệ.") from e
    if not isfinite(value):
        raise ValueError(f"Tham số {name} phải là số hữu hạn.")
    config = _PARAMETER_RANGES[name]
    return min(max(value, config["min"]), config["max"])


def analyze_function(
    expression: str,
    parameters: Mapping[str, float] | None = None,
    *,
    interval: Mapping[str, float] | None = None,
    line: Mapping[str, float] | None = None,
    parameter_conditions: Mapping[str, Any] | None = None,
    transform: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []

    try:
        parse_result = _parse_expr(expression)
        parsed = parse_result.expr
    except ValueError as e:
        code = getattr(e.__cause__, "code", "ANALYZER_PARSE_FAILED")
        return {"error": str(e), "error_code": code, "warnings": [str(e)]}

    detected_parameters = ["m"] if m in parsed.free_symbols else []
    active_parameters: dict[str, float] = {}
    f = parsed
    if "m" in detected_parameters:
        try:
            m_value = _parameter_value(parameters, "m")
        except ValueError as e:
            return {"error": str(e), "warnings": [str(e)]}
        active_parameters["m"] = m_value
        f = f.subs(m, m_value)
        warnings.append(f"Kết quả khảo sát tại m = {_fmt_num(m_value)}.")

    result: dict[str, Any] = {
        "expression": expression,
        "expression_latex": latex(parsed),
        "evaluated_expression": _fmt_sym(f),
        "evaluated_expression_latex": latex(f),
        "analysis_mode": "numeric_substituted" if detected_parameters else "symbolic",
        "parameters": {
            "detected": detected_parameters,
            "active": active_parameters,
            "ranges": {name: dict(config) for name, config in _PARAMETER_RANGES.items() if name in detected_parameters},
        },
        "complexity_score": parse_result.complexity_score,
        "_parsed_expr": parsed,
        "_evaluated_expr": f,
    }

    try:
        dom = continuous_domain(f, x, S.Reals)
        result["domain"] = str(dom)
        result["domain_latex"] = latex(dom)
    except Exception as e:
        warnings.append(f"Không tính được tập xác định: {e}")
        result["domain"] = None
        result["domain_latex"] = None

    try:
        rng = function_range(f, x, S.Reals)
        result["range"] = str(rng)
        result["range_latex"] = latex(rng)
    except Exception as e:
        warnings.append(f"Không tính được tập giá trị: {e}")
        result["range"] = None
        result["range_latex"] = None

    try:
        f_neg = simplify(f.subs(x, -x))
        if simplify(f_neg - f) == 0:
            result["parity"] = "even"
        elif simplify(f_neg + f) == 0:
            result["parity"] = "odd"
        else:
            result["parity"] = "neither"
    except Exception:
        result["parity"] = "neither"

    try:
        fp = diff(f, x)
        fp_simplified = simplify(fp)
        result["derivative"] = _fmt_sym(fp_simplified)
        result["derivative_latex"] = latex(fp_simplified)
    except Exception as e:
        warnings.append(f"Không tính được đạo hàm: {e}")
        fp_simplified = None
        result["derivative"] = None
        result["derivative_latex"] = None

    fpp_simplified = None
    if fp_simplified is not None:
        try:
            fpp_simplified = simplify(diff(fp_simplified, x))
            result["second_derivative"] = _fmt_sym(fpp_simplified)
            result["second_derivative_latex"] = latex(fpp_simplified)
        except Exception as e:
            warnings.append(f"Không tính được đạo hàm cấp 2: {e}")
    result.setdefault("second_derivative", None)
    result.setdefault("second_derivative_latex", None)

    critical_points: list[dict[str, Any]] = []
    if fp_simplified is not None:
        try:
            for cp in _collect_stationary_candidates(f, fp_simplified):
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
                    y_val = float(f.subs(x, cp).evalf())
                except Exception:
                    y_val = None

                critical_points.append({
                    "x": _fmt_num(cp_float),
                    "x_exact": _fmt_sym(cp),
                    "y": _fmt_num(y_val) if y_val is not None else None,
                    "kind": kind,
                    "kind_label": kind_label,
                })
        except Exception as e:
            warnings.append(f"Không giải được f'(x) = 0: {e}")

    result["critical_points"] = critical_points

    inflection_pts: list[dict[str, str]] = []
    concavity_breakpoints: list[float] = []
    if fpp_simplified is not None:
        try:
            for z in _solve_real_roots(fpp_simplified):
                try:
                    z_f = float(z.evalf())
                    left = float(fpp_simplified.subs(x, z - Rational(1, 1000)).evalf())
                    right = float(fpp_simplified.subs(x, z + Rational(1, 1000)).evalf())
                except Exception:
                    continue
                if left * right < 0:
                    try:
                        y_val = float(f.subs(x, z).evalf())
                    except Exception:
                        continue
                    inflection_pts.append({"x": _fmt_num(z_f), "x_exact": _fmt_sym(z), "y": _fmt_num(y_val)})
                    concavity_breakpoints.append(z_f)
        except Exception as e:
            warnings.append(f"Không tính được điểm uốn: {e}")
    result["inflection_points"] = inflection_pts
    if fpp_simplified is not None and concavity_breakpoints:
        result["concave_up_intervals"], result["concave_down_intervals"] = _sign_intervals(fpp_simplified, sorted(concavity_breakpoints))
    else:
        result["concave_up_intervals"] = []
        result["concave_down_intervals"] = []

    ha: list[dict] = []
    try:
        lim_pos = limit(f, x, oo)
        lim_neg = limit(f, x, -oo)
        if lim_pos not in (oo, -oo, zoo, nan, S.NaN):
            ha.append({"direction": "+∞", "value": _fmt_num(lim_pos)})
        if lim_neg not in (oo, -oo, zoo, nan, S.NaN) and lim_neg != lim_pos:
            ha.append({"direction": "-∞", "value": _fmt_num(lim_neg)})
    except Exception as e:
        warnings.append(f"Không tính được tiệm cận ngang: {e}")
    result["horizontal_asymptotes"] = ha

    va: list[dict] = []
    try:
        _, denom_expr = fraction(cancel(f))
        for z in solve(denom_expr, x):
            try:
                z_f = float(z.evalf())
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
    except Exception as e:
        warnings.append(f"Không tính được tiệm cận đứng: {e}")
    result["vertical_asymptotes"] = va

    if fp_simplified is not None:
        mono_breakpoints = [float(cp["x"]) for cp in critical_points if _is_numeric(cp.get("x", ""))]
        mono_breakpoints.extend(float(item["x"]) for item in va if _is_numeric(item.get("x", "")))
        bps = sorted(set(mono_breakpoints))
        result["intervals_increasing"], result["intervals_decreasing"] = _sign_intervals(fp_simplified, bps)
    else:
        result["intervals_increasing"] = []
        result["intervals_decreasing"] = []

    oblique = None
    try:
        a_coef = limit(f / x, x, oo)
        if a_coef not in (oo, -oo, zoo, nan, S.NaN, S.Zero):
            b_coef = limit(f - a_coef * x, x, oo)
            if b_coef not in (oo, -oo, zoo, nan, S.NaN):
                oblique = f"y = {_fmt_num(a_coef)}x + {_fmt_num(b_coef)}"
    except Exception:
        pass
    result["oblique_asymptote"] = oblique

    x_intercepts: list[str] = []
    seen_intercepts: set[str] = set()
    seen_roots_float: list[float] = []
    root_eps = 1e-5
    try:
        for z in solve(f, x)[:6]:
            try:
                val = float(z.evalf())
            except Exception:
                item = _fmt_sym(z)
                if item in seen_intercepts:
                    continue
                seen_intercepts.add(item)
                x_intercepts.append(item)
                continue
            scale = max(1.0, abs(val))
            if any(abs(val - prev) <= root_eps * scale for prev in seen_roots_float):
                continue
            seen_roots_float.append(val)
            item = _fmt_num(val)
            if item in seen_intercepts:
                continue
            seen_intercepts.add(item)
            x_intercepts.append(item)
    except Exception:
        pass
    result["x_intercepts"] = x_intercepts

    y_intercept = None
    try:
        y0 = float(f.subs(x, 0).evalf())
        y_intercept = _fmt_num(y0)
    except Exception:
        pass
    result["y_intercept"] = y_intercept

    if interval:
        try:
            result["interval_analysis"] = _analyze_interval(f, fp_simplified, interval)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không tính được GTLN/GTNN trên đoạn: {e}")

    if line:
        try:
            result["line_analysis"] = _analyze_line_position(f, line)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không xét được tương giao với đường thẳng: {e}")

    if parameter_conditions:
        result["parameter_conditions"] = _solve_parameter_conditions(parsed, parameter_conditions)

    if transform:
        try:
            result["transform_preview"] = _build_transform_preview(f, transform)
        except ValueError as e:
            warnings.append(str(e))
        except Exception as e:
            warnings.append(f"Không dựng được biến đổi đồ thị: {e}")

    result["variation_table"] = _build_variation_table(result, critical_points)
    result["capabilities"] = {"trig_periodic": True, "exact_solving": True, "numeric_fallback": True}
    result["warnings"] = warnings

    return result


def _analyze_interval(f_expr, fp_expr, interval: Mapping[str, Any]) -> dict[str, Any]:
    a = _finite_float(interval.get("a", -10), "a")
    b = _finite_float(interval.get("b", 10), "b")
    open_a = bool(interval.get("open_a", False))
    open_b = bool(interval.get("open_b", False))
    if a >= b:
        raise ValueError("Đoạn khảo sát không hợp lệ: cần a < b.")

    candidates = []
    
    if open_a:
        limit_a = limit(f_expr, x, a, dir='+')
        y_a = None if limit_a in [oo, -oo, zoo, nan] else float(limit_a)
        candidates.append({"x": a, "x_exact": _fmt_num(a), "y": y_a, "kind": "limit", "label": f"lim(x->{_fmt_num(a)}+)"})
    else:
        candidates.append({"x": a, "x_exact": _fmt_num(a), "y": _eval_float(f_expr, a), "kind": "endpoint", "label": f"f({_fmt_num(a)})"})

    if open_b:
        limit_b = limit(f_expr, x, b, dir='-')
        y_b = None if limit_b in [oo, -oo, zoo, nan] else float(limit_b)
        candidates.append({"x": b, "x_exact": _fmt_num(b), "y": y_b, "kind": "limit", "label": f"lim(x->{_fmt_num(b)}-)"})
    else:
        candidates.append({"x": b, "x_exact": _fmt_num(b), "y": _eval_float(f_expr, b), "kind": "endpoint", "label": f"f({_fmt_num(b)})"})

    extrema_inside = []
    if fp_expr is not None:
        for cp in _collect_stationary_candidates(f_expr, fp_expr):
            try:
                cp_float = float(cp.evalf())
            except Exception:
                continue
            if not a < cp_float < b:
                continue
            y_val = _eval_float(f_expr, cp_float)
            point = {"x": _fmt_num(cp_float), "x_exact": _fmt_sym(cp), "y": _fmt_num(y_val), "kind": "critical", "label": "Cực trị trong khoảng"}
            extrema_inside.append(point)
            candidates.append({"x": cp_float, "x_exact": _fmt_sym(cp), "y": y_val, "kind": "critical", "label": "Cực trị"})

    finite = [item for item in candidates if item["y"] is not None and isfinite(item["y"])]
    if not finite:
        raise ValueError(f"Không tính được giá trị hữu hạn trên {'khoảng' if open_a or open_b else 'đoạn'}.")
    
    max_item = max(finite, key=lambda item: item["y"])
    min_item = min(finite, key=lambda item: item["y"])

    conclusion = []
    if max_item["kind"] == "limit":
        conclusion.append(f"Hàm số không có GTLN, Supremum (cận trên đúng) = {_fmt_num(max_item['y'])} khi x tiến về {_fmt_num(max_item['x'])}")
    else:
        conclusion.append(f"GTLN = {_fmt_num(max_item['y'])} tại x = {_fmt_num(max_item['x'])}")

    if min_item["kind"] == "limit":
        conclusion.append(f"Hàm số không có GTNN, Infimum (cận dưới đúng) = {_fmt_num(min_item['y'])} khi x tiến về {_fmt_num(min_item['x'])}")
    else:
        conclusion.append(f"GTNN = {_fmt_num(min_item['y'])} tại x = {_fmt_num(min_item['x'])}")

    return {
        "a": _fmt_num(a), "b": _fmt_num(b), "open_a": open_a, "open_b": open_b,
        "fa": _fmt_num(candidates[0]["y"]) if candidates[0]["y"] is not None else "oo",
        "fb": _fmt_num(candidates[1]["y"]) if candidates[1]["y"] is not None else "oo",
        "extrema_inside": extrema_inside,
        "max_point": _point_result(max_item),
        "min_point": _point_result(min_item),
        "conclusion": "; ".join(conclusion) + ".",
    }


def _analyze_line_position(f_expr, line: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(line.get("mode", "intersect"))
    
    if mode == "tangent_at":
        x0 = _finite_float(line.get("x0", 0), "x0")
        y0 = _eval_float(f_expr, x0)
        try:
            fp_expr = diff(f_expr, x)
            k = _eval_float(fp_expr, x0)
            b_val = y0 - k * x0
        except Exception as e:
            raise ValueError(f"Không thể tính đạo hàm tại x0={x0}")
        equation = f"y = {_fmt_num(k)}(x - {_fmt_num(x0)}) + {_fmt_num(y0)}" if x0 >= 0 else f"y = {_fmt_num(k)}(x + {_fmt_num(-x0)}) + {_fmt_num(y0)}"
        return {
            "mode": "tangent_at",
            "x0": _fmt_num(x0), "y0": _fmt_num(y0),
            "k": _fmt_num(k), "b": _fmt_num(b_val),
            "equation": equation,
            "conclusion": f"Tiếp tuyến tại điểm ({_fmt_num(x0)}, {_fmt_num(y0)}) là: {equation}"
        }

    k = _finite_float(line.get("k", 0), "k")
    b_val = _finite_float(line.get("b", 0), "b")
    line_expr = k * x + b_val
    diff_expr = simplify(f_expr - line_expr)
    intersections: list[dict[str, str]] = []
    
    roots = _solve_real_roots(diff_expr)[:12]
    if not roots:
        roots = _numeric_roots(diff_expr)
    for root in roots:
        try:
            root_f = float(root.evalf() if hasattr(root, "evalf") else root)
            if not isfinite(root_f):
                continue
            y_val = k * root_f + b_val
            intersections.append({"x": _fmt_num(root_f), "y": _fmt_num(y_val), "x_exact": _fmt_sym(root)})
        except Exception:
            continue
    
    split = sorted({float(item["x"]) for item in intersections if _is_numeric(item["x"])})
    above, below = _sign_intervals(diff_expr, split)
    
    area_text = None
    if len(split) >= 2:
        try:
            from sympy import Integral
            a_root, b_root = split[0], split[-1]
            area_val = abs(float(Integral(Abs(diff_expr), (x, a_root, b_root)).evalf()))
            area_text = _fmt_num(area_val)
        except Exception:
            pass

    return {
        "mode": "intersect",
        "k": _fmt_num(k),
        "b": _fmt_num(b_val),
        "equation": f"y = {_fmt_num(k)}x + {_fmt_num(b_val)}",
        "intersection_count": len(intersections),
        "intersections": intersections,
        "relative_intervals": {"above": above, "below": below},
        "area_between_curves": area_text,
    }


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
    return {
        "type": transform_type,
        "value": _fmt_num(value),
        "label": label,
        "expression": _fmt_sym(transformed),
        "expression_latex": latex(transformed),
        "pedagogical_steps": steps
    }


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


def _sign_intervals(expr, breakpoints: list[float]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    bounds = [-1e9] + breakpoints + [1e9]
    
    # 1. Analytical try
    try:
        pos_set = sp.solveset(expr > 0, x, domain=sp.S.Reals)
        neg_set = sp.solveset(expr < 0, x, domain=sp.S.Reals)
        
        if not pos_set.has(sp.ConditionSet) and not neg_set.has(sp.ConditionSet):
            def format_set(s):
                res = []
                args = s.args if isinstance(s, sp.Union) else [s]
                for arg in args:
                    if isinstance(arg, sp.Interval):
                        a_str = _bound_label(float(arg.start)) if arg.start.is_finite else ("-∞" if arg.start == -sp.oo else "+∞")
                        b_str = _bound_label(float(arg.end)) if arg.end.is_finite else ("-∞" if arg.end == -sp.oo else "+∞")
                        res.append(f"({a_str}; {b_str})")
                return res
            
            positive = format_set(pos_set)
            negative = format_set(neg_set)
            if positive or negative:
                return positive, negative
    except Exception:
        pass

    # 2. Fallback numeric sampling
    positive = []
    negative = []
    for i in range(len(bounds) - 1):
        mid = (bounds[i] + bounds[i + 1]) / 2
        try:
            sign = float(expr.subs(x, mid).evalf())
            interval_str = f"({_bound_label(bounds[i])}; {_bound_label(bounds[i + 1])})"
            if sign > 0:
                positive.append(interval_str)
            elif sign < 0:
                negative.append(interval_str)
        except Exception:
            pass
    return positive, negative


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


def _collect_stationary_candidates(f_expr, fp_expr) -> list:
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
