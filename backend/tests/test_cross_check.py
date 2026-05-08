"""Unit tests cho ``app.services.cross_check``.

Kiểm chứng rằng hai đường tính độc lập đồng thuận trên cấu hình hợp lệ và
phát hiện lệch nhau khi nhập đầu vào không nhất quán.
"""

from __future__ import annotations

import math

import pytest

from app.services.cross_check import (
    verify_point_plane_distance,
    verify_tetrahedron_volume,
    verify_triangle_area,
)


def test_point_plane_distance_consistent():
    res = verify_point_plane_distance(
        [1.0, 2.0, 3.0],
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )
    assert res.consistent
    assert math.isclose(res.primary, 3.0, rel_tol=1e-9)
    assert math.isclose(res.secondary, 3.0, rel_tol=1e-9)


def test_point_plane_distance_zero_inplane():
    res = verify_point_plane_distance(
        [0.5, 0.5, 0.0],
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )
    assert res.consistent
    assert math.isclose(res.primary, 0.0, abs_tol=1e-9)


def test_point_plane_distance_degenerate_plane():
    # 3 điểm thẳng hàng → secondary không xác định nhưng primary fail-soft
    res = verify_point_plane_distance(
        [1.0, 1.0, 1.0],
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    )
    assert not res.consistent or "degenerate" in (res.detail or "")


def test_triangle_area_consistent():
    res = verify_triangle_area(
        [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 4.0, 0.0]],
    )
    assert res.consistent
    assert math.isclose(res.primary, 6.0, rel_tol=1e-9)
    assert math.isclose(res.secondary, 6.0, rel_tol=1e-9)


def test_triangle_area_degenerate():
    res = verify_triangle_area(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    )
    assert math.isclose(res.primary, 0.0, abs_tol=1e-9)


def test_tetrahedron_volume_consistent():
    res = verify_tetrahedron_volume(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
    assert res.consistent
    assert math.isclose(res.primary, 1 / 6, rel_tol=1e-9)
    assert math.isclose(res.secondary, 1 / 6, rel_tol=1e-9)


def test_tetrahedron_volume_flat():
    # 4 điểm đồng phẳng → V = 0, secondary cũng 0 (height = 0)
    res = verify_tetrahedron_volume(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]],
    )
    assert math.isclose(res.primary, 0.0, abs_tol=1e-9)


@pytest.mark.parametrize(
    "tet",
    [
        [[0, 0, 0], [2, 0, 0], [0, 3, 0], [0, 0, 5]],
        [[1, 1, 1], [2, 1, 1], [1, 3, 1], [1, 1, 4]],
    ],
)
def test_tetrahedron_volume_various(tet):
    res = verify_tetrahedron_volume([list(map(float, p)) for p in tet])
    assert res.consistent
    assert res.primary > 0.0
