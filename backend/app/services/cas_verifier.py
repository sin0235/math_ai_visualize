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

from app.schemas.scene import (
    Circle2D,
    MathScene,
    Point2D,
    Point3D,
    Relation,
    Sphere,
)

REL_EPS = 1e-6


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


def _coords(point: Point2D | Point3D) -> tuple[float, ...]:
    if isinstance(point, Point3D):
        return (point.x, point.y, point.z)
    return (point.x, point.y)


def _vec_sub(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(ai - bi for ai, bi in zip(a, b, strict=False))


def _vec_add(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(ai + bi for ai, bi in zip(a, b, strict=False))


def _vec_scale(v: tuple[float, ...], k: float) -> tuple[float, ...]:
    return tuple(k * x for x in v)


def _length(v: tuple[float, ...]) -> float:
    return sqrt(sum(x * x for x in v))


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(ai * bi for ai, bi in zip(a, b, strict=False))


def _cross3(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _to_3d(v: tuple[float, ...]) -> tuple[float, float, float]:
    if len(v) == 3:
        return (v[0], v[1], v[2])
    return (v[0], v[1], 0.0)


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
    pts3d = [points[name] for name in names if isinstance(points.get(name), Point3D)]
    if len(pts3d) < 3:
        return None
    p0 = _coords(pts3d[0])
    for i in range(1, len(pts3d) - 1):
        for j in range(i + 1, len(pts3d)):
            v1 = _vec_sub(_coords(pts3d[i]), p0)
            v2 = _vec_sub(_coords(pts3d[j]), p0)
            n = _cross3(v1, v2)  # type: ignore[arg-type]
            if _length(n) > REL_EPS:
                return n
    return None


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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def verify_scene(scene: MathScene) -> list[CasIssue]:
    """Kiểm tra mọi relation trong scene; trả issues nếu vi phạm số học."""
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
    return issues


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
    return None


# Khi một điểm bị nhiều issue ép về vị trí khác nhau, ưu tiên relation chặt
# nhất trước. Số nhỏ hơn = ưu tiên cao hơn.
_FIX_PRIORITY = {
    "midpoint": 1,    # M = (A+B)/2 — duy nhất
    "on_plane": 2,    # foot vuông góc — duy nhất với mặt phẳng cố định
    "on_line": 3,     # foot trên đoạn — duy nhất
    "on_sphere": 4,   # scale theo direction hiện tại — phụ thuộc direction
    "on_circle": 5,   # scale theo direction hiện tại — phụ thuộc direction
}


def auto_fix_scene(scene: MathScene) -> tuple[MathScene, list[CasIssue]]:
    """Sửa deterministic: midpoint, on_line, on_plane, on_sphere, on_circle.

    Các quan hệ phức (perpendicular, parallel, equal_length, distance, angle,
    collinear, coplanar, tangent) chỉ được report làm warning vì có nhiều
    nghiệm khả dĩ — fix tự động dễ phá hỏng các ràng buộc khác.
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
        if not isinstance(m_name, str) or not isinstance(expected, tuple):
            continue
        if not all(isinstance(v, (int, float)) and isfinite(v) for v in expected):
            continue
        prev = chosen.get(m_name)
        if prev is None or priority < prev[0]:
            chosen[m_name] = (priority, tuple(expected), issue)

    if not chosen:
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
    return fixed, issues


__all__ = ["CasIssue", "auto_fix_scene", "verify_scene"]
