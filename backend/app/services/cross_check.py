"""Cross-validation hai phương pháp độc lập cho các đại lượng hình học chính.

Mục đích: phát hiện sai sót numeric (overflow, hủy số, lỗi formula) bằng cách
tính cùng một đại lượng theo hai con đường tách biệt và so sánh. Nếu lệch
> ``CROSS_TOL_RELATIVE``, ghi ``logger.warning`` để admin/dev có thể truy vết.

Các verifier:

- ``verify_point_plane_distance``: Hesse vs 3V_tetra / S_triangle.
- ``verify_triangle_area``: Heron vs |AB × AC| / 2.
- ``verify_tetrahedron_volume``: |det| / 6 vs (1/3) · S_đáy · h.

Giá trị trả về luôn là kết quả "primary" (đường thứ nhất). Đường thứ hai chỉ
là sanity. Người dùng cuối không bị fail; chỉ log nội bộ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

CROSS_TOL_RELATIVE = 1e-6
CROSS_TOL_ABSOLUTE = 1e-9


@dataclass
class CrossCheckResult:
    name: str
    primary: float
    secondary: float | None
    consistent: bool
    detail: str = ""


def _consistent(a: float, b: float) -> bool:
    if not (isfinite(a) and isfinite(b)):
        return False
    diff = abs(a - b)
    if diff <= CROSS_TOL_ABSOLUTE:
        return True
    scale = max(abs(a), abs(b), 1.0)
    return diff <= scale * CROSS_TOL_RELATIVE


def verify_point_plane_distance(
    point: Sequence[float],
    plane_points: Sequence[Sequence[float]],
) -> CrossCheckResult:
    """Tính d(P,(ABC)) theo Hesse và theo 3V/S; cảnh báo nếu lệch."""
    if len(plane_points) < 3:
        return CrossCheckResult("point_plane_distance", float("nan"), None, False, "cần ≥3 điểm mặt phẳng")

    a, b, c = (np.asarray(p, dtype=float) for p in plane_points[:3])
    p = np.asarray(point, dtype=float)
    ab, ac = b - a, c - a
    normal = np.cross(ab, ac)
    n_norm = float(np.linalg.norm(normal))
    if n_norm <= CROSS_TOL_ABSOLUTE:
        return CrossCheckResult("point_plane_distance", float("nan"), None, False, "mặt phẳng suy biến")

    primary = abs(float(np.dot(normal, p - a))) / n_norm  # Hesse

    # Secondary: 3V_tetra(P,A,B,C) / S_triangle(ABC)
    ap = p - a
    volume_6 = abs(float(np.dot(ap, np.cross(ab, ac))))  # = 6V
    triangle_area_2 = n_norm  # |AB×AC| = 2·S
    secondary = volume_6 / triangle_area_2  # = 6V / (2S) = 3V/S
    if not _consistent(primary, secondary):
        logger.warning(
            "cross_check[point_plane_distance] lệch: Hesse=%.10g vs 3V/S=%.10g (P=%s, plane=%s)",
            primary, secondary, p.tolist(), [a.tolist(), b.tolist(), c.tolist()],
        )
        return CrossCheckResult("point_plane_distance", primary, secondary, False, f"Hesse {primary:.6g} vs 3V/S {secondary:.6g}")

    return CrossCheckResult("point_plane_distance", primary, secondary, True)


def verify_triangle_area(triangle: Sequence[Sequence[float]]) -> CrossCheckResult:
    """Tính diện tích tam giác theo cross product và Heron; cảnh báo nếu lệch."""
    if len(triangle) < 3:
        return CrossCheckResult("triangle_area", float("nan"), None, False, "cần 3 điểm")
    a, b, c = (np.asarray(p, dtype=float) for p in triangle[:3])
    cross_norm = float(np.linalg.norm(np.cross(b - a, c - a)))
    primary = cross_norm / 2.0

    side_a = float(np.linalg.norm(c - b))
    side_b = float(np.linalg.norm(c - a))
    side_c = float(np.linalg.norm(b - a))
    s = (side_a + side_b + side_c) / 2.0
    radicand = s * (s - side_a) * (s - side_b) * (s - side_c)
    if radicand < -CROSS_TOL_ABSOLUTE:
        secondary = float("nan")
    else:
        secondary = sqrt(max(radicand, 0.0))

    if not _consistent(primary, secondary):
        logger.warning(
            "cross_check[triangle_area] lệch: cross=%.10g vs Heron=%.10g (A=%s, B=%s, C=%s)",
            primary, secondary, a.tolist(), b.tolist(), c.tolist(),
        )
        return CrossCheckResult("triangle_area", primary, secondary, False, f"cross {primary:.6g} vs Heron {secondary:.6g}")
    return CrossCheckResult("triangle_area", primary, secondary, True)


def verify_tetrahedron_volume(tetra: Sequence[Sequence[float]]) -> CrossCheckResult:
    """Tính V tứ diện theo |det|/6 và (1/3)·S_đáy·h; cảnh báo nếu lệch."""
    if len(tetra) < 4:
        return CrossCheckResult("tetrahedron_volume", float("nan"), None, False, "cần 4 điểm")
    a, b, c, d = (np.asarray(p, dtype=float) for p in tetra[:4])
    ab, ac, ad = b - a, c - a, d - a
    primary = abs(float(np.dot(ab, np.cross(ac, ad)))) / 6.0  # det formula

    # Secondary: (1/3) · S_ABC · d(D, plane(ABC))
    plane_normal = np.cross(ab, ac)
    n_norm = float(np.linalg.norm(plane_normal))
    if n_norm <= CROSS_TOL_ABSOLUTE:
        secondary = float("nan")
    else:
        s_base = n_norm / 2.0
        height = abs(float(np.dot(plane_normal, ad))) / n_norm
        secondary = s_base * height / 3.0

    if not _consistent(primary, secondary):
        logger.warning(
            "cross_check[tetrahedron_volume] lệch: det=%.10g vs (1/3)Sh=%.10g (vertices=%s)",
            primary, secondary, [a.tolist(), b.tolist(), c.tolist(), d.tolist()],
        )
        return CrossCheckResult("tetrahedron_volume", primary, secondary, False, f"det {primary:.6g} vs (1/3)Sh {secondary:.6g}")
    return CrossCheckResult("tetrahedron_volume", primary, secondary, True)


__all__ = [
    "CROSS_TOL_RELATIVE",
    "CrossCheckResult",
    "verify_point_plane_distance",
    "verify_tetrahedron_volume",
    "verify_triangle_area",
]
