from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp

from app.services.geometry_facts import GeometryFact, GeometryFactGraph


MAX_FRAME_FACTS = 8
MAX_DERIVED_POINTS = 64


@dataclass(frozen=True)
class OrthogonalFrame:
    fact: GeometryFact
    points: dict[str, sp.Matrix]
    axis_lengths: tuple[sp.Expr, sp.Expr, sp.Expr]


@dataclass(frozen=True)
class ProjectionData:
    foot: sp.Matrix
    alpha: sp.Expr
    beta: sp.Expr
    distance: sp.Expr
    first_direction_point: str
    second_direction_point: str


@dataclass(frozen=True)
class PointPlaneFrameSolution:
    frame: OrthogonalFrame
    points: dict[str, sp.Matrix]
    projection: ProjectionData
    construction_facts: tuple[GeometryFact, ...]


@dataclass(frozen=True)
class PointPlaneFrameResolution:
    solution: PointPlaneFrameSolution | None
    declared_frame_seen: bool
    relevant_frame_seen: bool
    missing_points: tuple[str, ...] = ()
    reason: str | None = None


def parse_point_plane_goal(question: str) -> tuple[str, tuple[str, str, str]] | None:
    match = re.fullmatch(
        r"d\(\s*([A-Za-z](?:[0-9]+|')?)\s*,\s*\(\s*([A-Za-z](?:[0-9]+|')?[A-Za-z0-9']*)\s*\)\s*\)",
        question.strip(),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    source = match.group(1).upper()
    plane_points = tuple(item.upper() for item in re.findall(r"[A-Za-z](?:[0-9]+|')?", match.group(2)))
    if len(plane_points) != 3:
        return None
    return source, (plane_points[0], plane_points[1], plane_points[2])


def resolve_point_plane_frame(
    graph: GeometryFactGraph,
    source: str,
    plane: tuple[str, str, str],
) -> PointPlaneFrameResolution:
    declared_frames = [
        fact
        for fact in graph.facts
        if fact.trusted and fact.type in {"orthogonal_frame", "derived_orthogonal_frame"}
    ]
    frames = orthogonal_frames(graph)
    if not frames:
        reason = (
            "Missing premise độ dài ba phương của khung vuông góc để tính khoảng cách."
            if declared_frames
            else None
        )
        return PointPlaneFrameResolution(None, bool(declared_frames), False, reason=reason)

    relevant_frame_seen = False
    missing: set[str] = set()
    solutions: list[PointPlaneFrameSolution] = []
    for frame in frames[:MAX_FRAME_FACTS]:
        points, construction_fact_ids = derive_named_points(frame, graph)
        if source not in points:
            continue
        relevant_frame_seen = True
        unknown = [name for name in plane if name not in points]
        if unknown:
            missing.update(unknown)
            continue
        projection = project_to_plane(points, source, plane)
        if projection is None:
            continue
        construction_facts = tuple(
            fact for fact in graph.by_type("midpoint") if fact.id in construction_fact_ids
        )
        solutions.append(PointPlaneFrameSolution(frame, points, projection, construction_facts))

    if solutions:
        first_distance = sp.simplify(solutions[0].projection.distance)
        if any(sp.simplify(solution.projection.distance - first_distance) != 0 for solution in solutions[1:]):
            return PointPlaneFrameResolution(
                None,
                True,
                relevant_frame_seen,
                reason="Các khung vuông góc đáng tin cậy cho kết quả khoảng cách mâu thuẫn.",
            )
        return PointPlaneFrameResolution(solutions[0], True, relevant_frame_seen)

    reason = None
    if relevant_frame_seen:
        detail = ", ".join(sorted(missing))
        reason = (
            f"Missing premise midpoint/incidence để xác định điểm {detail} trong mặt phẳng đích."
            if detail
            else "Missing premise để dựng và kiểm chứng chân đường vuông góc trong mặt phẳng đích."
        )
    return PointPlaneFrameResolution(
        None,
        bool(declared_frames),
        relevant_frame_seen,
        tuple(sorted(missing)),
        reason,
    )


def orthogonal_frames(graph: GeometryFactGraph) -> list[OrthogonalFrame]:
    frames: list[OrthogonalFrame] = []
    for fact in graph.facts:
        if not fact.trusted or fact.type not in {"orthogonal_frame", "derived_orthogonal_frame"}:
            continue
        base = labels(fact.args.get("base"))
        top = labels(fact.args.get("top"))
        raw_lengths = fact.args.get("axis_lengths")
        if len(base) != 4 or len(top) != 4 or not isinstance(raw_lengths, tuple | list) or len(raw_lengths) != 3:
            continue
        lengths = tuple(exact_expr(value) for value in raw_lengths)
        if any(
            value is None
            or value.is_finite is not True
            or value.is_real is not True
            or value <= 0
            for value in lengths
        ):
            continue
        lx, ly, lz = lengths
        assert lx is not None and ly is not None and lz is not None
        points = {
            base[0]: sp.Matrix([0, 0, 0]),
            base[1]: sp.Matrix([lx, 0, 0]),
            base[2]: sp.Matrix([lx, ly, 0]),
            base[3]: sp.Matrix([0, ly, 0]),
            top[0]: sp.Matrix([0, 0, lz]),
            top[1]: sp.Matrix([lx, 0, lz]),
            top[2]: sp.Matrix([lx, ly, lz]),
            top[3]: sp.Matrix([0, ly, lz]),
        }
        frames.append(OrthogonalFrame(fact, points, (lx, ly, lz)))
    return frames


def derive_named_points(
    frame: OrthogonalFrame,
    graph: GeometryFactGraph,
) -> tuple[dict[str, sp.Matrix], set[str]]:
    points = dict(frame.points)
    used_fact_ids: set[str] = set()
    midpoint_facts = graph.by_type("midpoint")
    changed = True
    while changed and len(points) < MAX_DERIVED_POINTS:
        changed = False
        for fact in midpoint_facts:
            point = str(fact.args.get("point") or "")
            segment = fact.args.get("segment")
            if not point or point in points or not isinstance(segment, tuple) or len(segment) != 2:
                continue
            first, second = segment
            if first not in points or second not in points:
                continue
            points[point] = sp.simplify((points[first] + points[second]) / 2)
            used_fact_ids.add(fact.id)
            changed = True
    return points, used_fact_ids


def project_to_plane(
    points: dict[str, sp.Matrix],
    source: str,
    plane: tuple[str, str, str],
) -> ProjectionData | None:
    origin, second, third = (points[name] for name in plane)
    first_direction = second - origin
    second_direction = third - origin
    gram = sp.Matrix([
        [first_direction.dot(first_direction), first_direction.dot(second_direction)],
        [first_direction.dot(second_direction), second_direction.dot(second_direction)],
    ])
    if sp.simplify(gram.det()) == 0:
        return None
    offset = points[source] - origin
    rhs = sp.Matrix([offset.dot(first_direction), offset.dot(second_direction)])
    alpha, beta = (sp.simplify(value) for value in gram.inv() * rhs)
    foot = sp.simplify(origin + alpha * first_direction + beta * second_direction)
    height = sp.simplify(points[source] - foot)
    if sp.simplify(height.dot(first_direction)) != 0 or sp.simplify(height.dot(second_direction)) != 0:
        return None
    distance = sp.simplify(sp.sqrt(height.dot(height)))
    if distance.has(sp.nan, sp.zoo) or distance.is_finite is not True or distance.is_real is not True:
        return None

    candidates: list[tuple[str, sp.Matrix]] = []
    for name in plane:
        direction = sp.simplify(points[name] - foot)
        if direction.dot(direction) != 0:
            candidates.append((name, direction))
    selected: tuple[str, str] | None = None
    for index, (first_name, first_vector) in enumerate(candidates):
        for second_name, second_vector in candidates[index + 1:]:
            normal = first_vector.cross(second_vector)
            if normal.dot(normal) != 0:
                selected = first_name, second_name
                break
        if selected:
            break
    if selected is None:
        return None
    return ProjectionData(foot, alpha, beta, distance, selected[0], selected[1])


def exact_expr(value: Any) -> sp.Expr | None:
    text = str(value or "").strip().replace(",", ".")
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?", text)
    if not matches:
        return None
    try:
        return sp.Rational(matches[-1])
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def labels(value: Any) -> tuple[str, ...]:
    if not isinstance(value, tuple | list):
        return ()
    return tuple(str(item).strip().upper() for item in value if str(item).strip())
