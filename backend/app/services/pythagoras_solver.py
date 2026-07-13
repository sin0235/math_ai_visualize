from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import sympy as sp

from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph, parse_edge_token
from app.services.safe_math_parser import SafeMathParseError, SafeMathComplexityError, parse_safe_math_expression

Edge = tuple[str, str]
PythagorasStatus = Literal["ok", "insufficient", "invalid"]


@dataclass(frozen=True)
class PythagorasProblem:
    vertices: tuple[str, str, str]
    right_vertex: str
    target: Edge
    lengths: dict[Edge, sp.Expr]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class PythagorasResult:
    status: PythagorasStatus
    problem: PythagorasProblem | None = None
    value: sp.Expr | None = None
    result_latex: str | None = None
    formula_latex: str | None = None
    substitution_latex: str | None = None
    verification_latex: str | None = None
    warning: str | None = None


# ponytail: Chỉ giải một tam giác vuông với một cạnh thiếu; mở rộng bằng proof search khi Stage 5 có dependency DAG.
def solve_pythagoras(scene: dict[str, Any], question: str) -> PythagorasResult:
    target = _target_edge(question)
    if target is None:
        return _failure("insufficient", "Cần chỉ rõ cạnh cần tính, ví dụ: tính cạnh AC.")

    candidates = _right_triangle_candidates(scene, target)
    if not candidates:
        return _failure("insufficient", "Thiếu giả thiết góc vuông đã kiểm chứng cho tam giác chứa cạnh cần tính.")
    if len(candidates) > 1:
        return _failure("insufficient", "Có nhiều tam giác vuông chứa cạnh cần tính; chưa xác định được tam giác cần dùng.")

    vertices, right_vertex, right_angle_fact = candidates[0]
    sides = _triangle_sides(vertices)
    lengths, length_facts, error = _exact_side_lengths(scene, sides)
    if error:
        return _failure("invalid", error)
    if target in lengths:
        return _failure("invalid", f"Cạnh {_edge_name(target)} đã có độ dài; không phải cạnh thiếu cần tính.")
    if len(lengths) != 2:
        return _failure("insufficient", "Định lý Pythagore cần đúng hai độ dài cạnh đã biết và một cạnh cần tìm.")

    hypotenuse = _edge_key(*(vertex for vertex in vertices if vertex != right_vertex))
    legs = [side for side in sides if side != hypotenuse]
    known_edges = set(lengths)
    required_edges = set(sides) - {target}
    if known_edges != required_edges:
        return _failure("insufficient", "Hai độ dài đã biết không khớp với hai cạnh còn lại của tam giác vuông.")

    if target == hypotenuse:
        radicand = sp.simplify(lengths[legs[0]] ** 2 + lengths[legs[1]] ** 2)
        formula = rf"{_edge_name(hypotenuse)}^2={_edge_name(legs[0])}^2+{_edge_name(legs[1])}^2"
        substitution = rf"{_edge_name(hypotenuse)}=\sqrt{{{sp.latex(lengths[legs[0]])}^2+{sp.latex(lengths[legs[1]])}^2}}"
    else:
        other_leg = next(leg for leg in legs if leg != target)
        radicand = sp.simplify(lengths[hypotenuse] ** 2 - lengths[other_leg] ** 2)
        formula = rf"{_edge_name(target)}^2={_edge_name(hypotenuse)}^2-{_edge_name(other_leg)}^2"
        substitution = rf"{_edge_name(target)}=\sqrt{{{sp.latex(lengths[hypotenuse])}^2-{sp.latex(lengths[other_leg])}^2}}"

    if radicand.is_positive is not True:
        return _failure("invalid", "Các độ dài mâu thuẫn: bình phương cạnh cần tìm không dương.")
    value = sp.simplify(sp.sqrt(radicand))
    if not _verify_substitution(target, hypotenuse, legs, lengths, value):
        return _failure("invalid", "Kết quả không thỏa đẳng thức Pythagore khi thế lại.")

    problem = PythagorasProblem(
        vertices=vertices,
        right_vertex=right_vertex,
        target=target,
        lengths=lengths,
        evidence_ids=(right_angle_fact.id, *(fact.id for fact in length_facts)),
    )
    verification = _verification_latex(target, hypotenuse, legs, lengths, value)
    return PythagorasResult(
        status="ok",
        problem=problem,
        value=value,
        result_latex=sp.latex(value),
        formula_latex=formula,
        substitution_latex=substitution,
        verification_latex=verification,
    )


