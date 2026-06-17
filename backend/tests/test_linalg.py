import numpy as np
import pytest
from app.services.linalg import (
    line_direction,
    is_point_in_plane,
    are_vectors_parallel,
    segment_ratio,
    project_point_to_line,
)


def test_line_direction():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 6.0, 8.0])
    d = line_direction(a, b)
    assert np.allclose(d, [3.0, 4.0, 5.0])


def test_is_point_in_plane():
    plane_point = np.array([0.0, 0.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    
    # Point on plane
    pt_on = np.array([1.0, 2.0, 0.0])
    assert is_point_in_plane(pt_on, plane_point, normal)
    
    # Point off plane
    pt_off = np.array([1.0, 2.0, 0.1])
    assert not is_point_in_plane(pt_off, plane_point, normal)


def test_are_vectors_parallel():
    # Parallel vectors
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([2.0, 4.0, 6.0])
    assert are_vectors_parallel(a, b)
    
    # Anti-parallel vectors
    c = np.array([-1.0, -2.0, -3.0])
    assert are_vectors_parallel(a, c)
    
    # Non-parallel vectors
    d = np.array([1.0, 0.0, 0.0])
    assert not are_vectors_parallel(a, d)


def test_segment_ratio():
    start = np.array([0.0, 0.0, 0.0])
    end = np.array([4.0, 0.0, 0.0])
    
    # Midpoint (t = 0.5)
    p1 = np.array([2.0, 0.0, 0.0])
    assert np.isclose(segment_ratio(p1, start, end), 0.5)
    
    # Quarter point (t = 0.25)
    p2 = np.array([1.0, 0.0, 0.0])
    assert np.isclose(segment_ratio(p2, start, end), 0.25)
    
    # Point off line (should return None because it is not collinear)
    p3 = np.array([2.0, 1.0, 0.0])
    assert segment_ratio(p3, start, end) is None
    
    # Degenerate segment (start == end)
    assert segment_ratio(p1, start, start) is None


def test_project_point_to_line():
    start = np.array([0.0, 0.0, 0.0])
    end = np.array([4.0, 0.0, 0.0])
    
    # Point off line projected onto line
    pt = np.array([2.0, 3.0, 4.0])
    proj = project_point_to_line(pt, start, end)
    assert np.allclose(proj, [2.0, 0.0, 0.0])
    
    # Degenerate line (start == end)
    assert project_point_to_line(pt, start, start) is None
