"""Safe single-line math expression evaluator.

Dùng để eval các biểu thức toạ độ phụ thuộc tham số động (a, h, alpha,...)
do LLM xuất ra, ví dụ "a/2", "sqrt(3)*a/2", "h*sin(alpha)".

An toàn: whitelist AST node + whitelist hàm/hằng, không cho phép import,
attribute, lambda, comprehension, hoặc bất cứ thứ gì có side-effect.
"""
from __future__ import annotations

import ast
import math
from typing import Mapping

_ALLOWED_FUNCS: dict[str, object] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "pow": pow,
    "deg": math.degrees,
    "rad": math.radians,
}

_ALLOWED_CONSTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
}

_ALLOWED_NODES: set[type[ast.AST]] = {
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.IfExp,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.BoolOp,
    ast.And,
    ast.Or,
}


class UnsafeExpressionError(ValueError):
    """Expression không an toàn hoặc không hợp lệ."""


def safe_eval(expr: str, variables: Mapping[str, float] | None = None) -> float:
    """Eval một biểu thức toán đơn giản.

    Hỗ trợ: + - * / % ** //, hằng pi/e, hàm sqrt/sin/cos/tan/asin/acos/atan/atan2,
    log/log2/log10/exp, abs/min/max/floor/ceil/round/pow, deg/rad. Mọi tên
    không có trong whitelist phải là biến do caller cung cấp qua `variables`.

    Trả về float. Raise `UnsafeExpressionError` nếu expression không an toàn,
    có biến chưa khai báo, hoặc gây lỗi khi eval.
    """
    if not isinstance(expr, str):
        raise UnsafeExpressionError("expression phải là chuỗi")
    expr = expr.strip()
    if not expr:
        raise UnsafeExpressionError("expression rỗng")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Lỗi cú pháp: {expr!r}") from exc

    variables = dict(variables or {})
    for node in ast.walk(tree):
        node_type = type(node)
        if node_type not in _ALLOWED_NODES:
            raise UnsafeExpressionError(f"Cú pháp không cho phép: {node_type.__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise UnsafeExpressionError("Chỉ cho phép gọi hàm theo tên đơn")
            if node.func.id not in _ALLOWED_FUNCS:
                raise UnsafeExpressionError(f"Hàm không cho phép: {node.func.id}")
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_FUNCS:
                continue
            if node.id in _ALLOWED_CONSTS:
                continue
            if node.id in variables:
                continue
            raise UnsafeExpressionError(f"Biến chưa khai báo: {node.id}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise UnsafeExpressionError(f"Hằng không cho phép: {type(node.value).__name__}")

    namespace: dict[str, object] = {}
    namespace.update(_ALLOWED_FUNCS)
    namespace.update(_ALLOWED_CONSTS)
    namespace.update(variables)
    try:
        result = eval(  # noqa: S307 - đã sandbox AST + namespace
            compile(tree, "<expr>", "eval"),
            {"__builtins__": {}},
            namespace,
        )
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise UnsafeExpressionError(f"Eval lỗi: {exc}") from exc

    if isinstance(result, bool):
        return 1.0 if result else 0.0
    if isinstance(result, (int, float)):
        return float(result)
    raise UnsafeExpressionError("Kết quả eval không phải số")


def try_safe_eval(expr: str, variables: Mapping[str, float] | None = None) -> float | None:
    """Variant không raise: trả None nếu lỗi."""
    try:
        return safe_eval(expr, variables)
    except UnsafeExpressionError:
        return None