def _right_triangle_candidates(
    scene: dict[str, Any],
    target: Edge,
) -> list[tuple[tuple[str, str, str], str, GeometryFact]]:
    graph = build_geometry_fact_graph(scene)
    candidates: list[tuple[tuple[str, str, str], str, GeometryFact]] = []
    facts = [*graph.by_type("right_angle"), *graph.by_type("perpendicular_lines")]
    for fact in facts:
        if fact.type == "right_angle":
            vertex = str(fact.args["vertex"])
            arms = tuple(str(item) for item in fact.args["arms"])
        else:
            first = tuple(fact.args["first"])
            second = tuple(fact.args["second"])
            shared = set(first).intersection(second)
            if len(shared) != 1:
                continue
            vertex = next(iter(shared))
            arms = tuple(
                edge[1] if edge[0] == vertex else edge[0]
                for edge in (first, second)
            )
        vertices = tuple(dict.fromkeys((arms[0], vertex, arms[1])))
        if len(vertices) != 3 or not set(target).issubset(vertices):
            continue
        candidate = (vertices, vertex, fact)
        if not any(existing[0] == vertices and existing[1] == vertex for existing in candidates):
            candidates.append(candidate)
    return candidates


def _exact_side_lengths(
    scene: dict[str, Any],
    sides: tuple[Edge, Edge, Edge],
) -> tuple[dict[Edge, sp.Expr], list[GeometryFact], str | None]:
    graph = build_geometry_fact_graph(scene)
    lengths: dict[Edge, sp.Expr] = {}
    used_facts: list[GeometryFact] = []
    side_set = set(sides)
    for fact in graph.by_type("length"):
        points = fact.args.get("points")
        if not isinstance(points, tuple) or len(points) != 2:
            continue
        edge = _edge_key(str(points[0]), str(points[1]))
        if edge not in side_set:
            continue
        value = _parse_positive_exact(fact.args.get("label"))
        if value is None:
            return {}, [], f"Độ dài {_edge_name(edge)} phải là số exact dương, không chứa biến hoặc đơn vị trong nhãn."
        if edge in lengths and sp.simplify(lengths[edge] - value) != 0:
            return {}, [], f"Dữ kiện độ dài {_edge_name(edge)} bị mâu thuẫn."
        if edge not in lengths:
            lengths[edge] = value
            used_facts.append(fact)
    return lengths, used_facts, None


def _parse_positive_exact(value: Any) -> sp.Expr | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace(",", ".").replace("√", "sqrt")
    text = re.sub(r"sqrt\s*([0-9]+(?:\.[0-9]+)?)", r"sqrt(\1)", text)
    try:
        parsed = parse_safe_math_expression(text).expr
    except (SafeMathParseError, SafeMathComplexityError, TypeError, ValueError):
        return None
    exact = sp.simplify(parsed)
    if exact.free_symbols or exact.is_real is not True or exact.is_finite is not True or exact.is_positive is not True:
        return None
    return exact


def _verify_substitution(
    target: Edge,
    hypotenuse: Edge,
    legs: list[Edge],
    lengths: dict[Edge, sp.Expr],
    value: sp.Expr,
) -> bool:
    resolved = {**lengths, target: value}
    return sp.simplify(resolved[hypotenuse] ** 2 - resolved[legs[0]] ** 2 - resolved[legs[1]] ** 2) == 0


def _verification_latex(
    target: Edge,
    hypotenuse: Edge,
    legs: list[Edge],
    lengths: dict[Edge, sp.Expr],
    value: sp.Expr,
) -> str:
    resolved = {**lengths, target: value}
    return (
        rf"{sp.latex(resolved[hypotenuse])}^2"
        rf"={sp.latex(resolved[legs[0]])}^2+{sp.latex(resolved[legs[1]])}^2"
    )


def _target_edge(question: str) -> Edge | None:
    match = re.search(
        r"(?:tính|tìm|calculate|find)(?:\s+độ\s+dài|\s+cạnh|\s+độ\s+dài\s+cạnh)?\s+([A-Z](?:[0-9]+|')?\s*-?\s*[A-Z](?:[0-9]+|')?)",
        question,
        re.IGNORECASE,
    )
    if match is None:
        match = re.search(r"([A-Z](?:[0-9]+|')?\s*-?\s*[A-Z](?:[0-9]+|')?)\s+(?:bằng bao nhiêu|dài bao nhiêu)", question, re.IGNORECASE)
    edge = parse_edge_token(match.group(1).upper()) if match else None
    return _edge_key(*edge) if edge else None


def _triangle_sides(vertices: tuple[str, str, str]) -> tuple[Edge, Edge, Edge]:
    first, second, third = vertices
    return _edge_key(first, second), _edge_key(second, third), _edge_key(first, third)


def _edge_key(first: str, second: str) -> Edge:
    return tuple(sorted((first.upper(), second.upper())))


def _edge_name(edge: Edge) -> str:
    return "".join(edge)


def _failure(status: Literal["insufficient", "invalid"], warning: str) -> PythagorasResult:
    return PythagorasResult(status=status, warning=warning)