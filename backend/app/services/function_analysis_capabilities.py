from __future__ import annotations

from math import isfinite
from typing import Any

import sympy as sp

from app.services.safe_math_parser import safe_math_parser_registry


REGISTRY_VERSION = "function-analyzer-capabilities-v2"

_EXAMPLES = (
    {"category": "Đa thức", "label": "Bậc hai", "expression": "x^2 - 4*x + 3", "latex": "x^2-4x+3"},
    {"category": "Đa thức", "label": "Bậc ba", "expression": "x^3 - 3*x + 2", "latex": "x^3-3x+2"},
    {"category": "Phân thức và căn", "label": "Phân thức", "expression": "(x^2 - 1)/(x - 2)", "latex": "\\frac{x^2-1}{x-2}"},
    {"category": "Phân thức và căn", "label": "Căn", "expression": "sqrt(x^2 + 1)", "latex": "\\sqrt{x^2+1}"},
    {"category": "Mũ và logarit", "label": "Mũ", "expression": "exp(x)", "latex": "e^x"},
    {"category": "Mũ và logarit", "label": "Logarit", "expression": "log(x)", "latex": "\\ln(x)"},
    {"category": "Lượng giác", "label": "Sin", "expression": "sin(x)", "latex": "\\sin(x)"},
    {"category": "Lượng giác", "label": "Tan", "expression": "tan(x)", "latex": "\\tan(x)"},
    {"category": "Từng đoạn", "label": "Piecewise", "expression": "Piecewise((x^2, x<0), (x, x>=0))", "latex": "\\begin{cases}x^2,&x<0\\\\x,&x\\ge0\\end{cases}"},
    {"category": "Tham số", "label": "Tham số m", "expression": "x^2 + m*x + 1", "latex": "x^2+mx+1"},
)


def analyzer_capability_registry() -> dict[str, Any]:
    parser = safe_math_parser_registry()
    return {
        "version": REGISTRY_VERSION,
        "parser": parser,
        "derivative": {
            "supported": True,
            "limitations": [
                "Điểm không khả vi của abs và Piecewise được báo riêng; không suy ra tiếp tuyến khi chưa chứng minh khả vi.",
                "Biểu thức vượt giới hạn parser hoặc timeout có thể trả partial/unknown.",
            ],
        },
        "piecewise_conditions": {
            "operators": ["<", "<=", ">", ">=", "=="],
            "variables": list(parser["variables"]),
            "ordered_branches": True,
            "max_branches": parser["limits"]["max_piecewise_branches"],
        },
        "parameters": {
            "supported": ["m"],
            "modes": ["symbolic", "substitute"],
            "ranges": {"m": {"min": -10.0, "max": 10.0, "step": 0.1}},
        },
        "tools": ["interval", "line", "tangent", "transform", "parameter_conditions"],
        "renderers": ["geogebra", "svg"],
        "examples": list(_EXAMPLES),
    }


def expression_capabilities(expr: sp.Expr, result: dict[str, Any]) -> dict[str, Any]:
    root_data = result.get("x_intercepts_v2") or {}
    graph_data = result.get("graph_analysis_v2") or {}
    periodicity = result.get("periodicity") or {}
    parameters = sorted(str(symbol) for symbol in expr.free_symbols if str(symbol) != "x")
    has_piecewise = bool(expr.has(sp.Piecewise))
    derivative_available = result.get("derivative") is not None
    return {
        "registry_version": REGISTRY_VERSION,
        "expression": {
            "piecewise": has_piecewise,
            "parameters": parameters,
            "parameter_mode": result.get("parameter_mode") or result.get("analysis_mode"),
        },
        "exactness": {
            "domain": "exact" if result.get("domain") is not None else "unknown",
            "range": "exact" if result.get("range") is not None else "unknown",
            "roots": _status_capability(root_data.get("status"), root_data.get("method")),
            "periodicity": _status_capability(periodicity.get("status"), periodicity.get("method")),
        },
        "completeness": {
            "roots": root_data.get("status", "unknown"),
            "graph": graph_data.get("status", "unknown"),
            "truncated": bool(root_data.get("truncated") or graph_data.get("truncated")),
        },
        "numeric_fallback": {
            "available": True,
            "used": root_data.get("method") == "numeric_adaptive" or graph_data.get("method") not in (None, "symbolic"),
        },
        "renderer": {
            "geogebra": bool(result.get("geogebra_commands")),
            "svg": bool(graph_data.get("segments") or result.get("graph_points")),
        },
        "tools": {
            "interval": result.get("domain") is not None,
            "line": result.get("domain") is not None,
            "tangent": derivative_available,
            "transform": not parameters or result.get("analysis_mode") == "numeric_substituted",
            "parameter_conditions": parameters == ["m"],
        },
        "limitations": (["Piecewise có thể làm một số phép đạo hàm hoặc giải nghiệm trả partial/unknown."] if has_piecewise else []),
    }


def exact_approx_value(value: Any, *, method: str, precision: int = 12) -> dict[str, Any]:
    exact = sp.simplify(value)
    approximation: float | None = None
    try:
        candidate = float(sp.N(exact, precision))
        if isfinite(candidate):
            approximation = candidate
    except (TypeError, ValueError, AttributeError):
        pass
    return {
        "exact": str(exact),
        "latex": sp.latex(exact),
        "approx": approximation,
        "precision": precision if approximation is not None else None,
        "method": method,
    }


def _status_capability(status: Any, method: Any) -> str:
    if status == "complete" and method == "symbolic_exact":
        return "exact_complete"
    if status == "complete":
        return "complete"
    if status == "partial":
        return "partial"
    return "unknown"