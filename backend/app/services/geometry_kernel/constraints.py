from __future__ import annotations

from dataclasses import dataclass
from math import acos, degrees
from typing import Callable

from app.schemas.scene_v3 import ConstraintResultV3, MathSceneV3, RelationV3
from app.services.geometry_kernel.primitives import (
    GeometryIndex,
    build_geometry_index,
    cross,
    distance,
    dot,
    midpoint,
    norm,
    normalized,
    plane_normal,
    point_line_distance,
    point_plane_distance,
    point_segment_parameter,
    sub,
)


@dataclass(frozen=True)
class Residual:
    value: float
    tolerance: float
    evidence: dict[str, object]


Verifier = Callable[[RelationV3, GeometryIndex], Residual]


def verify_constraints(scene: MathSceneV3, index: GeometryIndex | None = None) -> tuple[ConstraintResultV3, ...]:
    geometry = index or build_geometry_index(scene)
    return tuple(verify_relation(relation, geometry) for relation in scene.relations)


def verify_relation(relation: RelationV3, geometry: GeometryIndex) -> ConstraintResultV3:
    from app.services.relation_registry import normalize_relation_type

    relation_type = normalize_relation_type(relation.type)
    verifier = VERIFIERS.get(relation_type)
    if verifier is None:
        return ConstraintResultV3(
            relation_id=relation.id,
            status="unsupported",
            verifier="geometry-kernel-v3",
            message=f"Chưa hỗ trợ relation {relation.type}",
        )
    try:
        residual = verifier(relation, geometry)
        return ConstraintResultV3(
            relation_id=relation.id,
            status="verified" if residual.value <= residual.tolerance else "failed",
            verifier="geometry-kernel-v3",
            tolerance=residual.tolerance,
            residual=residual.value,
            evidence=residual.evidence,
        )
    except ValueError as error:
        return ConstraintResultV3(
            relation_id=relation.id,
            status="unverifiable",
            verifier="geometry-kernel-v3",
            message=str(error),
        )
    except Exception as error:
        return ConstraintResultV3(
            relation_id=relation.id,
            status="error",
            verifier="geometry-kernel-v3",
            message=error.__class__.__name__,
        )


def _matching_ids(relation: RelationV3, *kinds: str) -> list[str]:
    return [operand.ref_id for operand in relation.operands if not kinds or operand.ref_kind in kinds]


def _ids(relation: RelationV3, *kinds: str) -> list[str]:
    values = _matching_ids(relation, *kinds)
    if not values:
        raise ValueError(f"Relation {relation.id} thiếu operand {kinds}")
    return values


def _line_directions(relation: RelationV3, geometry: GeometryIndex):
    ids = _ids(relation, "line", "segment", "vector")
    if len(ids) != 2:
        raise ValueError(f"Relation {relation.id} cần đúng hai đối tượng tuyến tính")
    endpoints = [geometry.line_points(object_id) for object_id in ids]
    directions = [sub(end, start) for start, end in endpoints]
    return ids, directions


def _line_and_plane(relation: RelationV3, geometry: GeometryIndex):
    line_ids = _matching_ids(relation, "line", "segment", "vector")
    plane_ids = _matching_ids(relation, "plane", "face")
    if len(line_ids) == 1 and len(plane_ids) == 1:
        start, end = geometry.line_points(line_ids[0])
        return line_ids[0], sub(end, start), plane_ids[0], plane_normal(geometry.plane_points(plane_ids[0]), geometry.tolerance)
    return None


