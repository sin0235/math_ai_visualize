from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

import sympy as sp


ANALYZER_COMPLEXITY_LIMIT = "ANALYZER_COMPLEXITY_LIMIT"

MAX_SAFE_MATH_CHARS = 1000
MAX_SAFE_MATH_TOKENS = 220
MAX_SAFE_MATH_AST_NODES = 160
MAX_SAFE_MATH_AST_DEPTH = 32
MAX_SAFE_MATH_FUNCTION_NESTING = 8
MAX_SAFE_MATH_INTEGER_DIGITS = 12
MAX_SAFE_MATH_EXPONENT_ABS = 20
MAX_SAFE_MATH_RESULT_NODES = 220
MAX_SAFE_MATH_POLY_DEGREE = 12


class SafeMathParseError(ValueError):
    code = "ANALYZER_PARSE_FAILED"


class SafeMathComplexityError(ValueError):
    code = ANALYZER_COMPLEXITY_LIMIT


@dataclass(frozen=True)
class SafeMathParseResult:
    expr: sp.Expr
    normalized: str
    complexity_score: int
    token_count: int
    ast_node_count: int
    ast_depth: int


@dataclass(frozen=True)
class _BuildContext:
    symbols: dict[str, sp.Symbol]
    functions: dict[str, Callable]
    constants: dict[str, sp.Expr]


_FUNCTIONS: dict[str, Callable] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "arcsin": sp.asin,
    "arccos": sp.acos,
    "arctan": sp.atan,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "Abs": sp.Abs,
}

_CONSTANTS = {"pi": sp.pi, "E": sp.E, "oo": sp.oo}
_SYMBOLS = {"x": sp.Symbol("x", real=True), "m": sp.Symbol("m", real=True)}
_ALLOWED_NAMES = set(_SYMBOLS) | set(_FUNCTIONS) | set(_CONSTANTS)
_ALLOWED_TOKEN_OPS = {"+", "-", "*", "/", "**", "(", ")", ","}


def parse_safe_math_expression(expression: str) -> SafeMathParseResult:
    if len(expression) > MAX_SAFE_MATH_CHARS:
        raise SafeMathComplexityError(f"Biểu thức vượt quá {MAX_SAFE_MATH_CHARS} ký tự.")
    tokens = _safe_tokens(expression)
    normalized = _tokens_to_python_expression(tokens)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as error:
        raise SafeMathParseError(f"Cú pháp biểu thức không hợp lệ: {error.msg}.") from error

    ast_nodes = list(ast.walk(tree))
    ast_node_count = len(ast_nodes)
    ast_depth = _ast_depth(tree)
    if ast_node_count > MAX_SAFE_MATH_AST_NODES:
        raise SafeMathComplexityError(f"Biểu thức vượt quá {MAX_SAFE_MATH_AST_NODES} node AST.")
    if ast_depth > MAX_SAFE_MATH_AST_DEPTH:
        raise SafeMathComplexityError(f"Biểu thức vượt quá độ sâu AST {MAX_SAFE_MATH_AST_DEPTH}.")

    ctx = _BuildContext(symbols=_SYMBOLS, functions=_FUNCTIONS, constants=_CONSTANTS)
    expr = _build_expr(tree.body, ctx, function_depth=0)
    _assert_sympy_complexity(expr)
    score = len(tokens) + ast_node_count + _sympy_node_count(expr) + ast_depth * 2
    return SafeMathParseResult(
        expr=expr,
        normalized=normalized,
        complexity_score=score,
        token_count=len(tokens),
        ast_node_count=ast_node_count,
        ast_depth=ast_depth,
    )


def _safe_tokens(expression: str) -> list[tokenize.TokenInfo]:
    try:
        raw_tokens = list(tokenize.generate_tokens(io.StringIO(expression).readline))
    except tokenize.TokenError as error:
        raise SafeMathParseError(f"Token biểu thức không hợp lệ: {error}.") from error

    tokens: list[tokenize.TokenInfo] = []
    for token in raw_tokens:
        if token.type in {tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER}:
            continue
        if token.type == tokenize.STRING:
            raise SafeMathParseError("Không cho phép string literal trong biểu thức.")
        if token.type == tokenize.NAME:
            if token.string not in _ALLOWED_NAMES:
                raise SafeMathParseError(f"Ký hiệu hoặc hàm không được hỗ trợ: {token.string}.")
            tokens.append(token)
            continue
        if token.type == tokenize.NUMBER:
            _assert_number_token(token.string)
            tokens.append(token)
            continue
        if token.type == tokenize.OP:
            if token.string == ".":
                raise SafeMathParseError("Không cho phép attribute access trong biểu thức.")
            if token.string not in _ALLOWED_TOKEN_OPS:
                raise SafeMathParseError(f"Toán tử không được hỗ trợ: {token.string}.")
            tokens.append(token)
            continue
        raise SafeMathParseError(f"Token không được hỗ trợ: {token.string}.")

    if len(tokens) > MAX_SAFE_MATH_TOKENS:
        raise SafeMathComplexityError(f"Biểu thức vượt quá {MAX_SAFE_MATH_TOKENS} token.")
    return tokens


def _tokens_to_python_expression(tokens: list[tokenize.TokenInfo]) -> str:
    out: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        if index > 0 and _needs_implicit_mul(tokens[index - 1], token):
            out.append((tokenize.OP, "*"))
        out.append((token.type, token.string))
    return tokenize.untokenize(out)


