from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass, field
from typing import Literal

import sympy as sp
from sympy.parsing.sympy_parser import convert_xor, implicit_multiplication_application, parse_expr, standard_transformations

from app.services.algebra.normalizer import normalize_algebra_input

TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
RELATION_OPERATORS = ("<=", ">=", "!=", "=", "<", ">")

_MAX_PARSE_CHARS = 2000
_MAX_INT_DIGITS = 20
_MAX_PARENS = 40
_MAX_POWER_OPS = 8
_MAX_TOKENS = 220

# Names allowed in algebra expressions (functions + constants + common symbols).
# Dynamic variable symbols from local_dict are also accepted at tokenize time.
_ALLOWED_FUNCTION_NAMES = {
    "sqrt", "root", "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "acot", "arcsin", "arccos", "arctan",
    "log", "ln", "exp", "abs", "Abs", "re", "im", "arg", "conjugate",
    "factorial", "binomial", "floor", "ceiling", "sign",
    "I", "pi", "E", "oo", "zoo", "nan",
}
_ALLOWED_TOKEN_OPS = {"+", "-", "*", "/", "**", "(", ")", ",", "="}


class AlgebraParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedAlgebraProblem:
    raw_input: str
    normalized_input: str
    topic: str
    relation: sp.Relational | None = None
    relations: list[sp.Relational] = field(default_factory=list)
    expression: sp.Expr | None = None
    variable: sp.Symbol = sp.Symbol("x", real=True)
    variables: list[sp.Symbol] = field(default_factory=list)
    domain: str = "R"
    # Optional solve interval (e.g. [0, 2π)); None means full problem domain.
    solve_interval: sp.Set | None = None

    @property
    def sympy_domain(self) -> sp.Set:
        if self.domain == "C":
            return sp.S.Complexes
        if self.domain == "Z":
            return sp.S.Integers
        if self.domain == "N":
            return sp.S.Naturals
        return sp.S.Reals

    @property
    def is_real_domain(self) -> bool:
        return self.domain in {"R", "Z", "N"}


def parse_algebra_problem(raw_input: str, topic: str = "auto", variables: list[str] | None = None, domain: str = "R") -> ParsedAlgebraProblem:
    normalized = normalize_algebra_input(raw_input)
    if variables:
        variable_names = list(variables)
    elif topic == "system":
        variable_names = ["x", "y"]
    else:
        variable_names = ["x"]
    local_dict = _local_dict(variable_names, real=(domain != "C"))
    symbols = [local_dict[name] for name in variable_names if isinstance(local_dict[name], sp.Symbol)]
    variable = symbols[0]
    relations = _parse_relations(normalized, local_dict)
    if len(relations) > 1:
        detected_multi = "system" if all(isinstance(rel, sp.Equality) for rel in relations) else "inequality"
        return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else detected_multi, relation=relations[0], relations=relations, variable=variable, variables=symbols, domain=domain)
    chained = _parse_chained_inequality(normalized, local_dict)
    if chained:
        return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else "inequality", relation=chained[0], relations=chained, variable=variable, variables=symbols, domain=domain)
    relation = relations[0] if relations else _parse_relation(normalized, local_dict)
    if relation is not None:
        detected = _relation_topic(relation)
        return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else detected, relation=relation, relations=[relation], variable=variable, variables=symbols, domain=domain)
    try:
        expression = _parse_expr(normalized, local_dict)
    except AlgebraParseError:
        raise
    except Exception as exc:
        raise AlgebraParseError(f"Không parse được biểu thức: {exc}") from exc
    return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else "expression", expression=expression, variable=variable, variables=symbols, domain=domain)


def _parse_relations(text: str, local_dict: dict[str, object]) -> list[sp.Relational]:
    parts = [part.strip() for part in text.replace("\n", ";").split(";") if part.strip()]
    if len(parts) <= 1:
        return []
    relations: list[sp.Relational] = []
    for part in parts:
        relation = _parse_relation(part, local_dict)
        if relation is None:
            return []
        relations.append(relation)
    return relations