def _perpendicular(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    line_plane = _line_and_plane(relation, geometry)
    if line_plane:
        line_id, direction, plane_id, normal = line_plane
        line_unit = normalized(direction, geometry.tolerance)
        residual = norm(cross(line_unit, normal))
        return Residual(residual, geometry.policy.angular_tolerance, {"line_id": line_id, "plane_id": plane_id, "normalized_cross": residual})
    ids, directions = _line_directions(relation, geometry)
    units = [normalized(direction, geometry.tolerance) for direction in directions]
    residual = abs(dot(units[0], units[1]))
    return Residual(residual, geometry.policy.angular_tolerance, {"object_ids": ids, "normalized_dot": residual})


def _parallel(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    line_plane = _line_and_plane(relation, geometry)
    if line_plane:
        line_id, direction, plane_id, normal = line_plane
        line_unit = normalized(direction, geometry.tolerance)
        residual = abs(dot(line_unit, normal))
        return Residual(residual, geometry.policy.angular_tolerance, {"line_id": line_id, "plane_id": plane_id, "normalized_dot": residual})
    ids, directions = _line_directions(relation, geometry)
    units = [normalized(direction, geometry.tolerance) for direction in directions]
    residual = norm(cross(units[0], units[1]))
    return Residual(residual, geometry.policy.angular_tolerance, {"object_ids": ids, "normalized_cross": residual})


def _equal_length(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    ids = _ids(relation, "line", "segment", "vector")
    if len(ids) != 2:
        raise ValueError(f"Relation {relation.id} cần đúng hai đoạn/vector")
    lengths = [distance(*geometry.line_points(object_id)) for object_id in ids]
    residual = abs(lengths[0] - lengths[1])
    return Residual(residual, geometry.tolerance, {"object_ids": ids, "lengths": lengths})


def _midpoint(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _matching_ids(relation, "point")
    segment_ids = _matching_ids(relation, "segment", "line")

    # Dạng chuẩn: 1 điểm giữa + 1 đoạn thẳng.
    if len(point_ids) == 1 and len(segment_ids) == 1:
        expected = midpoint(*geometry.line_points(segment_ids[0]))
        residual = distance(geometry.point(point_ids[0]), expected)
        return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "segment_id": segment_ids[0], "expected": expected})

    # Dạng 3 điểm: E là trung điểm của A và B (thường AI gửi midpoint(A, B, E)).
    # Prefer explicit midpoint role; otherwise prefer last operand; only accept a
    # unique in-tolerance candidate when falling back so mis-ordered operands fail.
    if len(point_ids) == 3:
        role_mid = next(
            (
                op.ref_id
                for op in relation.operands
                if op.ref_kind == "point" and op.role in {"midpoint", "mid", "result"}
            ),
            None,
        )

        def residual_for(mid_id: str) -> Residual:
            others = [pid for pid in point_ids if pid != mid_id]
            expected_mid = midpoint(geometry.point(others[0]), geometry.point(others[1]))
            res = distance(geometry.point(mid_id), expected_mid)
            return Residual(
                res,
                geometry.tolerance,
                {
                    "midpoint_id": mid_id,
                    "endpoint_ids": others,
                    "expected": expected_mid,
                },
            )

        preferred_id = role_mid if role_mid in point_ids else point_ids[-1]
        preferred = residual_for(preferred_id)
        if preferred.value <= preferred.tolerance or role_mid is not None:
            return preferred

        fits = [residual_for(pid) for pid in point_ids]
        within = [item for item in fits if item.value <= item.tolerance]
        if len(within) == 1:
            return within[0]
        # Ambiguous or none fit: keep preferred (last-operand) residual so trust fails closed.
        return preferred

    raise ValueError(f"Relation {relation.id} cần (1 điểm + 1 đoạn) hoặc 3 điểm")


def _on_line(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    line_ids = _ids(relation, "line", "segment")
    if len(point_ids) != 1 or len(line_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một điểm và một đường")
    residual = point_line_distance(geometry.point(point_ids[0]), *geometry.line_points(line_ids[0]), geometry.tolerance)
    return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "line_id": line_ids[0], "distance": residual})


def _point_on_segment(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    segment_ids = _ids(relation, "segment")
    if len(point_ids) != 1 or len(segment_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một điểm và một đoạn")
    point = geometry.point(point_ids[0])
    start, end = geometry.line_points(segment_ids[0])
    line_residual = point_line_distance(point, start, end, geometry.tolerance)
    parameter = point_segment_parameter(point, start, end, geometry.tolerance)
    outside = max(0.0, -parameter, parameter - 1.0) * distance(start, end)
    residual = max(line_residual, outside)
    return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "segment_id": segment_ids[0], "parameter": parameter})


def _collinear(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    ids = _ids(relation, "point")
    if len(ids) < 3:
        raise ValueError(f"Relation {relation.id} cần ít nhất ba điểm")
    first, second = geometry.point(ids[0]), geometry.point(ids[1])
    residual = max(point_line_distance(geometry.point(point_id), first, second, geometry.tolerance) for point_id in ids[2:])
    return Residual(residual, geometry.tolerance, {"point_ids": ids, "max_distance": residual})


def _coplanar(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    ids = _ids(relation, "point")
    if len(ids) < 4:
        raise ValueError(f"Relation {relation.id} cần ít nhất bốn điểm")
    plane = tuple(geometry.point(point_id) for point_id in ids[:3])
    residual = max(point_plane_distance(geometry.point(point_id), plane, geometry.tolerance) for point_id in ids[3:])
    return Residual(residual, geometry.tolerance, {"point_ids": ids, "max_distance": residual})


def _on_plane(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    plane_ids = _ids(relation, "plane", "face")
    if len(point_ids) != 1 or len(plane_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một điểm và một mặt phẳng")
    residual = point_plane_distance(geometry.point(point_ids[0]), geometry.plane_points(plane_ids[0]), geometry.tolerance)
    return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "plane_id": plane_ids[0], "distance": residual})


def _on_circle(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    circle_ids = _ids(relation, "circle")
    if len(point_ids) != 1 or len(circle_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một điểm và một đường tròn")
    center, radius = geometry.circle(circle_ids[0])
    actual = distance(geometry.point(point_ids[0]), center)
    return Residual(abs(actual - radius), geometry.tolerance, {"point_id": point_ids[0], "circle_id": circle_ids[0], "radius": radius, "actual": actual})


def _on_sphere(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    sphere_ids = _ids(relation, "sphere")
    if len(point_ids) != 1 or len(sphere_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một điểm và một mặt cầu")
    center, radius = geometry.sphere(sphere_ids[0])
    actual = distance(geometry.point(point_ids[0]), center)
    return Residual(abs(actual - radius), geometry.tolerance, {"point_id": point_ids[0], "sphere_id": sphere_ids[0], "radius": radius, "actual": actual})


def _distance(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _matching_ids(relation, "point")
    line_ids = _matching_ids(relation, "line", "segment", "vector")
    plane_ids = _matching_ids(relation, "plane", "face")
    expected = relation.args.get("value")

    # Dạng chuẩn: 2 điểm.
    if len(point_ids) == 2 and not line_ids and not plane_ids:
        if not isinstance(expected, (int, float)):
            raise ValueError(f"Relation {relation.id} cần args.value")
        actual = distance(geometry.point(point_ids[0]), geometry.point(point_ids[1]))
        return Residual(abs(actual - float(expected)), geometry.tolerance, {"point_ids": point_ids, "expected": expected, "actual": actual})

    # Dạng điểm-đường: khoảng cách từ điểm đến đường/đoạn.
    if len(point_ids) == 1 and len(line_ids) == 1 and not plane_ids:
        if not isinstance(expected, (int, float)):
            raise ValueError(f"Relation {relation.id} cần args.value")
        actual = point_line_distance(geometry.point(point_ids[0]), *geometry.line_points(line_ids[0]), geometry.tolerance)
        return Residual(abs(actual - float(expected)), geometry.tolerance, {"point_id": point_ids[0], "line_id": line_ids[0], "expected": expected, "actual": actual})

    # Dạng điểm-mặt phẳng: khoảng cách từ điểm đến mặt phẳng.
    if len(point_ids) == 1 and len(plane_ids) == 1 and not line_ids:
        if not isinstance(expected, (int, float)):
            raise ValueError(f"Relation {relation.id} cần args.value")
        actual = point_plane_distance(geometry.point(point_ids[0]), geometry.plane_points(plane_ids[0]), geometry.tolerance)
        return Residual(abs(actual - float(expected)), geometry.tolerance, {"point_id": point_ids[0], "plane_id": plane_ids[0], "expected": expected, "actual": actual})

    raise ValueError(f"Relation {relation.id} cần (2 điểm), (1 điểm + 1 đường) hoặc (1 điểm + 1 mặt phẳng)")


def _angle_at_vertex(
    vertex_id: str,
    arm_ids: list[str],
    expected_degrees: float,
    geometry: GeometryIndex,
) -> Residual:
    """Interior three-point angle at vertex in [0°, 180°] (no abs-dot fold)."""
    vertex = geometry.point(vertex_id)
    others = [geometry.point(arm_id) for arm_id in arm_ids]
    u1 = normalized(sub(others[0], vertex), geometry.tolerance)
    u2 = normalized(sub(others[1], vertex), geometry.tolerance)
    cosine = max(-1.0, min(1.0, dot(u1, u2)))
    actual = degrees(acos(cosine))
    residual = abs(actual - float(expected_degrees))
    angular_degrees = degrees(geometry.policy.angular_tolerance)
    return Residual(
        residual,
        angular_degrees,
        {
            "vertex_id": vertex_id,
            "arm_ids": arm_ids,
            "expected_degrees": expected_degrees,
            "actual_degrees": actual,
        },
    )


def _angle(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _matching_ids(relation, "point")

    # Dạng 3 điểm: góc tại đỉnh tạo bởi 2 cạnh đến 2 điểm còn lại.
    # Prefer role vertex / middle operand (angle A-B-C → B). Only fall back to a
    # unique in-tolerance vertex when the preferred choice fails.
    if len(point_ids) == 3:
        expected = relation.args.get("degrees")
        if not isinstance(expected, (int, float)):
            raise ValueError(f"Relation {relation.id} thiếu args.degrees")
        role_vertex = next(
            (
                op.ref_id
                for op in relation.operands
                if op.ref_kind == "point" and op.role in {"vertex", "apex", "at"}
            ),
            None,
        )
        preferred_vertex = role_vertex if role_vertex in point_ids else point_ids[1]
        preferred = _angle_at_vertex(
            preferred_vertex,
            [pid for pid in point_ids if pid != preferred_vertex],
            float(expected),
            geometry,
        )
        if preferred.value <= preferred.tolerance or role_vertex is not None:
            return preferred

        fits: list[Residual] = []
        for vertex_id in point_ids:
            candidate = _angle_at_vertex(
                vertex_id,
                [pid for pid in point_ids if pid != vertex_id],
                float(expected),
                geometry,
            )
            if candidate.value <= candidate.tolerance:
                fits.append(candidate)
        if len(fits) == 1:
            return fits[0]
        # Ambiguous or none: keep middle-operand residual (fail closed).
        return preferred

    # Dạng 2 đường/đoạn: góc không hướng giữa 2 vector → [0°, 90°].
    ids, directions = _line_directions(relation, geometry)
    expected = relation.args.get("degrees")
    if not isinstance(expected, (int, float)):
        raise ValueError(f"Relation {relation.id} thiếu args.degrees")
    units = [normalized(direction, geometry.tolerance) for direction in directions]
    cosine = max(-1.0, min(1.0, abs(dot(units[0], units[1]))))
    actual = degrees(acos(cosine))
    residual = abs(actual - float(expected))
    angular_degrees = degrees(geometry.policy.angular_tolerance)
    return Residual(residual, angular_degrees, {"object_ids": ids, "expected_degrees": expected, "actual_degrees": actual})


def _parallel_planes(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    ids = _ids(relation, "plane", "face")
    if len(ids) != 2:
        raise ValueError(f"Relation {relation.id} cần hai mặt phẳng")
    normals = [plane_normal(geometry.plane_points(object_id), geometry.tolerance) for object_id in ids]
    residual = norm(cross(normals[0], normals[1]))
    return Residual(residual, geometry.policy.angular_tolerance, {"plane_ids": ids, "normalized_cross": residual})


def _perpendicular_planes(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    ids = _ids(relation, "plane", "face")
    if len(ids) != 2:
        raise ValueError(f"Relation {relation.id} cần hai mặt phẳng")
    normals = [plane_normal(geometry.plane_points(object_id), geometry.tolerance) for object_id in ids]
    residual = abs(dot(normals[0], normals[1]))
    return Residual(residual, geometry.policy.angular_tolerance, {"plane_ids": ids, "normalized_dot": residual})


def _intersection(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    point_ids = _ids(relation, "point")
    line_ids = _matching_ids(relation, "line", "segment")
    plane_ids = _matching_ids(relation, "plane", "face")

    if len(point_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần đúng một giao điểm")
    point = geometry.point(point_ids[0])

    # Dạng chuẩn: giao 2 đường.
    if len(line_ids) == 2 and not plane_ids:
        distances = [point_line_distance(point, *geometry.line_points(oid), geometry.tolerance) for oid in line_ids]
        residual = max(distances)
        return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "line_ids": line_ids, "distances": distances})

    # Dạng 3D: giao đường với mặt phẳng.
    if len(line_ids) == 1 and len(plane_ids) == 1:
        line_dist = point_line_distance(point, *geometry.line_points(line_ids[0]), geometry.tolerance)
        plane_dist = point_plane_distance(point, geometry.plane_points(plane_ids[0]), geometry.tolerance)
        residual = max(line_dist, plane_dist)
        return Residual(residual, geometry.tolerance, {"point_id": point_ids[0], "line_id": line_ids[0], "plane_id": plane_ids[0], "distances": [line_dist, plane_dist]})

    raise ValueError(f"Relation {relation.id} cần (1 điểm + 2 đường) hoặc (1 điểm + 1 đường + 1 mặt phẳng)")


def _line_in_plane(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    line_ids = _ids(relation, "line", "segment")
    plane_ids = _ids(relation, "plane", "face")
    if len(line_ids) != 1 or len(plane_ids) != 1:
        raise ValueError(f"Relation {relation.id} cần một đường và một mặt phẳng")
    plane = geometry.plane_points(plane_ids[0])
    distances = [point_plane_distance(point, plane, geometry.tolerance) for point in geometry.line_points(line_ids[0])]
    residual = max(distances)
    return Residual(residual, geometry.tolerance, {"line_id": line_ids[0], "plane_id": plane_ids[0], "endpoint_distances": distances})


def _ratio(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    object_ids = _ids(relation, "line", "segment", "vector")
    expected = relation.args.get("value")
    if len(object_ids) != 2 or not isinstance(expected, (int, float)):
        raise ValueError(f"Relation {relation.id} cần hai đoạn/vector và args.value")
    lengths = [distance(*geometry.line_points(object_id)) for object_id in object_ids]
    if lengths[1] <= geometry.tolerance:
        raise ValueError("Mẫu tỉ số là đoạn suy biến")
    actual = lengths[0] / lengths[1]
    tolerance = geometry.policy.relative_tolerance * max(1.0, abs(float(expected)))
    return Residual(abs(actual - float(expected)), tolerance, {"object_ids": object_ids, "expected": expected, "actual": actual})


def _tangent(relation: RelationV3, geometry: GeometryIndex) -> Residual:
    line_ids = _matching_ids(relation, "line", "segment")
    circle_ids = _matching_ids(relation, "circle")
    if len(line_ids) == 1 and len(circle_ids) == 1:
        center, radius = geometry.circle(circle_ids[0])
        actual = point_line_distance(center, *geometry.line_points(line_ids[0]), geometry.tolerance)
        return Residual(abs(actual - radius), geometry.tolerance, {"line_id": line_ids[0], "circle_id": circle_ids[0], "center_distance": actual, "radius": radius})
    sphere_ids = _matching_ids(relation, "sphere")
    plane_ids = _matching_ids(relation, "plane", "face")
    if len(sphere_ids) == 1 and len(plane_ids) == 1:
        center, radius = geometry.sphere(sphere_ids[0])
        actual = point_plane_distance(center, geometry.plane_points(plane_ids[0]), geometry.tolerance)
        return Residual(abs(actual - radius), geometry.tolerance, {"sphere_id": sphere_ids[0], "plane_id": plane_ids[0], "center_distance": actual, "radius": radius})
    raise ValueError(f"Relation {relation.id} cần line-circle hoặc sphere-plane")


VERIFIERS: dict[str, Verifier] = {
    "perpendicular": _perpendicular,
    "parallel": _parallel,
    "equal_length": _equal_length,
    "midpoint": _midpoint,
    "intersection": _intersection,
    "tangent": _tangent,
    "on_line": _on_line,
    "point_on_segment": _point_on_segment,
    "collinear": _collinear,
    "coplanar": _coplanar,
    "on_plane": _on_plane,
    "line_in_plane": _line_in_plane,
    "on_circle": _on_circle,
    "on_sphere": _on_sphere,
    "distance": _distance,
    "angle": _angle,
    "ratio": _ratio,
    "parallel_planes": _parallel_planes,
    "perpendicular_planes": _perpendicular_planes,
}