def _needs_implicit_mul(left: tokenize.TokenInfo, right: tokenize.TokenInfo) -> bool:
    left_value = left.string
    right_value = right.string
    left_atom = left.type in {tokenize.NAME, tokenize.NUMBER} or left_value == ")"
    right_atom = right.type in {tokenize.NAME, tokenize.NUMBER} or right_value == "("
    if not left_atom or not right_atom:
        return False
    if left.type == tokenize.NAME and left_value in _FUNCTIONS and right_value == "(":
        return False
    if left_value == "(" or right_value == ")":
        return False
    return True


def _assert_number_token(value: str) -> None:
    digits = [char for char in value if char.isdigit()]
    if len(digits) > MAX_SAFE_MATH_INTEGER_DIGITS:
        raise SafeMathComplexityError(f"Số trong biểu thức vượt quá {MAX_SAFE_MATH_INTEGER_DIGITS} chữ số.")


def _build_expr(node: ast.AST, ctx: _BuildContext, *, function_depth: int) -> sp.Expr:
    if isinstance(node, ast.BinOp):
        left = _build_expr(node.left, ctx, function_depth=function_depth)
        right = _build_expr(node.right, ctx, function_depth=function_depth)
        if isinstance(node.op, ast.Add):
            return sp.Add(left, right, evaluate=False)
        if isinstance(node.op, ast.Sub):
            return sp.Add(left, sp.Mul(sp.Integer(-1), right, evaluate=False), evaluate=False)
        if isinstance(node.op, ast.Mult):
            return sp.Mul(left, right, evaluate=False)
        if isinstance(node.op, ast.Div):
            return sp.Mul(left, sp.Pow(right, sp.Integer(-1), evaluate=False), evaluate=False)
        if isinstance(node.op, ast.Pow):
            _assert_safe_exponent(right)
            return sp.Pow(left, right, evaluate=False)
        raise SafeMathParseError("Toán tử nhị phân không được hỗ trợ.")
    if isinstance(node, ast.UnaryOp):
        value = _build_expr(node.operand, ctx, function_depth=function_depth)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return sp.Mul(sp.Integer(-1), value, evaluate=False)
        raise SafeMathParseError("Toán tử một ngôi không được hỗ trợ.")
    if isinstance(node, ast.Call):
        if function_depth >= MAX_SAFE_MATH_FUNCTION_NESTING:
            raise SafeMathComplexityError(f"Biểu thức vượt quá {MAX_SAFE_MATH_FUNCTION_NESTING} tầng hàm lồng nhau.")
        if not isinstance(node.func, ast.Name):
            raise SafeMathParseError("Chỉ cho phép gọi hàm đã đăng ký.")
        func_name = node.func.id
        if func_name not in ctx.functions:
            raise SafeMathParseError(f"Hàm không được hỗ trợ: {func_name}.")
        if node.keywords:
            raise SafeMathParseError("Không cho phép keyword argument trong biểu thức.")
        if not 1 <= len(node.args) <= 2:
            raise SafeMathParseError(f"Hàm {func_name} chỉ nhận 1 hoặc 2 tham số.")
        args = [_build_expr(arg, ctx, function_depth=function_depth + 1) for arg in node.args]
        return ctx.functions[func_name](*args)
    if isinstance(node, ast.Name):
        if node.id in ctx.symbols:
            return ctx.symbols[node.id]
        if node.id in ctx.constants:
            return ctx.constants[node.id]
        raise SafeMathParseError(f"Tên không được hỗ trợ: {node.id}.")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise SafeMathParseError("Chỉ cho phép hằng số số học.")
        if isinstance(node.value, int):
            _assert_number_token(str(abs(node.value)))
            return sp.Integer(node.value)
        return sp.Float(node.value)
    raise SafeMathParseError(f"Node AST không được hỗ trợ: {node.__class__.__name__}.")


def _assert_safe_exponent(value: sp.Expr) -> None:
    if value.is_number:
        try:
            number = float(value)
        except Exception as error:
            raise SafeMathComplexityError("Số mũ không tính được kích thước.") from error
        if abs(number) > MAX_SAFE_MATH_EXPONENT_ABS:
            raise SafeMathComplexityError(f"Số mũ vượt quá {MAX_SAFE_MATH_EXPONENT_ABS}.")


def _assert_sympy_complexity(expr: sp.Expr) -> None:
    node_count = _sympy_node_count(expr)
    if node_count > MAX_SAFE_MATH_RESULT_NODES:
        raise SafeMathComplexityError(f"Biểu thức vượt quá {MAX_SAFE_MATH_RESULT_NODES} node SymPy.")
    try:
        degree = sp.Poly(expr, _SYMBOLS["x"]).total_degree()
    except Exception:
        return
    if degree > MAX_SAFE_MATH_POLY_DEGREE:
        raise SafeMathComplexityError(f"Bậc đa thức vượt quá {MAX_SAFE_MATH_POLY_DEGREE}.")


def _sympy_node_count(expr: sp.Expr) -> int:
    return sum(1 for _ in sp.preorder_traversal(expr))


def _ast_depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    if not children:
        return 1
    return 1 + max(_ast_depth(child) for child in children)


def safe_lambdify_expr(expr: sp.Expr):
    return sp.lambdify(_SYMBOLS["x"], expr, "math")


def rational_to_sympy(value: Fraction) -> sp.Rational:
    return sp.Rational(value.numerator, value.denominator)