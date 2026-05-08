"""Tests cho ``_nsimplify_latex`` và việc lan toả ``result_latex`` vào kết quả
``calculate_*``. Đảm bảo Phase 3 (SymPy exact result) hoạt động trên các giá
trị tiêu biểu trong giáo trình hình học.
"""

from __future__ import annotations

import math

import pytest

from app.services.geometry_engine import (
    _nsimplify_latex,
    calculate_point_plane_distance,
    calculate_polygon_area,
    calculate_tetrahedron_volume,
)
from app.services.linalg import vec3


@pytest.mark.parametrize(
    "value, expected_substring",
    [
        (math.sqrt(6) / 6, "sqrt"),
        (math.sqrt(3), "sqrt"),
        (1 / 2, "frac"),
        (2.0, "2"),
        (math.pi / 4, "pi"),
        (math.pi, "pi"),
    ],
)
def test_nsimplify_latex_returns_exact_for_canonical_values(value, expected_substring):
    latex = _nsimplify_latex(value)
    assert latex is not None
    assert expected_substring in latex


def test_nsimplify_latex_returns_none_for_random_irrational():
    # 0.31415926... không khớp basis nào → None hoặc rational hợp lệ
    latex = _nsimplify_latex(0.31415926)
    assert latex is None or "frac" in latex or "/" in latex


def test_nsimplify_latex_preserves_zero_and_negative():
    assert _nsimplify_latex(0.0) == "0"
    latex = _nsimplify_latex(-math.sqrt(2))
    assert latex is not None
    assert "sqrt" in latex


def test_calculate_point_plane_distance_uses_exact_latex():
    # d(A, (BCD)) với A=(0,0,0), B=(1,0,0), C=(0,1,0), D=(0,0,1)
    # plane x+y+z=1 → khoảng cách từ O tới mặt phẳng = 1/sqrt(3) = sqrt(3)/3
    points = {
        "O": vec3(0.0, 0.0, 0.0),
        "B": vec3(1.0, 0.0, 0.0),
        "C": vec3(0.0, 1.0, 0.0),
        "D": vec3(0.0, 0.0, 1.0),
    }
    res = calculate_point_plane_distance(points, "O", ["B", "C", "D"])
    assert res["status"] == "ok"
    assert res["result_value"] == pytest.approx(1 / math.sqrt(3))
    assert "sqrt" in res["result_latex"] or "frac" in res["result_latex"]


def test_calculate_tetrahedron_volume_exact_rational():
    points = {
        "A": vec3(0.0, 0.0, 0.0),
        "B": vec3(1.0, 0.0, 0.0),
        "C": vec3(0.0, 1.0, 0.0),
        "D": vec3(0.0, 0.0, 1.0),
    }
    res = calculate_tetrahedron_volume(points, ["A", "B", "C", "D"])
    assert res["status"] == "ok"
    assert res["result_value"] == pytest.approx(1 / 6)
    assert res["result_latex"] in {r"\frac{1}{6}", "1/6"} or "frac" in res["result_latex"]


def test_calculate_polygon_area_triangle_exact():
    # Tam giác đều cạnh 2 → diện tích = sqrt(3)
    points = {
        "A": vec3(0.0, 0.0, 0.0),
        "B": vec3(2.0, 0.0, 0.0),
        "C": vec3(1.0, math.sqrt(3), 0.0),
    }
    res = calculate_polygon_area(points, ["A", "B", "C"])
    assert res["status"] == "ok"
    assert res["result_value"] == pytest.approx(math.sqrt(3))
    assert "sqrt" in res["result_latex"]
