from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import sympy as sp
from sympy.parsing.sympy_parser import convert_xor, implicit_multiplication_application, parse_expr, standard_transformations

from app.services.algebra.normalizer import normalize_algebra_input

TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application, convert_xor)
RELATION_OPERATORS = ("<=", ">=", "!=", "=", "<", ">")


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


def parse_algebra_problem(raw_input: str, topic: str = "auto", variables: list[str] | None = None, domain: str = "R") -> ParsedAlgebraProblem:
    normalized = normalize_algebra_input(raw_input)
    variable_names = variables or ["x"]
    if topic == "system" and variables is None:
        variable_names = ["x", "y"]
    local_dict = _local_dict(variable_names, real=(domain != "C"))
    symbols = [local_dict[name] for name in variable_names if isinstance(local_dict[name], sp.Symbol)]
    variable = symbols[0]
    relations = _parse_relations(normalized, local_dict)
    if len(relations) > 1:
        return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else "system", relation=relations[0], relations=relations, variable=variable, variables=symbols, domain=domain)
    relation = relations[0] if relations else _parse_relation(normalized, local_dict)
    if relation is not None:
        detected = _relation_topic(relation)
        return ParsedAlgebraProblem(raw_input, normalized, topic if topic != "auto" else detected, relation=relation, relations=[relation], variable=variable, variables=symbols, domain=domain)
    try:
        expression = _parse_expr(normalized, local_dict)
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


def _parse_expr(text: str, local_dict: dict[str, object]) -> sp.Expr:
    return parse_expr(text.strip(), local_dict=local_dict, transformations=TRANSFORMATIONS, evaluate=True)


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
