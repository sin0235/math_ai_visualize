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

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

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

_SYMPY_FUNCS: dict[str, object] = {
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "atan2": sp.atan2,
    "log": sp.log,
    "log2": lambda value: sp.log(value, 2),
    "log10": lambda value: sp.log(value, 10),
    "exp": sp.exp,
    "abs": sp.Abs,
    "min": sp.Min,
    "max": sp.Max,
    "floor": sp.floor,
    "ceil": sp.ceiling,
    "round": round,
    "pow": sp.Pow,
    "deg": lambda value: value * 180 / sp.pi,
    "rad": lambda value: value * sp.pi / 180,
}

_SYMPY_CONSTS: dict[str, object] = {
    "pi": sp.pi,
    "e": sp.E,
    "E": sp.E,
}

_MAX_EXPR_CHARS = 500
_MAX_AST_NODES = 120

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


def _validate_expression(expr: str, variables: Mapping[str, object] | None = None) -> ast.Expression:
    if not isinstance(expr, str):
        raise UnsafeExpressionError("expression phải là chuỗi")
    expr = expr.strip()
    if not expr:
        raise UnsafeExpressionError("expression rỗng")
    if len(expr) > _MAX_EXPR_CHARS:
        raise UnsafeExpressionError("expression quá dài")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Lỗi cú pháp: {expr!r}") from exc

    variables = dict(variables or {})
    nodes = list(ast.walk(tree))
    if len(nodes) > _MAX_AST_NODES:
        raise UnsafeExpressionError("expression quá phức tạp")
    for node in nodes:
        node_type = type(node)
        if node_type not in _ALLOWED_NODES:
            raise UnsafeExpressionError(f"Cú pháp không cho phép: {node_type.__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise UnsafeExpressionError("Chỉ cho phép gọi hàm theo tên đơn")
            if node.func.id not in _ALLOWED_FUNCS:
                raise UnsafeExpressionError(f"Hàm không cho phép: {node.func.id}")
            if node.func.id == "pow":
                _validate_power_arguments(node.args)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            _validate_power_arguments([node.right])
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
    return tree


def _validate_power_arguments(arguments: list[ast.AST]) -> None:
    exponent = arguments[-1] if arguments else None
    if not isinstance(exponent, ast.Constant) or isinstance(exponent.value, bool) or not isinstance(exponent.value, (int, float)):
        raise UnsafeExpressionError("Số mũ phải là hằng số hữu hạn")
    if not math.isfinite(float(exponent.value)) or abs(float(exponent.value)) > 64:
        raise UnsafeExpressionError("Số mũ vượt giới hạn an toàn")


def _evaluate_node(node: ast.AST, namespace: Mapping[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return namespace[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_node(node.operand, namespace)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left, namespace)
        right = _evaluate_node(node.right, namespace)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left**right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
    if isinstance(node, ast.Call):
        function = namespace[node.func.id]  # _validate_expression chỉ cho phép ast.Name trong whitelist.
        return function(*(_evaluate_node(argument, namespace) for argument in node.args))
    if isinstance(node, ast.IfExp):
        branch = node.body if _evaluate_node(node.test, namespace) else node.orelse
        return _evaluate_node(branch, namespace)
    if isinstance(node, ast.Compare):
        left = _evaluate_node(node.left, namespace)
        for operator, comparator in zip(node.ops, node.comparators):
            right = _evaluate_node(comparator, namespace)
            matches = (
                left == right if isinstance(operator, ast.Eq) else
                left != right if isinstance(operator, ast.NotEq) else
                left < right if isinstance(operator, ast.Lt) else
                left <= right if isinstance(operator, ast.LtE) else
                left > right if isinstance(operator, ast.Gt) else
                left >= right
            )
            if not matches:
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        values = iter(node.values)
        result = _evaluate_node(next(values), namespace)
        for value in values:
            if isinstance(node.op, ast.And) and not result:
                return result
            if isinstance(node.op, ast.Or) and result:
                return result
            result = _evaluate_node(value, namespace)
        return result
    raise UnsafeExpressionError(f"Cú pháp không hỗ trợ: {type(node).__name__}")


def safe_eval(expr: str, variables: Mapping[str, float] | None = None) -> float:
    """Eval một biểu thức toán đơn giản.

    Hỗ trợ: + - * / % ** //, hằng pi/e, hàm sqrt/sin/cos/tan/asin/acos/atan/atan2,
    log/log2/log10/exp, abs/min/max/floor/ceil/round/pow, deg/rad. Mọi tên
    không có trong whitelist phải là biến do caller cung cấp qua `variables`.

    Trả về float. Raise `UnsafeExpressionError` nếu expression không an toàn,
    có biến chưa khai báo, hoặc gây lỗi khi eval.
    """
    tree = _validate_expression(expr, variables)
    namespace: dict[str, object] = {}
    namespace.update(_ALLOWED_FUNCS)
    namespace.update(_ALLOWED_CONSTS)
    namespace.update(dict(variables or {}))
    try:
        result = _evaluate_node(tree.body, namespace)
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise UnsafeExpressionError(f"Eval lỗi: {exc}") from exc

    if isinstance(result, bool):
        return 1.0 if result else 0.0
    if isinstance(result, (int, float)):
        numeric = float(result)
        if not math.isfinite(numeric):
            raise UnsafeExpressionError("Kết quả eval không hữu hạn")
        return numeric
    raise UnsafeExpressionError("Kết quả eval không phải số")


def safe_sympify(expr: str, variables: Mapping[str, float | int | str | sp.Expr] | None = None) -> sp.Expr:
    _validate_expression(expr, variables)
    local_dict: dict[str, object] = {}
    local_dict.update(_SYMPY_FUNCS)
    local_dict.update(_SYMPY_CONSTS)
    for name, value in dict(variables or {}).items():
        local_dict[name] = sp.sympify(value, locals={**_SYMPY_FUNCS, **_SYMPY_CONSTS})
    try:
        global_dict = {name: getattr(sp, name) for name in ("Integer", "Float", "Rational", "Symbol")}
        global_dict["__builtins__"] = {}
        parsed = parse_expr(expr.replace("^", "**"), local_dict=local_dict, global_dict=global_dict, evaluate=True)
        return sp.simplify(parsed)
    except Exception as exc:
        raise UnsafeExpressionError(f"SymPy parse lỗi: {exc}") from exc


def safe_eval_exact(expr: str, variables: Mapping[str, float | int | str | sp.Expr] | None = None) -> tuple[sp.Expr, float]:
    parsed = safe_sympify(expr, variables)
    try:
        value = float(parsed.evalf())
    except (TypeError, ValueError) as exc:
        raise UnsafeExpressionError(f"Eval exact lỗi: {exc}") from exc
    if not math.isfinite(value):
        raise UnsafeExpressionError("Kết quả eval không hữu hạn")
    return parsed, value


def try_safe_eval(expr: str, variables: Mapping[str, float] | None = None) -> float | None:
    """Variant không raise: trả None nếu lỗi."""
    try:
        return safe_eval(expr, variables)
    except UnsafeExpressionError:
        return None


def try_safe_eval_exact(expr: str, variables: Mapping[str, float | int | str | sp.Expr] | None = None) -> tuple[sp.Expr, float] | None:
    """Variant exact không raise: trả None nếu lỗi."""
    try:
        return safe_eval_exact(expr, variables)
    except UnsafeExpressionError:
        return None
