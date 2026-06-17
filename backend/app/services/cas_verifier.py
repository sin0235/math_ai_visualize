"""CAS verify + auto-correct cho MathScene.

Sau khi LLM dựng scene, có thể có sai lệch số học so với mô tả:
- "M là trung điểm AB" nhưng toạ độ M không chính xác
- "SA ⟂ (ABCD)" nhưng dot product giữa SA và một vector trong (ABCD) ≠ 0
- "AB = BC" nhưng độ dài thực tế khác nhau
- "A nằm trên (ABC)" nhưng A không nằm trên mặt phẳng đó
- "AB tiếp tuyến với (C)" nhưng khoảng cách tâm đến đường thẳng ≠ bán kính

Module này chạy 2 pass:

1. ``verify_scene(scene)`` → trả về danh sách ``CasIssue`` mô tả vi phạm.
2. ``auto_fix_scene(scene, issues)`` → cố gắng sửa các trường hợp DETERMINISTIC
   (midpoint, on_line, on_plane, on_sphere, on_circle), trả về scene đã chỉnh
   và issues còn lại (không fix được).

Triết lý: ưu tiên an toàn — chỉ fix khi quan hệ không có ambiguity. Các quan
hệ phức tạp (đa biến, hệ phương trình) chỉ log warning để frontend hiển thị.

Ngưỡng dung sai cố định ở ``REL_EPS`` (~1e-6) để tránh nhiễu floating-point
nhưng vẫn bắt được lệch ý nghĩa.

Các loại quan hệ được verify:
- perpendicular: đoạn-đoạn, đoạn-mặt phẳng
- parallel: đoạn-đoạn (2D/3D)
- equal_length: |AB| == |CD|
- midpoint: M là trung điểm AB
- collinear: 3+ điểm thẳng hàng
- coplanar: 4+ điểm đồng phẳng
- on_line: điểm nằm trên đoạn/đường thẳng AB
- on_plane: điểm nằm trên mặt phẳng (ABC...)
- on_sphere: điểm cách tâm = bán kính
- on_circle: điểm cách tâm = bán kính (2D)
- tangent: đường tiếp xúc đường tròn / mặt cầu
- distance: khoảng cách hai điểm = giá trị (metadata.value)
- angle: số đo góc = giá trị (metadata.value, đơn vị độ)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import acos, degrees, isfinite, sqrt
from typing import Any

import numpy as np
import sympy as sp
from scipy.optimize import least_squares

from app.schemas.scene import (
    Circle2D,
    Face,
    MathScene,
    Plane,
    Point2D,
    Point3D,
    Relation,
    Sphere,
)
from app.services.linalg import add as _vec_add, as_vec3, bbox_diagonal as _bbox_diag, cross as _cross3, dot as _dot, norm as _length, plane_from_points, scale as _vec_scale, sub as _vec_sub, to_tuple, vec3

REL_EPS = 1e-6
_SAFE_SYMPY_LOCALS = {
    "sqrt": sp.sqrt,
    "pi": sp.pi,
    "E": sp.E,
    "e": sp.E,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "abs": sp.Abs,
}


@dataclass
class CasIssue:
    relation_type: str
    description: str
    severity: str = "warning"  # warning | error
    auto_fixed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Vector primitives
# ---------------------------------------------------------------------------


def _coords(point: Point2D | Point3D):
    if isinstance(point, Point3D):
        return vec3(point.x, point.y, point.z)
    return (point.x, point.y)


def _to_3d(v):
    if len(v) == 3:
        return vec3(v[0], v[1], v[2])
    return vec3(v[0], v[1], 0.0)


def _coord_expr(point: Point2D | Point3D) -> tuple[sp.Expr, ...]:
    values = (point.x, point.y, point.z) if isinstance(point, Point3D) else (point.x, point.y)
    exprs = (
        (point.x_expr, point.y_expr, point.z_expr)
        if isinstance(point, Point3D)
        else (point.x_expr, point.y_expr)
    )
    return tuple(_parse_expr(expr, value) for expr, value in zip(exprs, values, strict=True))


def _parse_expr(expr: str | None, value: float) -> sp.Expr:
    if expr:
        try:
            parsed = sp.sympify(expr, locals=_SAFE_SYMPY_LOCALS)
            if not parsed.free_symbols:
                return sp.simplify(parsed)
        except Exception:
            pass
    return sp.Rational(str(float(value))).limit_denominator(1_000_000)


def _expr_float(expr: sp.Expr) -> float:
    return float(sp.N(expr))


def _expr_text(expr: sp.Expr) -> str | None:
    simplified = sp.simplify(expr)
    if simplified == 0:
        return "0"
    return str(simplified).replace("**", "^")


def _expr_tuple_to_coords(exprs: tuple[sp.Expr, ...]) -> tuple[float, ...]:
    return tuple(_expr_float(expr) for expr in exprs)


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def _build_point_index(scene: MathScene) -> dict[str, Point2D | Point3D]:
    return {obj.name: obj for obj in scene.objects if isinstance(obj, (Point2D, Point3D))}


def _build_circle_index(scene: MathScene) -> dict[str, Circle2D]:
    return {obj.name: obj for obj in scene.objects if isinstance(obj, Circle2D) and obj.name}


def _build_sphere_index(scene: MathScene) -> dict[str, Sphere]:
    return {obj.name: obj for obj in scene.objects if isinstance(obj, Sphere) and obj.name}


# ---------------------------------------------------------------------------
# Token parsers
# ---------------------------------------------------------------------------


def _parse_segment_token(token: str) -> tuple[str, str] | None:
    if not token:
        return None
    token = token.strip()
    if "-" in token:
        parts = [p for p in token.split("-") if p]
        if len(parts) == 2 and all(len(p) >= 1 for p in parts):
            return parts[0], parts[1]
    if len(token) == 2 and token[0].isupper() and token[1].isupper():
        return token[0], token[1]
    return None


def _parse_plane_token(token: str) -> list[str] | None:
    """Parse 'plane(ABCD)' hoặc '(ABCD)' → ['A', 'B', 'C', 'D']."""
    if not token:
        return None
    token = token.strip()
    if token.startswith("plane(") and token.endswith(")"):
        inside = token[6:-1].strip()
    elif token.startswith("(") and token.endswith(")"):
        inside = token[1:-1].strip()
    else:
        return None
    if not inside:
        return None
    return [c for c in inside if c.isupper()]


def _parse_point_list(token: str) -> list[str]:
    """Parse 'A,B,C' hoặc 'ABC' → ['A','B','C']."""
    if not token:
        return []
    token = token.strip()
    if "," in token:
        return [p.strip() for p in token.split(",") if p.strip()]
    if " " in token:
        return [p.strip() for p in token.split(" ") if p.strip()]
    return [c for c in token if c.isupper()]


def _segment_vector(
    points: dict[str, Point2D | Point3D], a: str, b: str
) -> tuple[float, ...] | None:
    pa = points.get(a)
    pb = points.get(b)
    if pa is None or pb is None:
        return None
    if type(pa) is not type(pb):
        return None
    return _vec_sub(_coords(pb), _coords(pa))


def _plane_normal(
    points: dict[str, Point2D | Point3D], names: list[str]
) -> tuple[float, float, float] | None:
    """Tính pháp tuyến mặt phẳng từ >=3 điểm 3D không thẳng hàng."""
    coords = [_coords(points[name]) for name in names if isinstance(points.get(name), Point3D)]
    plane = plane_from_points(coords, REL_EPS)
    if plane is None:
        return None
    return to_tuple(plane[1])


# ---------------------------------------------------------------------------
# Verifiers (đã có)
# ---------------------------------------------------------------------------


def _verify_perpendicular(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    seg1 = _parse_segment_token(rel.object_1)
    obj2 = rel.object_2 or ""
    plane = _parse_plane_token(obj2)

    if seg1 and plane:
        v = _segment_vector(points, *seg1)
        n = _plane_normal(points, plane)
        if v is None or n is None or len(v) != 3:
            return None
        cross = _cross3(v, n)  # type: ignore[arg-type]
        if _length(cross) > REL_EPS * max(_length(v) * _length(n), 1.0):
            return CasIssue(
                relation_type="perpendicular",
                description=(
                    f"Đoạn {seg1[0]}{seg1[1]} không vuông góc với mặt phẳng "
                    f"({''.join(plane)}) (|v×n| = {_length(cross):.4f})"
                ),
            )
        return None

    seg2 = _parse_segment_token(obj2)
    if seg1 and seg2:
        v1 = _segment_vector(points, *seg1)
        v2 = _segment_vector(points, *seg2)
        if v1 is None or v2 is None:
            return None
        d = _dot(v1, v2)
        l1, l2 = _length(v1), _length(v2)
        if l1 < REL_EPS or l2 < REL_EPS:
            return None
        if abs(d) > REL_EPS * l1 * l2:
            return CasIssue(
                relation_type="perpendicular",
                description=(
                    f"Đoạn {seg1[0]}{seg1[1]} và {seg2[0]}{seg2[1]} không vuông góc "
                    f"(cos = {d / (l1 * l2):.4f})"
                ),
            )
    return None


def _verify_parallel(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    seg1 = _parse_segment_token(rel.object_1)
    seg2 = _parse_segment_token(rel.object_2 or "")
    if not (seg1 and seg2):
        return None
    v1 = _segment_vector(points, *seg1)
    v2 = _segment_vector(points, *seg2)
    if v1 is None or v2 is None:
        return None
    l1, l2 = _length(v1), _length(v2)
    if l1 < REL_EPS or l2 < REL_EPS:
        return None
    if len(v1) == 3 and len(v2) == 3:
        cross = _cross3(v1, v2)  # type: ignore[arg-type]
        if _length(cross) > REL_EPS * l1 * l2:
            return CasIssue(
                relation_type="parallel",
                description=(
                    f"{seg1[0]}{seg1[1]} không song song với {seg2[0]}{seg2[1]} "
                    f"(|v1×v2| = {_length(cross):.4f})"
                ),
            )
    elif len(v1) == 2 and len(v2) == 2:
        cz = v1[0] * v2[1] - v1[1] * v2[0]
        if abs(cz) > REL_EPS * l1 * l2:
            return CasIssue(
                relation_type="parallel",
                description=(
                    f"{seg1[0]}{seg1[1]} không song song với {seg2[0]}{seg2[1]} "
                    f"(cross2D = {cz:.4f})"
                ),
            )
    return None


def _verify_equal_length(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    seg1 = _parse_segment_token(rel.object_1)
    seg2 = _parse_segment_token(rel.object_2 or "")
    if not (seg1 and seg2):
        return None
    v1 = _segment_vector(points, *seg1)
    v2 = _segment_vector(points, *seg2)
    if v1 is None or v2 is None:
        return None
    l1, l2 = _length(v1), _length(v2)
    if max(l1, l2) < REL_EPS:
        return None
    if abs(l1 - l2) > REL_EPS * max(l1, l2):
        return CasIssue(
            relation_type="equal_length",
            description=(
                f"|{seg1[0]}{seg1[1]}| = {l1:.4f} ≠ |{seg2[0]}{seg2[1]}| = {l2:.4f}"
            ),
        )
    return None


def _verify_midpoint(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = M (tên điểm), object_2 = 'A-B' hoặc 'AB'."""
    m_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    if not (m_name and seg):
        return None
    m = points.get(m_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if m is None or a is None or b is None:
        return None
    if not (type(m) is type(a) is type(b)):
        return None
    expected = tuple((ai + bi) / 2 for ai, bi in zip(_coords(a), _coords(b), strict=False))
    actual = _coords(m)
    diff = sqrt(sum((ai - bi) ** 2 for ai, bi in zip(expected, actual, strict=False)))
    seg_len = _length(_vec_sub(_coords(b), _coords(a)))
    if diff > REL_EPS * max(seg_len, 1.0):
        return CasIssue(
            relation_type="midpoint",
            description=(
                f"Điểm {m_name} lệch khỏi trung điểm {seg[0]}{seg[1]} "
                f"(lệch {diff:.4f})"
            ),
            metadata={"point": m_name, "expected": expected, "segment": seg},
        )
    return None


# ---------------------------------------------------------------------------
# Verifiers (mới)
# ---------------------------------------------------------------------------


def _verify_collinear(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 chứa danh sách >=3 tên điểm. Vd 'A,B,C' hoặc 'ABC'."""
    names = _parse_point_list(rel.object_1 or "")
    extra = _parse_point_list(rel.object_2 or "")
    if extra:
        names.extend(extra)
    names = [n for n in names if n in points]
    if len(names) < 3:
        return None
    p0 = _coords(points[names[0]])
    p1 = _coords(points[names[1]])
    base = _vec_sub(p1, p0)
    if _length(base) < REL_EPS:
        return None
    base3 = _to_3d(base)
    for name in names[2:]:
        v = _vec_sub(_coords(points[name]), p0)
        v3 = _to_3d(v)
        cross = _cross3(base3, v3)
        norm = _length(cross)
        if norm > REL_EPS * max(_length(base) * _length(v), 1.0):
            return CasIssue(
                relation_type="collinear",
                description=(
                    f"Các điểm {','.join(names)} không thẳng hàng "
                    f"(điểm {name} lệch, |cross| = {norm:.4f})"
                ),
                metadata={"points": names, "outlier": name, "anchor": names[:2]},
            )
    return None


def _verify_coplanar(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    names = _parse_point_list(rel.object_1 or "")
    extra = _parse_point_list(rel.object_2 or "")
    if extra:
        names.extend(extra)
    names = [n for n in names if isinstance(points.get(n), Point3D)]
    if len(names) < 4:
        return None
    p0 = _coords(points[names[0]])
    # Tìm 2 vector độc lập từ p0 → tính pháp tuyến mặt phẳng
    base_vectors: list[tuple[float, ...]] = []
    normal: tuple[float, float, float] | None = None
    for name in names[1:]:
        v = _vec_sub(_coords(points[name]), p0)
        if _length(v) < REL_EPS:
            continue
        if not base_vectors:
            base_vectors.append(v)
            continue
        cross = _cross3(_to_3d(base_vectors[0]), _to_3d(v))
        if _length(cross) > REL_EPS:
            base_vectors.append(v)
            normal = cross
            break
    if normal is None or len(base_vectors) < 2:
        return None
    n_len = _length(normal)
    for name in names[1:]:
        v = _vec_sub(_coords(points[name]), p0)
        offset = abs(_dot(v, normal)) / max(n_len, REL_EPS)
        if offset > REL_EPS * max(_length(v), 1.0):
            return CasIssue(
                relation_type="coplanar",
                description=(
                    f"Các điểm {','.join(names)} không đồng phẳng "
                    f"(điểm {name} lệch {offset:.4f})"
                ),
                metadata={"points": names, "outlier": name, "anchor": names[0]},
            )
    return None


def _verify_on_line(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = tên điểm P; object_2 = 'A-B' hoặc 'AB' (đường thẳng)."""
    p_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    if not (p_name and seg):
        return None
    p = points.get(p_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if p is None or a is None or b is None:
        return None
    if not (type(p) is type(a) is type(b)):
        return None
    base = _vec_sub(_coords(b), _coords(a))
    if _length(base) < REL_EPS:
        return None
    v = _vec_sub(_coords(p), _coords(a))
    cross = _cross3(_to_3d(base), _to_3d(v))
    norm = _length(cross)
    base_len = _length(base)
    if norm > REL_EPS * max(base_len * _length(v), 1.0):
        # Tính foot để auto-fix
        t = _dot(v, base) / (base_len * base_len)
        foot = _vec_add(_coords(a), _vec_scale(base, t))
        return CasIssue(
            relation_type="on_line",
            description=(
                f"Điểm {p_name} không nằm trên đường thẳng {seg[0]}{seg[1]} "
                f"(lệch {norm / base_len:.4f})"
            ),
            metadata={"point": p_name, "expected": foot, "line": seg},
        )
    return None


def _verify_on_plane(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = tên điểm P; object_2 = 'plane(ABC)' hoặc '(ABC)'."""
    p_name = (rel.object_1 or "").strip()
    plane = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
    if not (p_name and plane and len(plane) >= 3):
        return None
    p = points.get(p_name)
    if not isinstance(p, Point3D):
        return None
    n = _plane_normal(points, plane)
    if n is None:
        return None
    p0 = _coords(points[plane[0]])
    v = _vec_sub(_coords(p), p0)
    n_len = _length(n)
    if n_len < REL_EPS:
        return None
    offset = _dot(v, n) / n_len  # signed distance
    abs_off = abs(offset)
    if abs_off > REL_EPS * max(_length(v), 1.0):
        # Auto-fix: project P xuống mặt phẳng
        n_unit = _vec_scale(n, 1.0 / n_len)
        foot = _vec_sub(_coords(p), _vec_scale(n_unit, offset))
        return CasIssue(
            relation_type="on_plane",
            description=(
                f"Điểm {p_name} không nằm trên mặt phẳng ({''.join(plane)}) "
                f"(lệch {abs_off:.4f})"
            ),
            metadata={"point": p_name, "expected": foot, "plane": plane},
        )
    return None


def _verify_on_sphere(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    spheres: dict[str, Sphere],
) -> CasIssue | None:
    """object_1 = tên điểm; object_2 = tên mặt cầu."""
    p_name = (rel.object_1 or "").strip()
    sphere_name = (rel.object_2 or "").strip()
    if not (p_name and sphere_name):
        return None
    p = points.get(p_name)
    sphere = spheres.get(sphere_name)
    if p is None or sphere is None:
        return None
    if not isinstance(p, Point3D):
        return None
    center = points.get(sphere.center)
    if not isinstance(center, Point3D):
        return None
    radius = sphere.radius
    if radius is None or radius <= 0:
        return None
    diff = _vec_sub(_coords(p), _coords(center))
    dist = _length(diff)
    if abs(dist - radius) > REL_EPS * max(radius, 1.0):
        # Auto-fix: scale diff về đúng bán kính
        if dist < REL_EPS:
            return CasIssue(
                relation_type="on_sphere",
                description=f"Điểm {p_name} trùng tâm mặt cầu {sphere_name}",
            )
        scale = radius / dist
        expected = _vec_add(_coords(center), _vec_scale(diff, scale))
        return CasIssue(
            relation_type="on_sphere",
            description=(
                f"Điểm {p_name} có khoảng cách đến tâm = {dist:.4f}, không bằng "
                f"bán kính {radius:.4f} của mặt cầu {sphere_name}"
            ),
            metadata={"point": p_name, "expected": expected, "sphere": sphere_name},
        )
    return None


def _verify_on_circle(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    circles: dict[str, Circle2D],
) -> CasIssue | None:
    p_name = (rel.object_1 or "").strip()
    circle_name = (rel.object_2 or "").strip()
    if not (p_name and circle_name):
        return None
    p = points.get(p_name)
    circle = circles.get(circle_name)
    if p is None or circle is None:
        return None
    if not isinstance(p, Point2D):
        return None
    center = points.get(circle.center)
    if not isinstance(center, Point2D):
        return None
    radius = circle.radius
    if radius is None and circle.through:
        through_pt = points.get(circle.through)
        if isinstance(through_pt, Point2D):
            radius = _length(_vec_sub(_coords(through_pt), _coords(center)))
    if radius is None or radius <= 0:
        return None
    diff = _vec_sub(_coords(p), _coords(center))
    dist = _length(diff)
    if abs(dist - radius) > REL_EPS * max(radius, 1.0):
        if dist < REL_EPS:
            return CasIssue(
                relation_type="on_circle",
                description=f"Điểm {p_name} trùng tâm đường tròn {circle_name}",
            )
        scale = radius / dist
        expected = _vec_add(_coords(center), _vec_scale(diff, scale))
        return CasIssue(
            relation_type="on_circle",
            description=(
                f"Điểm {p_name} có khoảng cách đến tâm = {dist:.4f}, không bằng "
                f"bán kính {radius:.4f} của đường tròn {circle_name}"
            ),
            metadata={"point": p_name, "expected": expected, "circle": circle_name},
        )
    return None


def _verify_tangent(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    circles: dict[str, Circle2D],
    spheres: dict[str, Sphere],
) -> CasIssue | None:
    """object_1 = tên đường (line/segment 'A-B' hoặc tên line) hoặc tên đường;
    object_2 = tên đường tròn / mặt cầu.
    """
    line_token = rel.object_1 or ""
    target_name = (rel.object_2 or "").strip()
    seg = _parse_segment_token(line_token)
    if not seg:
        return None
    a = points.get(seg[0])
    b = points.get(seg[1])
    if a is None or b is None:
        return None

    if target_name in circles:
        circle = circles[target_name]
        center = points.get(circle.center)
        if not isinstance(center, Point2D) or not isinstance(a, Point2D) or not isinstance(b, Point2D):
            return None
        radius = circle.radius
        if radius is None and circle.through:
            through_pt = points.get(circle.through)
            if isinstance(through_pt, Point2D):
                radius = _length(_vec_sub(_coords(through_pt), _coords(center)))
        if radius is None or radius <= 0:
            return None
        # Khoảng cách điểm-đường thẳng 2D
        ab = _vec_sub(_coords(b), _coords(a))
        ac = _vec_sub(_coords(center), _coords(a))
        ab_len = _length(ab)
        if ab_len < REL_EPS:
            return None
        cz = ab[0] * ac[1] - ab[1] * ac[0]
        dist = abs(cz) / ab_len
        if abs(dist - radius) > REL_EPS * max(radius, 1.0):
            return CasIssue(
                relation_type="tangent",
                description=(
                    f"Đường {seg[0]}{seg[1]} không tiếp tuyến đường tròn {target_name} "
                    f"(d = {dist:.4f}, r = {radius:.4f})"
                ),
            )
        return None

    if target_name in spheres:
        sphere = spheres[target_name]
        center = points.get(sphere.center)
        if not isinstance(center, Point3D) or not isinstance(a, Point3D) or not isinstance(b, Point3D):
            return None
        if sphere.radius is None or sphere.radius <= 0:
            return None
        ab = _vec_sub(_coords(b), _coords(a))
        ac = _vec_sub(_coords(center), _coords(a))
        ab_len = _length(ab)
        if ab_len < REL_EPS:
            return None
        cross = _cross3(_to_3d(ab), _to_3d(ac))
        dist = _length(cross) / ab_len
        if abs(dist - sphere.radius) > REL_EPS * max(sphere.radius, 1.0):
            return CasIssue(
                relation_type="tangent",
                description=(
                    f"Đường {seg[0]}{seg[1]} không tiếp tuyến mặt cầu {target_name} "
                    f"(d = {dist:.4f}, r = {sphere.radius:.4f})"
                ),
            )
        return None
    return None


def _verify_distance(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """Quan hệ distance với metadata.value: |AB| == value."""
    seg = _parse_segment_token(rel.object_1 or "")
    if not seg:
        seg = _parse_segment_token(rel.object_2 or "")
    if not seg:
        return None
    expected_value = rel.metadata.get("value") if rel.metadata else None
    if not isinstance(expected_value, (int, float)) or expected_value <= 0:
        return None
    v = _segment_vector(points, *seg)
    if v is None:
        return None
    actual = _length(v)
    if abs(actual - expected_value) > REL_EPS * max(expected_value, 1.0):
        return CasIssue(
            relation_type="distance",
            description=(
                f"|{seg[0]}{seg[1]}| = {actual:.4f} ≠ giá trị đề bài {expected_value}"
            ),
        )
    return None


def _verify_angle(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """Góc giữa hai đoạn: object_1 và object_2 là 'A-B'/'AB'.

    metadata.value (đơn vị độ) là số đo mong muốn.
    """
    seg1 = _parse_segment_token(rel.object_1 or "")
    seg2 = _parse_segment_token(rel.object_2 or "")
    if not (seg1 and seg2):
        return None
    expected_deg = rel.metadata.get("value") if rel.metadata else None
    if not isinstance(expected_deg, (int, float)):
        return None
    v1 = _segment_vector(points, *seg1)
    v2 = _segment_vector(points, *seg2)
    if v1 is None or v2 is None:
        return None
    l1, l2 = _length(v1), _length(v2)
    if l1 < REL_EPS or l2 < REL_EPS:
        return None
    cos_val = max(-1.0, min(1.0, _dot(v1, v2) / (l1 * l2)))
    actual_deg = degrees(acos(cos_val))
    if abs(actual_deg - expected_deg) > 1e-3:  # 0.001°
        return CasIssue(
            relation_type="angle",
            description=(
                f"Góc giữa {seg1[0]}{seg1[1]} và {seg2[0]}{seg2[1]} = "
                f"{actual_deg:.3f}° ≠ {expected_deg}°"
            ),
        )
    return None


def _verify_point_on_segment(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = tên điểm P; object_2 = 'A-B' hoặc 'AB' (đoạn thẳng).

    Khác on_line: yêu cầu P nằm GIỮA A và B (0 <= t <= 1).
    """
    p_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    if not (p_name and seg):
        return None
    p = points.get(p_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if p is None or a is None or b is None:
        return None
    if not (type(p) is type(a) is type(b)):
        return None
    base = _vec_sub(_coords(b), _coords(a))
    base_len = _length(base)
    if base_len < REL_EPS:
        return None
    v = _vec_sub(_coords(p), _coords(a))
    cross = _cross3(_to_3d(base), _to_3d(v))
    dist = _length(cross) / base_len
    if dist > REL_EPS * max(base_len, 1.0):
        t = _dot(v, base) / (base_len * base_len)
        t_clamped = max(0.0, min(1.0, t))
        foot = _vec_add(_coords(a), _vec_scale(base, t_clamped))
        return CasIssue(
            relation_type="point_on_segment",
            description=(
                f"Điểm {p_name} không nằm trên đoạn {seg[0]}{seg[1]} "
                f"(lệch {dist:.4f})"
            ),
            metadata={"point": p_name, "expected": foot, "segment": seg},
        )
    # On the line — check 0 <= t <= 1
    t = _dot(v, base) / (base_len * base_len)
    if t < -REL_EPS or t > 1.0 + REL_EPS:
        t_clamped = max(0.0, min(1.0, t))
        foot = _vec_add(_coords(a), _vec_scale(base, t_clamped))
        return CasIssue(
            relation_type="point_on_segment",
            description=(
                f"Điểm {p_name} nằm trên đường thẳng {seg[0]}{seg[1]} "
                f"nhưng ngoài đoạn (t = {t:.4f})"
            ),
            metadata={"point": p_name, "expected": foot, "segment": seg},
        )
    return None


def _verify_line_in_plane(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = 'AB' (đường thẳng); object_2 = 'plane(ABCD)' hoặc '(ABC)' (mặt phẳng).

    Kiểm tra cả hai đầu mút của đường thẳng đều nằm trên mặt phẳng.
    """
    seg = _parse_segment_token(rel.object_1 or "")
    plane = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
    if not (seg and plane and len(plane) >= 3):
        return None
    p1 = points.get(seg[0])
    p2 = points.get(seg[1])
    if not (isinstance(p1, Point3D) and isinstance(p2, Point3D)):
        return None
    n = _plane_normal(points, plane)
    if n is None:
        return None
    p0 = _coords(points[plane[0]])
    n_len = _length(n)
    if n_len < REL_EPS:
        return None
    offsets = []
    for name, pt in [(seg[0], p1), (seg[1], p2)]:
        v = _vec_sub(_coords(pt), p0)
        off = abs(_dot(v, n) / n_len)
        offsets.append((name, off))
    max_off = max(off for _, off in offsets)
    if max_off > REL_EPS * max(_length(_vec_sub(_coords(p2), _coords(p1))), 1.0):
        bad = [name for name, off in offsets if off > REL_EPS]
        return CasIssue(
            relation_type="line_in_plane",
            description=(
                f"Đường thẳng {seg[0]}{seg[1]} không nằm trong mặt phẳng "
                f"({''.join(plane)}) (điểm lệch: {', '.join(bad)}, max = {max_off:.4f})"
            ),
        )
    return None


def _verify_parallel_planes(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = 'plane(ABC)' / '(ABC)'; object_2 = 'plane(DEF)' / '(DEF)'."""
    plane1 = _parse_plane_token(rel.object_1 or "") or _parse_point_list(rel.object_1 or "")
    plane2 = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
    if not (plane1 and plane2 and len(plane1) >= 3 and len(plane2) >= 3):
        return None
    n1 = _plane_normal(points, plane1)
    n2 = _plane_normal(points, plane2)
    if n1 is None or n2 is None:
        return None
    l1, l2 = _length(n1), _length(n2)
    if l1 < REL_EPS or l2 < REL_EPS:
        return None
    cross = _cross3(n1, n2)
    if _length(cross) > REL_EPS * l1 * l2:
        return CasIssue(
            relation_type="parallel_planes",
            description=(
                f"Mặt phẳng ({''.join(plane1)}) không song song với "
                f"({''.join(plane2)}) (|n1×n2| = {_length(cross):.4f})"
            ),
        )
    return None


def _verify_perpendicular_planes(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """object_1 = 'plane(ABC)' / '(ABC)'; object_2 = 'plane(DEF)' / '(DEF)'."""
    plane1 = _parse_plane_token(rel.object_1 or "") or _parse_point_list(rel.object_1 or "")
    plane2 = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
    if not (plane1 and plane2 and len(plane1) >= 3 and len(plane2) >= 3):
        return None
    n1 = _plane_normal(points, plane1)
    n2 = _plane_normal(points, plane2)
    if n1 is None or n2 is None:
        return None
    l1, l2 = _length(n1), _length(n2)
    if l1 < REL_EPS or l2 < REL_EPS:
        return None
    d = _dot(n1, n2)
    if abs(d) > REL_EPS * l1 * l2:
        return CasIssue(
            relation_type="perpendicular_planes",
            description=(
                f"Mặt phẳng ({''.join(plane1)}) không vuông góc với "
                f"({''.join(plane2)}) (cos = {d / (l1 * l2):.4f})"
            ),
        )
    return None


def _verify_ratio(
    rel: Relation, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """Tỉ lệ chia đoạn: P chia AB theo tỉ lệ metadata.value.

    object_1 = tên điểm P; object_2 = 'A-B' hoặc 'AB'.
    metadata.value = t (P = A + t*(B-A)), hoặc
    metadata.ratio = "m:n" hoặc "m/n" (PA/PB = m/n → t = m/(m+n)).
    """
    p_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    if not (p_name and seg):
        return None
    meta = rel.metadata or {}
    # Parse expected t
    expected_t: float | None = None
    if "value" in meta:
        try:
            expected_t = float(meta["value"])
        except (TypeError, ValueError):
            pass
    elif "ratio" in meta:
        ratio_str = str(meta["ratio"])
        if ":" in ratio_str:
            parts = ratio_str.split(":")
            if len(parts) == 2:
                try:
                    m, n = float(parts[0]), float(parts[1])
                    if abs(m + n) > REL_EPS:
                        expected_t = m / (m + n)
                except (TypeError, ValueError):
                    pass
        elif "/" in ratio_str:
            parts = ratio_str.split("/")
            if len(parts) == 2:
                try:
                    m, n = float(parts[0]), float(parts[1])
                    if abs(m + n) > REL_EPS:
                        expected_t = m / (m + n)
                except (TypeError, ValueError):
                    pass
    elif "t" in meta:
        try:
            expected_t = float(meta["t"])
        except (TypeError, ValueError):
            pass
    if expected_t is None:
        return None
    p = points.get(p_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if p is None or a is None or b is None:
        return None
    if not (type(p) is type(a) is type(b)):
        return None
    base = _vec_sub(_coords(b), _coords(a))
    base_len = _length(base)
    if base_len < REL_EPS:
        return None
    v = _vec_sub(_coords(p), _coords(a))
    actual_t = _dot(v, base) / (base_len * base_len)
    if abs(actual_t - expected_t) > REL_EPS * max(abs(expected_t), 1.0):
        expected_pos = _vec_add(_coords(a), _vec_scale(base, expected_t))
        return CasIssue(
            relation_type="ratio",
            description=(
                f"Điểm {p_name} chia đoạn {seg[0]}{seg[1]} với t = {actual_t:.4f} "
                f"≠ kỳ vọng {expected_t:.4f}"
            ),
            metadata={"point": p_name, "expected": expected_pos, "segment": seg},
        )
    return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def verify_scene(scene: MathScene) -> list[CasIssue]:
    """Kiểm tra mọi relation trong scene; trả issues nếu vi phạm số học.

    Bao gồm cả check planarity cho Face/Plane object có ≥4 điểm — phát hiện
    LLM gán các đỉnh không đồng phẳng vào cùng một mặt.
    """
    points = _build_point_index(scene)
    circles = _build_circle_index(scene)
    spheres = _build_sphere_index(scene)
    issues: list[CasIssue] = []
    for rel in scene.relations:
        try:
            issue = _dispatch(rel, points, circles, spheres)
        except Exception:  # pragma: no cover - defensive
            issue = None
        if issue is not None:
            issues.append(issue)

    # Pass thứ 2: kiểm tra planarity của Face/Plane (không gắn với relation)
    for obj in scene.objects:
        if isinstance(obj, (Face, Plane)) and len(obj.points) >= 4:
            issue = _verify_face_planarity(obj, points)
            if issue is not None:
                issues.append(issue)
    return issues


def _verify_face_planarity(
    face: Face | Plane, points: dict[str, Point2D | Point3D]
) -> CasIssue | None:
    """SVD-based planarity: tính singular value thứ 3 (RMS distance đến mặt phẳng best-fit).

    Chỉ chạy khi đủ 4 Point3D hợp lệ. Threshold = REL_EPS * bbox_diagonal.
    """
    coords: list[tuple[float, float, float]] = []
    for name in face.points:
        point = points.get(name)
        if isinstance(point, Point3D):
            coords.append(_coords(point))  # type: ignore[arg-type]
    if len(coords) < 4:
        return None
    arr = np.asarray(coords, dtype=float)
    centered = arr - arr.mean(axis=0)
    try:
        _, sv, _ = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    if len(sv) < 3:
        return None
    diag = float(np.linalg.norm(arr.max(axis=0) - arr.min(axis=0)))
    threshold = REL_EPS * max(diag, 1.0)
    if sv[2] > threshold:
        return CasIssue(
            relation_type="planarity",
            description=(
                f"Face/Plane {face.name or '?'} ({','.join(face.points)}) không đồng phẳng "
                f"(RMS lệch = {sv[2]:.4f}, ngưỡng {threshold:.4f})"
            ),
            metadata={"face": face.name, "points": list(face.points), "rms": sv[2]},
        )
    return None


def _dispatch(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    circles: dict[str, Circle2D],
    spheres: dict[str, Sphere],
) -> CasIssue | None:
    rtype = rel.type.strip().lower()
    if rtype == "perpendicular":
        return _verify_perpendicular(rel, points)
    if rtype == "parallel":
        return _verify_parallel(rel, points)
    if rtype == "equal_length":
        return _verify_equal_length(rel, points)
    if rtype == "midpoint":
        return _verify_midpoint(rel, points)
    if rtype == "collinear":
        return _verify_collinear(rel, points)
    if rtype == "coplanar":
        return _verify_coplanar(rel, points)
    if rtype == "on_line":
        return _verify_on_line(rel, points)
    if rtype == "on_plane":
        return _verify_on_plane(rel, points)
    if rtype == "on_sphere":
        return _verify_on_sphere(rel, points, spheres)
    if rtype == "on_circle":
        return _verify_on_circle(rel, points, circles)
    if rtype == "tangent":
        return _verify_tangent(rel, points, circles, spheres)
    if rtype == "distance":
        return _verify_distance(rel, points)
    if rtype == "angle":
        return _verify_angle(rel, points)
    if rtype == "point_on_segment":
        return _verify_point_on_segment(rel, points)
    if rtype == "line_in_plane":
        return _verify_line_in_plane(rel, points)
    if rtype in {"parallel_planes", "parallel_plane_plane"}:
        return _verify_parallel_planes(rel, points)
    if rtype in {"perpendicular_planes", "perpendicular_plane_plane"}:
        return _verify_perpendicular_planes(rel, points)
    if rtype in {"ratio", "segment_ratio", "ratio_length"}:
        return _verify_ratio(rel, points)
    return None


def infer_point_coordinates(scene: MathScene) -> tuple[MathScene, list[CasIssue]]:
    points = _build_point_index(scene)
    updates: dict[str, tuple[sp.Expr, ...]] = {}
    issues: list[CasIssue] = []

    for rel in scene.relations:
        rtype = rel.type.strip().lower()
        if rtype == "midpoint":
            _infer_midpoint(rel, points, updates, issues)
        elif rtype == "on_line":
            _infer_on_line(rel, points, updates, issues)
        elif rtype == "on_plane":
            _infer_on_plane(rel, points, updates, issues)

    if not updates:
        return scene, issues

    data = scene.model_dump()
    for obj in data.get("objects", []):
        name = obj.get("name")
        exprs = updates.get(name)
        if exprs is None:
            continue
        _apply_expr_update(obj, exprs)

    return MathScene.model_validate(data), issues


def _infer_midpoint(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    updates: dict[str, tuple[sp.Expr, ...]],
    issues: list[CasIssue],
) -> None:
    m_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    if not (m_name and seg):
        return
    m = points.get(m_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if m is None or a is None or b is None or not (type(m) is type(a) is type(b)):
        return
    target = tuple(sp.simplify((ai + bi) / 2) for ai, bi in zip(_coord_expr(a), _coord_expr(b), strict=True))
    if _expr_tuple_close(_coord_expr(m), target):
        return
    updates[m_name] = target
    issues.append(CasIssue("midpoint", f"Nội suy exact {m_name} là trung điểm {seg[0]}{seg[1]}", auto_fixed=True, metadata={"point": m_name}))


def _infer_on_line(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    updates: dict[str, tuple[sp.Expr, ...]],
    issues: list[CasIssue],
) -> None:
    p_name = (rel.object_1 or "").strip()
    seg = _parse_segment_token(rel.object_2 or "")
    t_raw = rel.metadata.get("t", rel.metadata.get("ratio")) if rel.metadata else None
    if not (p_name and seg) or t_raw is None:
        return
    p = points.get(p_name)
    a = points.get(seg[0])
    b = points.get(seg[1])
    if p is None or a is None or b is None or not (type(p) is type(a) is type(b)):
        return
    try:
        t = sp.sympify(t_raw, locals=_SAFE_SYMPY_LOCALS)
    except Exception:
        return
    a_expr = _coord_expr(a)
    b_expr = _coord_expr(b)
    target = tuple(sp.simplify(ai + t * (bi - ai)) for ai, bi in zip(a_expr, b_expr, strict=True))
    if _expr_tuple_close(_coord_expr(p), target):
        return
    updates[p_name] = target
    issues.append(CasIssue("on_line", f"Nội suy exact {p_name} trên {seg[0]}{seg[1]} với t={t}", auto_fixed=True, metadata={"point": p_name}))


def _infer_on_plane(
    rel: Relation,
    points: dict[str, Point2D | Point3D],
    updates: dict[str, tuple[sp.Expr, ...]],
    issues: list[CasIssue],
) -> None:
    p_name = (rel.object_1 or "").strip()
    plane = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
    p = points.get(p_name)
    if not (p_name and plane and len(plane) >= 3) or not isinstance(p, Point3D):
        return
    anchors = [points.get(name) for name in plane[:3]]
    if not all(isinstance(item, Point3D) for item in anchors):
        return
    a, b, c = anchors  # type: ignore[misc]
    ax, ay, az = _coord_expr(a)
    bx, by, bz = _coord_expr(b)
    cx, cy, cz = _coord_expr(c)
    normal = sp.Matrix([bx - ax, by - ay, bz - az]).cross(sp.Matrix([cx - ax, cy - ay, cz - az]))
    if normal == sp.Matrix([0, 0, 0]):
        return
    px, py, pz = _coord_expr(p)
    current = [px, py, pz]
    candidates: list[tuple[float, str, tuple[sp.Expr, ...]]] = []
    for index, axis in enumerate(("x", "y", "z")):
        expr_field = getattr(p, f"{axis}_expr")
        if expr_field is not None:
            continue
        symbol = sp.Symbol(f"{p_name}_{axis}")
        candidate = list(current)
        candidate[index] = symbol
        equation = sp.simplify(normal.dot(sp.Matrix([candidate[0] - ax, candidate[1] - ay, candidate[2] - az])))
        solved = sp.solve(equation, symbol)
        if len(solved) != 1:
            continue
        target = tuple(candidate)
        target = tuple(sp.simplify(solved[0]) if i == index else sp.simplify(value) for i, value in enumerate(target))
        if _expr_tuple_close(_coord_expr(p), target):
            continue
        delta = abs(_expr_float(target[index] - current[index]))
        candidates.append((delta, axis, target))
    if not candidates:
        return
    _, axis, target = max(candidates, key=lambda item: (item[0], {"x": 0, "y": 1, "z": 2}[item[1]]))
    updates[p_name] = target
    issues.append(CasIssue("on_plane", f"Nội suy exact tọa độ {axis} của {p_name} trên plane({''.join(plane)})", auto_fixed=True, metadata={"point": p_name}))
    return


def _expr_tuple_close(actual: tuple[sp.Expr, ...], expected: tuple[sp.Expr, ...]) -> bool:
    return len(actual) == len(expected) and all(sp.simplify(a - b) == 0 for a, b in zip(actual, expected, strict=True))


def _apply_expr_update(obj: dict[str, Any], exprs: tuple[sp.Expr, ...]) -> None:
    obj["x"] = _expr_float(exprs[0])
    obj["y"] = _expr_float(exprs[1])
    obj["x_expr"] = _expr_text(exprs[0])
    obj["y_expr"] = _expr_text(exprs[1])
    if obj.get("type") == "point_3d" and len(exprs) == 3:
        obj["z"] = _expr_float(exprs[2])
        obj["z_expr"] = _expr_text(exprs[2])


# Khi một điểm bị nhiều issue ép về vị trí khác nhau, ưu tiên relation chặt
# nhất trước. Số nhỏ hơn = ưu tiên cao hơn.
_FIX_PRIORITY = {
    "midpoint": 1,    # M = (A+B)/2 — duy nhất
    "on_plane": 2,    # foot vuông góc — duy nhất với mặt phẳng cố định
    "on_line": 3,     # foot trên đoạn — duy nhất
    "point_on_segment": 3,  # same priority as on_line
    "ratio": 3,             # same priority as on_line
    "on_sphere": 4,   # scale theo direction hiện tại — phụ thuộc direction
    "on_circle": 5,   # scale theo direction hiện tại — phụ thuộc direction
}


def auto_fix_scene(scene: MathScene, *, use_optimizer: bool = True) -> tuple[MathScene, list[CasIssue]]:
    """Sửa deterministic: midpoint, on_line, on_plane, on_sphere, on_circle.

    Các quan hệ phức (perpendicular, parallel, equal_length, distance, angle,
    collinear, coplanar, tangent, planarity) được optimizer SciPy least_squares
    sửa khi vẫn còn issue sau pass deterministic. Mặc định ON từ v2; tắt bằng
    ``use_optimizer=False`` cho test đơn lẻ pass deterministic.
    """
    issues = verify_scene(scene)
    if not issues:
        return scene, issues

    # Map: point_name → (priority, expected_coords, issue_ref)
    chosen: dict[str, tuple[int, tuple[float, ...], CasIssue]] = {}

    for issue in issues:
        priority = _FIX_PRIORITY.get(issue.relation_type)
        if priority is None:
            continue
        meta = issue.metadata or {}
        m_name = meta.get("point")
        expected = meta.get("expected")
        if not isinstance(m_name, str) or expected is None:
            continue
        expected_tuple = tuple(float(v) for v in expected)
        if not all(isfinite(v) for v in expected_tuple):
            continue
        prev = chosen.get(m_name)
        if prev is None or priority < prev[0]:
            chosen[m_name] = (priority, expected_tuple, issue)

    if not chosen:
        if use_optimizer:
            optimized, optimizer_issues = _optimize_scene_constraints(scene, issues)
            if optimized is not None:
                return optimized, [*issues, *optimizer_issues]
            return scene, [*issues, *optimizer_issues]
        return scene, issues

    updates: dict[str, tuple[float, ...]] = {name: data[1] for name, data in chosen.items()}
    for _, _, issue in chosen.values():
        issue.auto_fixed = True

    data = scene.model_dump()
    for obj in data.get("objects", []):
        if obj.get("type") not in ("point_2d", "point_3d"):
            continue
        name = obj.get("name")
        if name not in updates:
            continue
        new = updates[name]
        if obj["type"] == "point_2d" and len(new) == 2:
            obj["x"], obj["y"] = new
            obj["x_expr"] = None
            obj["y_expr"] = None
        elif obj["type"] == "point_3d" and len(new) == 3:
            obj["x"], obj["y"], obj["z"] = new
            obj["x_expr"] = None
            obj["y_expr"] = None
            obj["z_expr"] = None

    fixed = MathScene.model_validate(data)
    if use_optimizer:
        optimized, optimizer_issues = _optimize_scene_constraints(fixed, verify_scene(fixed))
        if optimized is not None:
            return optimized, [*issues, *optimizer_issues]
        return fixed, [*issues, *optimizer_issues]
    return fixed, issues


_OPTIMIZER_MIN_POINTS = 3
_OPTIMIZER_MAX_POINTS = 24
_DISPLACEMENT_RATIO_THRESHOLD = 0.5  # tối đa 50% bbox_diagonal
_DISPLACEMENT_ABSOLUTE_FLOOR = 1e-3
_REGULARIZATION_WEIGHT = 1e-3


def _is_symbolic_anchor(point: Point3D) -> bool:
    """Điểm có ít nhất một toạ độ symbolic (*_expr không rỗng) → coi là cố định.

    Lý do: các điểm gốc thường được LLM gán biểu thức như "0", "a", "a*sqrt(3)/2",
    chỉ điểm phụ thuộc (trung điểm, hình chiếu) bị float hoá. Pin các anchor giúp
    optimizer không trôi toàn bộ scene khi chỉ vài điểm sai.
    """
    return any(getattr(point, f"{axis}_expr", None) for axis in ("x", "y", "z"))


def _optimize_scene_constraints(scene: MathScene, base_issues: list[CasIssue]) -> tuple[MathScene | None, list[CasIssue]]:
    point_index = _build_point_index(scene)
    point_objects = [obj for obj in scene.objects if isinstance(obj, Point3D)]
    if not (_OPTIMIZER_MIN_POINTS <= len(point_objects) <= _OPTIMIZER_MAX_POINTS):
        return None, []

    anchor_set = {p.name for p in point_objects if _is_symbolic_anchor(p)}
    free_names = [p.name for p in point_objects if p.name not in anchor_set]
    # Trường hợp mọi điểm đều symbolic: không có gì để chỉnh
    if not free_names:
        return None, []
    # Trường hợp không anchor nào: pin centroid bằng cách thêm regularization
    # (xử lý ở residuals)

    name_to_index = {name: idx for idx, name in enumerate(free_names)}
    base_vector = np.concatenate([as_vec3(_coords(point_index[name])) for name in free_names])
    base_issue_count = len(base_issues)

    all_coords = np.array([_coords(point_index[p.name]) for p in point_objects], dtype=float)
    diag = float(_bbox_diag(all_coords)) if len(all_coords) >= 2 else 1.0
    scene_scale = max(diag, 1.0)

    def unpack(values: np.ndarray) -> dict[str, np.ndarray]:
        pts: dict[str, np.ndarray] = {}
        for name, idx in name_to_index.items():
            pts[name] = values[idx * 3:idx * 3 + 3]
        for name in anchor_set:
            point = point_index.get(name)
            if isinstance(point, Point3D):
                pts[name] = as_vec3(_coords(point))
        return pts

    def relation_residuals(pts: dict[str, np.ndarray]) -> list[float]:
        residual: list[float] = []
        for rel in scene.relations:
            rtype = rel.type.strip().lower()
            if rtype in {"perpendicular", "parallel", "equal_length", "angle"}:
                seg1 = _parse_segment_token(rel.object_1)
                seg2 = _parse_segment_token(rel.object_2 or "")
                if not (seg1 and seg2 and all(name in pts for name in [*seg1, *seg2])):
                    continue
                v1 = pts[seg1[1]] - pts[seg1[0]]
                v2 = pts[seg2[1]] - pts[seg2[0]]
                l1, l2 = _length(v1), _length(v2)
                denom = max(l1 * l2, 1.0)
                if rtype == "perpendicular":
                    residual.append(_dot(v1, v2) / denom)
                elif rtype == "parallel":
                    residual.extend((_cross3(v1, v2) / denom).tolist())
                elif rtype == "equal_length":
                    residual.append((l1 - l2) / max(l1, l2, 1.0))
                else:
                    expected = rel.metadata.get("value") if rel.metadata else None
                    if isinstance(expected, (int, float)) and l1 > REL_EPS and l2 > REL_EPS:
                        expected_cos = np.cos(np.radians(float(expected)))
                        residual.append((_dot(v1, v2) / denom) - expected_cos)
            elif rtype == "distance":
                seg = _parse_segment_token(rel.object_1 or "") or _parse_segment_token(rel.object_2 or "")
                expected = rel.metadata.get("value") if rel.metadata else None
                if seg and isinstance(expected, (int, float)) and all(name in pts for name in seg):
                    residual.append((_length(pts[seg[1]] - pts[seg[0]]) - float(expected)) / max(float(expected), 1.0))
            elif rtype == "on_line":
                p_name = (rel.object_1 or "").strip()
                seg = _parse_segment_token(rel.object_2 or "")
                if p_name in pts and seg and all(name in pts for name in seg):
                    base = pts[seg[1]] - pts[seg[0]]
                    base_len = _length(base)
                    if base_len > REL_EPS:
                        residual.extend((_cross3(base, pts[p_name] - pts[seg[0]]) / max(base_len, 1.0)).tolist())
            elif rtype == "on_plane":
                p_name = (rel.object_1 or "").strip()
                plane = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
                if p_name in pts and len(plane) >= 3 and all(name in pts for name in plane[:3]):
                    normal = _cross3(pts[plane[1]] - pts[plane[0]], pts[plane[2]] - pts[plane[0]])
                    n_len = _length(normal)
                    if n_len > REL_EPS:
                        residual.append(_dot(pts[p_name] - pts[plane[0]], normal) / max(n_len, 1.0))
            elif rtype == "coplanar":
                names = _parse_point_list(rel.object_1 or "") + _parse_point_list(rel.object_2 or "")
                names = [name for name in names if name in pts]
                if len(names) >= 4:
                    normal = _cross3(pts[names[1]] - pts[names[0]], pts[names[2]] - pts[names[0]])
                    n_len = _length(normal)
                    if n_len > REL_EPS:
                        for name in names[3:]:
                            residual.append(_dot(pts[name] - pts[names[0]], normal) / max(n_len, 1.0))
            elif rtype == "collinear":
                names = _parse_point_list(rel.object_1 or "") + _parse_point_list(rel.object_2 or "")
                names = [name for name in names if name in pts]
                if len(names) >= 3:
                    base = pts[names[1]] - pts[names[0]]
                    base_len = _length(base)
                    if base_len > REL_EPS:
                        for name in names[2:]:
                            residual.extend((_cross3(base, pts[name] - pts[names[0]]) / max(base_len, 1.0)).tolist())
            elif rtype == "on_sphere":
                # Caller phải đảm bảo sphere center là Point3D đã update qua deterministic
                p_name = (rel.object_1 or "").strip()
                sphere_name = (rel.object_2 or "").strip()
                sphere = next((obj for obj in scene.objects if isinstance(obj, Sphere) and obj.name == sphere_name), None)
                if sphere is None or sphere.radius is None or sphere.radius <= 0:
                    continue
                if p_name in pts and sphere.center in pts:
                    diff = pts[p_name] - pts[sphere.center]
                    residual.append((_length(diff) - float(sphere.radius)) / max(float(sphere.radius), 1.0))
            elif rtype == "tangent":
                seg = _parse_segment_token(rel.object_1 or "")
                target_name = (rel.object_2 or "").strip()
                sphere = next((obj for obj in scene.objects if isinstance(obj, Sphere) and obj.name == target_name), None)
                if seg and sphere is not None and sphere.radius and sphere.center in pts and all(name in pts for name in seg):
                    ab = pts[seg[1]] - pts[seg[0]]
                    ac = pts[sphere.center] - pts[seg[0]]
                    ab_len = _length(ab)
                    if ab_len > REL_EPS:
                        dist = _length(_cross3(ab, ac)) / ab_len
                        residual.append((dist - float(sphere.radius)) / max(float(sphere.radius), 1.0))
            elif rtype == "point_on_segment":
                p_name = (rel.object_1 or "").strip()
                seg = _parse_segment_token(rel.object_2 or "")
                if p_name in pts and seg and all(name in pts for name in seg):
                    base = pts[seg[1]] - pts[seg[0]]
                    base_len = _length(base)
                    if base_len > REL_EPS:
                        # Same as on_line residual (collinearity)
                        residual.extend((_cross3(base, pts[p_name] - pts[seg[0]]) / max(base_len, 1.0)).tolist())
                        # Plus clamp t to [0,1]
                        t = _dot(pts[p_name] - pts[seg[0]], base) / (base_len * base_len)
                        if t < 0:
                            residual.append(-t)
                        elif t > 1:
                            residual.append(t - 1)
            elif rtype == "line_in_plane":
                seg = _parse_segment_token(rel.object_1 or "")
                plane = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
                if seg and len(plane) >= 3 and all(name in pts for name in [*seg, *plane[:3]]):
                    normal = _cross3(pts[plane[1]] - pts[plane[0]], pts[plane[2]] - pts[plane[0]])
                    n_len = _length(normal)
                    if n_len > REL_EPS:
                        for pt_name in seg:
                            residual.append(_dot(pts[pt_name] - pts[plane[0]], normal) / max(n_len, 1.0))
                        if len(plane) >= 4:
                            for name in plane[3:]:
                                if name in pts:
                                    residual.append(_dot(pts[name] - pts[plane[0]], normal) / n_len)
            elif rtype in {"parallel_planes", "parallel_plane_plane"}:
                plane1 = _parse_plane_token(rel.object_1 or "") or _parse_point_list(rel.object_1 or "")
                plane2 = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
                if plane1 and plane2 and len(plane1) >= 3 and len(plane2) >= 3:
                    all_names = [*plane1[:3], *plane2[:3]]
                    if all(name in pts for name in all_names):
                        n1 = _cross3(pts[plane1[1]] - pts[plane1[0]], pts[plane1[2]] - pts[plane1[0]])
                        n2 = _cross3(pts[plane2[1]] - pts[plane2[0]], pts[plane2[2]] - pts[plane2[0]])
                        l1, l2 = _length(n1), _length(n2)
                        denom = max(l1 * l2, 1.0)
                        if l1 > REL_EPS and l2 > REL_EPS:
                            residual.extend((_cross3(n1, n2) / denom).tolist())
                        if len(plane1) >= 4 and l1 > REL_EPS:
                            for name in plane1[3:]:
                                if name in pts:
                                    residual.append(_dot(pts[name] - pts[plane1[0]], n1) / l1)
                        if len(plane2) >= 4 and l2 > REL_EPS:
                            for name in plane2[3:]:
                                if name in pts:
                                    residual.append(_dot(pts[name] - pts[plane2[0]], n2) / l2)
            elif rtype in {"perpendicular_planes", "perpendicular_plane_plane"}:
                plane1 = _parse_plane_token(rel.object_1 or "") or _parse_point_list(rel.object_1 or "")
                plane2 = _parse_plane_token(rel.object_2 or "") or _parse_point_list(rel.object_2 or "")
                if plane1 and plane2 and len(plane1) >= 3 and len(plane2) >= 3:
                    all_names = [*plane1[:3], *plane2[:3]]
                    if all(name in pts for name in all_names):
                        n1 = _cross3(pts[plane1[1]] - pts[plane1[0]], pts[plane1[2]] - pts[plane1[0]])
                        n2 = _cross3(pts[plane2[1]] - pts[plane2[0]], pts[plane2[2]] - pts[plane2[0]])
                        l1, l2 = _length(n1), _length(n2)
                        denom = max(l1 * l2, 1.0)
                        if l1 > REL_EPS and l2 > REL_EPS:
                            residual.append(_dot(n1, n2) / denom)
                        if len(plane1) >= 4 and l1 > REL_EPS:
                            for name in plane1[3:]:
                                if name in pts:
                                    residual.append(_dot(pts[name] - pts[plane1[0]], n1) / l1)
                        if len(plane2) >= 4 and l2 > REL_EPS:
                            for name in plane2[3:]:
                                if name in pts:
                                    residual.append(_dot(pts[name] - pts[plane2[0]], n2) / l2)
            elif rtype in {"ratio", "segment_ratio", "ratio_length"}:
                p_name = (rel.object_1 or "").strip()
                seg = _parse_segment_token(rel.object_2 or "")
                meta = rel.metadata or {}
                expected_t: float | None = None
                if "value" in meta:
                    try:
                        expected_t = float(meta["value"])
                    except (TypeError, ValueError):
                        pass
                elif "ratio" in meta:
                    ratio_str = str(meta["ratio"])
                    if ":" in ratio_str:
                        parts = ratio_str.split(":")
                        if len(parts) == 2:
                            try:
                                m, n = float(parts[0]), float(parts[1])
                                if abs(m + n) > REL_EPS:
                                    expected_t = m / (m + n)
                            except (TypeError, ValueError):
                                pass
                elif "t" in meta:
                    try:
                        expected_t = float(meta["t"])
                    except (TypeError, ValueError):
                        pass
                if expected_t is not None and p_name in pts and seg and all(name in pts for name in seg):
                    base = pts[seg[1]] - pts[seg[0]]
                    base_len = _length(base)
                    if base_len > REL_EPS:
                        # Collinearity
                        residual.extend((_cross3(base, pts[p_name] - pts[seg[0]]) / max(base_len, 1.0)).tolist())
                        # Ratio
                        actual_t = _dot(pts[p_name] - pts[seg[0]], base) / (base_len * base_len)
                        residual.append(actual_t - expected_t)

        # Planarity SVD cho Face/Plane: nếu Face có >=4 điểm, residual = singular value thứ 3
        # (ý nghĩa: tổng bình phương distance từ điểm tới best-fit plane).
        for obj in scene.objects:
            if isinstance(obj, (Face, Plane)) and len(obj.points) >= 4:
                pts_xyz = [pts[name] for name in obj.points if name in pts]
                if len(pts_xyz) < 4:
                    continue
                arr = np.asarray(pts_xyz, dtype=float)
                centered = arr - arr.mean(axis=0)
                try:
                    _, sv, _ = np.linalg.svd(centered, full_matrices=False)
                except np.linalg.LinAlgError:
                    continue
                if len(sv) >= 3:
                    residual.append(sv[2] / max(scene_scale, 1.0))
        return residual

    free_count_3 = len(free_names) * 3

    def residuals(values: np.ndarray) -> np.ndarray:
        relation_values = relation_residuals(unpack(values))
        # Regularization: kéo về vị trí ban đầu (tránh nghiệm xa)
        regularization = (values - base_vector) * _REGULARIZATION_WEIGHT
        # Anchor centroid khi không có symbolic anchor: tránh trôi toàn bộ scene
        if not anchor_set:
            current_centroid = values.reshape(-1, 3).mean(axis=0)
            base_centroid = base_vector.reshape(-1, 3).mean(axis=0)
            centroid_residual = (current_centroid - base_centroid) * np.sqrt(free_count_3)
        else:
            centroid_residual = np.zeros(3)
        return np.asarray([*relation_values, *regularization, *centroid_residual], dtype=float)

    base_relation_residuals = relation_residuals(unpack(base_vector))
    if not base_relation_residuals:
        return None, []
    base_norm = float(np.linalg.norm(base_relation_residuals))
    try:
        # Tinh chỉnh scipy.optimize: dùng jac="3-point" (chính xác hơn) và loss="soft_l1" (bền vững với nhiễu)
        result = least_squares(
            residuals, base_vector,
            jac="3-point", loss="soft_l1",
            max_nfev=500, xtol=1e-10, ftol=1e-10, gtol=1e-10
        )
    except Exception as exc:  # pragma: no cover - SciPy có thể raise nhiều loại
        return None, [CasIssue("optimizer", f"SciPy least_squares lỗi: {exc}")]
    if not result.success:
        return None, [CasIssue("optimizer", f"SciPy least_squares không hội tụ: {result.message}")]
    optimized_relation_residuals = relation_residuals(unpack(result.x))
    optimized_norm = float(np.linalg.norm(optimized_relation_residuals)) if optimized_relation_residuals else 0.0
    # Yêu cầu giảm 10x hoặc về dưới ngưỡng tuyệt đối
    if optimized_norm > min(base_norm * 0.1, 1e-5):
        return None, [CasIssue("optimizer", f"Bỏ nghiệm optimizer vì residual còn lớn ({optimized_norm:.3g})")]
    displacement = float(np.max(np.abs(result.x - base_vector)))
    displacement_cap = max(scene_scale * _DISPLACEMENT_RATIO_THRESHOLD, _DISPLACEMENT_ABSOLUTE_FLOOR)
    if displacement > displacement_cap:
        return None, [CasIssue("optimizer", f"Bỏ nghiệm optimizer vì dịch chuyển quá lớn ({displacement:.3f}, cap {displacement_cap:.3f})")]

    optimized_scene = _scene_with_point_vector(scene, free_names, result.x)
    optimized_issues = verify_scene(optimized_scene)
    if len(optimized_issues) >= base_issue_count:
        return None, [CasIssue("optimizer", "Bỏ nghiệm optimizer vì không giảm số lỗi CAS")]
    fixed_issue = CasIssue(
        "optimizer",
        f"SciPy least_squares giảm lỗi CAS từ {base_issue_count} xuống {len(optimized_issues)}; "
        f"residual {base_norm:.3g} → {optimized_norm:.3g}, dịch {displacement:.3f}/{scene_scale:.2f}",
        auto_fixed=True,
        metadata={
            "anchored_points": sorted(anchor_set),
            "free_points": list(free_names),
            "displacement": displacement,
            "scene_scale": scene_scale,
        },
    )
    return optimized_scene, [fixed_issue]


def _scene_with_point_vector(scene: MathScene, point_names: list[str], values: np.ndarray) -> MathScene:
    updates = {name: values[index * 3:index * 3 + 3] for index, name in enumerate(point_names)}
    data = scene.model_dump()
    for obj in data.get("objects", []):
        if obj.get("type") != "point_3d" or obj.get("name") not in updates:
            continue
        x, y, z = updates[obj["name"]]
        obj["x"] = float(x)
        obj["y"] = float(y)
        obj["z"] = float(z)
        obj["x_expr"] = None
        obj["y_expr"] = None
        obj["z_expr"] = None
    return MathScene.model_validate(data)


__all__ = ["CasIssue", "auto_fix_scene", "infer_point_coordinates", "verify_scene"]
