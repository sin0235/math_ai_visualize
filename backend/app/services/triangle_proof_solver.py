from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import sympy as sp

from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph
from app.services.safe_math_parser import SafeMathComplexityError, SafeMathParseError, parse_safe_math_expression

Triangle = tuple[str, str, str]
TriangleProofKind = Literal["congruence", "similarity"]
TriangleProofStatus = Literal["verified", "missing_premise", "invalid"]


@dataclass(frozen=True)
class TriangleProofGoal:
    kind: TriangleProofKind
    first: Triangle
    second: Triangle


@dataclass(frozen=True)
class TriangleProofResult:
    status: TriangleProofStatus
    goal: TriangleProofGoal | None = None
    theorem_id: str | None = None
    theorem_name: str | None = None
    premise_facts: tuple[GeometryFact, ...] = ()
    missing_premises: tuple[str, ...] = ()
    answer: str | None = None
    warning: str | None = None


# ponytail: Chỉ replay SSS và AA; thêm SAS/ASA hoặc tỉ số cạnh khi fact contract biểu diễn được góc bằng nhau và tỉ lệ exact.
def solve_triangle_proof(scene: dict[str, Any], question: str) -> TriangleProofResult:
    goal = parse_triangle_proof_goal(question)
    if goal is None:
        return TriangleProofResult(
            status="invalid",
            warning="Cần nêu rõ hai tam giác và mục tiêu bằng nhau hoặc đồng dạng.",
        )
    if len(set(goal.first)) != 3 or len(set(goal.second)) != 3 or set(goal.first) == set(goal.second):
        return TriangleProofResult(
            status="invalid",
            goal=goal,
            warning="Mỗi tam giác cần ba đỉnh phân biệt và hai tam giác không được là cùng một tập đỉnh.",
        )
    return _prove_sss(scene, goal) if goal.kind == "congruence" else _prove_aa(scene, goal)


def parse_triangle_proof_goal(question: str) -> TriangleProofGoal | None:
    triangles = [
        tuple(match.group(1).upper())
        for match in re.finditer(
            r"(?:tam\s*gi[aá]c|triangle|[△∆])\s*([A-Z]{3})",
            question,
            re.IGNORECASE,
        )
    ]
    if len(triangles) != 2:
        return None
    if re.search(r"đ[oồ]ng\s*d[aạ]ng|similar|[∼~]", question, re.IGNORECASE):
        kind: TriangleProofKind = "similarity"
    elif re.search(r"b[aằ]ng\s*nhau|congruent|[≅≡]", question, re.IGNORECASE):
        kind = "congruence"
    else:
        return None
    return TriangleProofGoal(kind=kind, first=triangles[0], second=triangles[1])


def _prove_sss(scene: dict[str, Any], goal: TriangleProofGoal) -> TriangleProofResult:
    graph = build_geometry_fact_graph(scene)
    facts = graph.by_type("equal_length")
    pairs = _corresponding_side_pairs(goal.first, goal.second)
    matched: list[GeometryFact] = []
    missing: list[str] = []
    for first_edge, second_edge in pairs:
        fact = next((candidate for candidate in facts if _equal_length_matches(candidate, first_edge, second_edge)), None)
        if fact is None:
            missing.append(f"{_edge_name(first_edge)} = {_edge_name(second_edge)}")
        elif fact.id not in {item.id for item in matched}:
            matched.append(fact)
    if missing:
        return TriangleProofResult(
            status="missing_premise",
            goal=goal,
            premise_facts=tuple(matched),
            missing_premises=tuple(missing),
            warning=f"Thiếu premise SSS: {', '.join(missing)}.",
        )
    return TriangleProofResult(
        status="verified",
        goal=goal,
        theorem_id="triangle.congruence.sss",
        theorem_name="Trường hợp bằng nhau cạnh-cạnh-cạnh",
        premise_facts=tuple(matched),
        answer=f"△{''.join(goal.first)} ≅ △{''.join(goal.second)}",
    )


