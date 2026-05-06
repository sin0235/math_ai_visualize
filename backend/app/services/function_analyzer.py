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

from sympy import (
    S, Symbol, oo, simplify, diff, solve, limit,
    Rational, zoo, nan, latex,
    sympify, SympifyError, fraction, cancel,
)
from sympy.calculus.util import continuous_domain, function_range
from sympy.calculus.singularities import singularities


x = Symbol("x", real=True)
m = Symbol("m", real=True)

_PARAMETER_RANGES = {"m": {"min": -10.0, "max": 10.0, "step": 0.1}}
_CLEAN_RE = re.compile(r"\s+")


def _parse_expr(expression: str):
    cleaned = (
        expression
        .replace("^", "**")
        .replace("ln", "log")
        .replace("tg", "tan")
        .replace("ctg", "cot")
    )
    try:
        expr = sympify(cleaned, locals={"x": x, "m": m})
    except (SympifyError, SyntaxError, TypeError) as e:
        raise ValueError(f"Không thể phân tích biểu thức: {expression!r}. Lỗi: {e}") from e

    unsupported = expr.free_symbols - {x, m}
    if unsupported:
        names = ", ".join(sorted(str(symbol) for symbol in unsupported))
        raise ValueError(f"Chỉ hỗ trợ biến x và tham số m trong phiên bản này. Ký hiệu chưa hỗ trợ: {names}.")
    return expr


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


def analyze_function(expression: str, parameters: Mapping[str, float] | None = None) -> dict[str, Any]:
    warnings: list[str] = []

    try:
        parsed = _parse_expr(expression)
    except ValueError as e:
        return {"error": str(e), "warnings": [str(e)]}

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

    if fp_simplified is not None and critical_points:
        cp_x_vals = sorted([float(cp["x"]) for cp in critical_points if _is_numeric(cp["x"])])
        result["intervals_increasing"], result["intervals_decreasing"] = _sign_intervals(fp_simplified, cp_x_vals)
    else:
        result["intervals_increasing"] = []
        result["intervals_decreasing"] = []

    inflection_pts: list[dict[str, str]] = []
    concavity_breakpoints: list[float] = []
    if fpp_simplified is not None:
        try:
            for z in solve(fpp_simplified, x):
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
        if mono_breakpoints:
            result["intervals_increasing"], result["intervals_decreasing"] = _sign_intervals(fp_simplified, sorted(set(mono_breakpoints)))

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
    try:
        for z in solve(f, x)[:6]:
            try:
                x_intercepts.append(_fmt_num(float(z.evalf())))
            except Exception:
                x_intercepts.append(_fmt_sym(z))
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

    result["variation_table"] = _build_variation_table(result, critical_points)
    result["warnings"] = warnings

    return result


def _sign_intervals(expr, breakpoints: list[float]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    bounds = [-1e9] + breakpoints + [1e9]
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
    Phân loại điểm dừng theo đổi dấu của f'(x) quanh cp.
    Ưu tiên tiêu chí đổi dấu (ổn định hơn cho trường hợp f''(cp)=0).
    """
    try:
        cp_f = float(cp.evalf())
    except Exception:
        return "unknown", "Điểm đặc biệt"

    left_sign, right_sign = _sample_derivative_signs(fp_simplified, cp_f)
    if left_sign is not None and right_sign is not None:
        if left_sign < 0 < right_sign:
            return "min", "CT"
        if left_sign > 0 > right_sign:
            return "max", "CĐ"
        if left_sign == right_sign:
            return "unknown", "Điểm dừng"

    # Fallback khi không lấy mẫu được dấu f' (miền xác định hẹp, biểu thức khó,...)
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