def _parse_relation(text: str, local_dict: dict[str, object]) -> sp.Relational | None:
    for operator in RELATION_OPERATORS:
        if operator not in text:
            continue
        left_text, right_text = text.split(operator, 1)
        if not left_text.strip() or not right_text.strip():
            continue
        # Avoid treating chained inequalities (0 < x < 1) as a single split on first op.
        if operator in {"<", ">", "<=", ">="} and _looks_chained_right(right_text):
            continue
        left = _parse_expr(left_text, local_dict)
        right = _parse_expr(right_text, local_dict)
        if operator == "=":
            return sp.Eq(left, right, evaluate=False)
        if operator == "<=":
            return sp.Le(left, right, evaluate=False)
        if operator == ">=":
            return sp.Ge(left, right, evaluate=False)
        if operator == "<":
            return sp.Lt(left, right, evaluate=False)
        if operator == ">":
            return sp.Gt(left, right, evaluate=False)
        if operator == "!=":
            return sp.Ne(left, right, evaluate=False)
    return None


def _looks_chained_right(text: str) -> bool:
    return bool(re.search(r"(<=|>=|<|>)", text))


def _parse_chained_inequality(text: str, local_dict: dict[str, object]) -> list[sp.Relational] | None:
    """Parse a < b < c or a <= b <= c into two relations (And as list)."""
    cleaned = text.strip()
    if ";" in cleaned or "\n" in cleaned:
        return None
    tokens = re.split(r"(<=|>=|<|>)", cleaned)
    if len(tokens) < 5 or len(tokens) % 2 == 0:
        return None
    # tokens: expr, op, expr, op, expr, ...
    expressions = tokens[0::2]
    operators = tokens[1::2]
    if len(expressions) < 3 or len(operators) != len(expressions) - 1:
        return None
    if any(op not in {"<", ">", "<=", ">="} for op in operators):
        return None
    try:
        parsed_exprs = [_parse_expr(part, local_dict) for part in expressions]
    except Exception:
        return None
    relations: list[sp.Relational] = []
    for index, operator in enumerate(operators):
        left, right = parsed_exprs[index], parsed_exprs[index + 1]
        if operator == "<":
            relations.append(sp.Lt(left, right, evaluate=False))
        elif operator == ">":
            relations.append(sp.Gt(left, right, evaluate=False))
        elif operator == "<=":
            relations.append(sp.Le(left, right, evaluate=False))
        else:
            relations.append(sp.Ge(left, right, evaluate=False))
    return relations


def _precheck_expr_text(text: str) -> None:
    if len(text) > _MAX_PARSE_CHARS:
        raise AlgebraParseError("Biểu thức vượt giới hạn độ dài an toàn.")
    if text.count("(") > _MAX_PARENS or text.count(")") > _MAX_PARENS:
        raise AlgebraParseError("Biểu thức có quá nhiều ngoặc lồng nhau.")
    if len(re.findall(r"\*\*|\^", text)) > _MAX_POWER_OPS:
        raise AlgebraParseError("Biểu thức có quá nhiều phép lũy thừa lồng nhau.")
    for match in re.finditer(r"\d+", text):
        if len(match.group(0)) > _MAX_INT_DIGITS:
            raise AlgebraParseError("Số nguyên trong biểu thức quá lớn.")
    if "__" in text or "import" in text.lower() or "exec" in text.lower() or "eval" in text.lower():
        raise AlgebraParseError("Biểu thức chứa token không an toàn.")


def _tokenize_allowlist_check(text: str, allowed_names: set[str]) -> None:
    """Reject attribute access and unknown names before sympy parse_expr (safe_math-inspired)."""
    try:
        raw_tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenError as error:
        raise AlgebraParseError(f"Token biểu thức không hợp lệ: {error}.") from error
    count = 0
    for token in raw_tokens:
        if token.type in {tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT}:
            continue
        if token.type == tokenize.STRING:
            raise AlgebraParseError("Không cho phép string literal trong biểu thức.")
        if token.type == tokenize.NAME:
            name = token.string
            if name.startswith("__") or name not in allowed_names:
                raise AlgebraParseError(f"Ký hiệu hoặc hàm không được hỗ trợ: {name}.")
            count += 1
            continue
        if token.type == tokenize.NUMBER:
            count += 1
            continue
        if token.type == tokenize.OP:
            if token.string == ".":
                raise AlgebraParseError("Không cho phép attribute access trong biểu thức.")
            if token.string not in _ALLOWED_TOKEN_OPS:
                # Relational ops appear only at problem level, not inside single expr.
                raise AlgebraParseError(f"Toán tử không được hỗ trợ trong biểu thức: {token.string}.")
            count += 1
            continue
        if token.type == tokenize.ERRORTOKEN:
            raise AlgebraParseError("Token biểu thức không hợp lệ.")
        # Ignore whitespace-like leftovers
        if token.string.strip() == "":
            continue
        raise AlgebraParseError(f"Token không được hỗ trợ: {token.string!r}.")
    if count > _MAX_TOKENS:
        raise AlgebraParseError(f"Biểu thức vượt quá {_MAX_TOKENS} token.")