def _prove_aa(scene: dict[str, Any], goal: TriangleProofGoal) -> TriangleProofResult:
    graph = build_geometry_fact_graph(scene)
    facts = graph.by_type("angle_measure")
    matched_pairs: list[tuple[GeometryFact, GeometryFact]] = []
    missing: list[str] = []
    for first_vertex, second_vertex in zip(goal.first, goal.second, strict=True):
        first_fact = _angle_at(facts, goal.first, first_vertex)
        second_fact = _angle_at(facts, goal.second, second_vertex)
        if first_fact is None or second_fact is None or not _same_exact_angle(first_fact, second_fact):
            missing.append(f"∠{_angle_name(goal.first, first_vertex)} = ∠{_angle_name(goal.second, second_vertex)}")
            continue
        matched_pairs.append((first_fact, second_fact))
    if len(matched_pairs) < 2:
        return TriangleProofResult(
            status="missing_premise",
            goal=goal,
            premise_facts=_unique_facts(fact for pair in matched_pairs for fact in pair),
            missing_premises=tuple(missing),
            warning=f"Thiếu premise AA: cần hai cặp góc tương ứng bằng nhau; chưa có {', '.join(missing)}.",
        )
    premise_facts = _unique_facts(fact for pair in matched_pairs[:2] for fact in pair)
    return TriangleProofResult(
        status="verified",
        goal=goal,
        theorem_id="triangle.similarity.aa",
        theorem_name="Trường hợp đồng dạng góc-góc",
        premise_facts=premise_facts,
        answer=f"△{''.join(goal.first)} ∼ △{''.join(goal.second)}",
    )


def _corresponding_side_pairs(first: Triangle, second: Triangle):
    return (
        (_edge(first[0], first[1]), _edge(second[0], second[1])),
        (_edge(first[1], first[2]), _edge(second[1], second[2])),
        (_edge(first[0], first[2]), _edge(second[0], second[2])),
    )


def _equal_length_matches(fact: GeometryFact, first_edge: tuple[str, str], second_edge: tuple[str, str]) -> bool:
    fact_first = _edge(*fact.args.get("first", ("", "")))
    fact_second = _edge(*fact.args.get("second", ("", "")))
    return {fact_first, fact_second} == {first_edge, second_edge}


def _angle_at(facts: list[GeometryFact], triangle: Triangle, vertex: str) -> GeometryFact | None:
    arms = set(triangle) - {vertex}
    return next(
        (
            fact
            for fact in facts
            if fact.args.get("vertex") == vertex and set(fact.args.get("arms") or ()) == arms
        ),
        None,
    )


def _same_exact_angle(first: GeometryFact, second: GeometryFact) -> bool:
    first_value = _parse_angle(first.args.get("label"))
    second_value = _parse_angle(second.args.get("label"))
    return first_value is not None and second_value is not None and sp.simplify(first_value - second_value) == 0


def _parse_angle(value: Any) -> sp.Expr | None:
    text = str(value or "").strip().replace(",", ".")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(?:°|deg)?", text, re.IGNORECASE)
    if match is None:
        return None
    try:
        exact = sp.simplify(parse_safe_math_expression(match.group(1)).expr)
    except (SafeMathComplexityError, SafeMathParseError, TypeError, ValueError):
        return None
    return exact if exact.is_real is True and 0 < exact < 180 else None


def _unique_facts(facts) -> tuple[GeometryFact, ...]:
    unique: list[GeometryFact] = []
    for fact in facts:
        if fact.id not in {item.id for item in unique}:
            unique.append(fact)
    return tuple(unique)


def _angle_name(triangle: Triangle, vertex: str) -> str:
    arms = [point for point in triangle if point != vertex]
    return f"{arms[0]}{vertex}{arms[1]}"


def _edge(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first.upper(), second.upper())))


def _edge_name(edge: tuple[str, str]) -> str:
    return "".join(edge)