def _parse_expr(text: str, local_dict: dict[str, object]) -> sp.Expr:
    cleaned = text.strip()
    _precheck_expr_text(cleaned)
    allowed_names = set(_ALLOWED_FUNCTION_NAMES) | {
        name for name, value in local_dict.items() if isinstance(value, sp.Symbol)
    }
    # Also allow any symbol-like keys in local_dict (functions registered there).
    allowed_names |= {name for name in local_dict if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)}
    _tokenize_allowlist_check(cleaned, allowed_names)
    global_dict = {name: getattr(sp, name) for name in ("Integer", "Float", "Rational", "Symbol")}
    global_dict["__builtins__"] = {}
    return parse_expr(
        cleaned,
        local_dict=local_dict,
        global_dict=global_dict,
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )


# Interval bounds: only numeric / constant expressions (no free variables, no functions).
# Supports: numbers, pi, e, oo, optional leading sign, 2*pi, pi/2, -pi, -e, etc.
_INTERVAL_BOUND_RE = re.compile(
    r"^[+\-]?(?:"
    r"(?:oo|inf|infinity)"
    r"|\d+(?:\.\d+)?(?:/\d+)?"
    r"|(?:\d+(?:\.\d+)?\*)?(?:pi|e|E)(?:/\d+)?"
    r"|(?:pi|e|E)(?:\*\d+(?:\.\d+)?)?"
    r")$",
    re.IGNORECASE,
)


def parse_interval_bound(text: str | None) -> sp.Expr:
    """Parse an interval endpoint with a strict allowlist (no unrestricted sympify)."""
    if text is None or str(text).strip() == "":
        raise AlgebraParseError("Cận khoảng trống.")
    cleaned = str(text).strip().replace("^", "**").replace(" ", "")
    # Normalize unicode minus
    cleaned = cleaned.replace("−", "-")
    if cleaned in {"oo", "inf", "infinity", "+oo", "+inf"}:
        return sp.oo
    if cleaned in {"-oo", "-inf", "-infinity"}:
        return -sp.oo
    if not _INTERVAL_BOUND_RE.fullmatch(cleaned):
        raise AlgebraParseError("Cận khoảng chỉ hỗ trợ số, pi, e, oo (ví dụ -pi, 2*pi, pi/2).")
    _precheck_expr_text(cleaned)
    local_dict = {
        "pi": sp.pi,
        "e": sp.E,
        "E": sp.E,
        "oo": sp.oo,
        "inf": sp.oo,
        "infinity": sp.oo,
    }
    global_dict = {name: getattr(sp, name) for name in ("Integer", "Float", "Rational", "Symbol")}
    global_dict["__builtins__"] = {}
    expr = parse_expr(
        cleaned,
        local_dict=local_dict,
        global_dict=global_dict,
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )
    if getattr(expr, "free_symbols", set()):
        raise AlgebraParseError("Cận khoảng không được chứa biến tự do.")
    return sp.simplify(expr)


def _local_dict(variable_names: list[str], real: bool = True) -> dict[str, object]:
    names = set(variable_names) | {"x", "y", "z", "m", "a", "b", "c", "t", "n", "k"}
    data: dict[str, object] = {name: sp.Symbol(name, real=real) for name in names}
    data.update({
        "sqrt": sp.sqrt,
        "root": lambda value, degree: value ** (sp.Rational(1, degree)),
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "cot": sp.cot,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,
        "acot": sp.acot,
        "arcsin": sp.asin,
        "arccos": sp.acos,
        "arctan": sp.atan,
        "arccot": sp.acot,
        "log": sp.log,
        "ln": sp.log,
        "exp": sp.exp,
        "Abs": sp.Abs,
        "abs": sp.Abs,
        "C": sp.binomial,
        "binomial": sp.binomial,
        "factorial": sp.factorial,
        "pi": sp.pi,
        "oo": sp.oo,
        "E": sp.E,
        "I": sp.I,
        "i": sp.I,
    })
    return data


def _relation_topic(relation: sp.Relational) -> Literal["equation", "inequality"]:
    return "equation" if isinstance(relation, sp.Equality) else "inequality"
