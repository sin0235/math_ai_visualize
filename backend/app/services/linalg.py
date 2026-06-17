from __future__ import annotations

from typing import Mapping, TypeAlias

import numpy as np

Vec3: TypeAlias = np.ndarray


def vec3(x: float, y: float, z: float) -> Vec3:
    return np.array([x, y, z], dtype=float)


def as_vector(value) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"Vector must be 1-dimensional, got {array.shape}")
    return array


def as_vec3(value) -> Vec3:
    array = as_vector(value)
    if array.shape != (3,):
        raise ValueError(f"Vec3 must have shape (3,), got {array.shape}")
    return array


def add(a, b) -> np.ndarray:
    return as_vector(a) + as_vector(b)


def sub(a, b) -> np.ndarray:
    return as_vector(a) - as_vector(b)


def scale(v, s: float) -> np.ndarray:
    return as_vector(v) * float(s)


def dot(a, b) -> float:
    return float(np.dot(as_vector(a), as_vector(b)))


def cross(a, b) -> Vec3:
    return np.cross(as_vec3(a), as_vec3(b))


def norm(v) -> float:
    return float(np.linalg.norm(as_vector(v)))


def normalize(v, eps: float = 1e-9) -> Vec3:
    size = norm(v)
    if size <= eps:
        return vec3(0.0, 0.0, 0.0)
    return scale(v, 1 / size)


def distance(a, b) -> float:
    return norm(sub(a, b))


def to_tuple(v) -> tuple[float, float, float]:
    array = as_vec3(v)
    return (float(array[0]), float(array[1]), float(array[2]))


def centroid(points) -> Vec3:
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 3 or coords.shape[0] == 0:
        raise ValueError(f"points must have shape (N, 3), got {coords.shape}")
    return coords.mean(axis=0)


def bbox_diagonal(points) -> float:
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 3 or coords.shape[0] == 0:
        raise ValueError(f"points must have shape (N, 3), got {coords.shape}")
    return distance(coords.min(axis=0), coords.max(axis=0))


def deterministic_normal_sign(normal) -> Vec3:
    result = normalize(normal)
    for value in result:
        if abs(float(value)) > 1e-12:
            return result if value > 0 else scale(result, -1)
    return result


def plane_from_points(points, eps: float = 1e-9) -> tuple[Vec3, Vec3] | None:
    coords = np.asarray(points, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 3 or coords.shape[0] < 3:
        return None
    center = coords.mean(axis=0)
    centered = coords - center
    try:
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    if len(singular_values) < 2 or singular_values[1] <= eps:
        return None
    normal = deterministic_normal_sign(vh[-1])
    if norm(normal) <= eps:
        return None
    return center, normal


def raw_plane_from_named_points(named_points: Mapping[str, Vec3], eps: float = 1e-9) -> tuple[Vec3, Vec3, tuple[str, str, str]] | None:
    names = list(named_points)
    if len(names) < 3:
        return None
    anchor_name = names[0]
    anchor = as_vec3(named_points[anchor_name])
    for i in range(1, len(names) - 1):
        for j in range(i + 1, len(names)):
            second_name = names[i]
            third_name = names[j]
            normal = cross(sub(named_points[second_name], anchor), sub(named_points[third_name], anchor))
            if norm(normal) > eps:
                return anchor, normal, (anchor_name, second_name, third_name)
    return None


def signed_distance_to_plane(point, plane_point, normal) -> float:
    unit = normalize(normal)
    return dot(unit, sub(point, plane_point))


def project_point_to_plane(point, plane_point, normal) -> Vec3:
    return sub(point, scale(normalize(normal), signed_distance_to_plane(point, plane_point, normal)))


def angle_between(a, b, eps: float = 1e-9) -> float | None:
    first_norm = norm(a)
    second_norm = norm(b)
    if first_norm <= eps or second_norm <= eps:
        return None
    ratio = float(np.clip(dot(a, b) / (first_norm * second_norm), -1.0, 1.0))
    return float(np.degrees(np.arccos(ratio)))


# ---------------------------------------------------------------------------
# Phase-4 geometry helpers
# ---------------------------------------------------------------------------


def line_direction(start, end) -> Vec3:
    """Direction vector from start to end (unnormalized)."""
    return sub(end, start)


def is_point_in_plane(point, plane_point, normal, eps: float = 1e-9) -> bool:
    """Check if point lies on the plane defined by plane_point and normal."""
    return abs(signed_distance_to_plane(point, plane_point, normal)) <= eps


def are_vectors_parallel(a, b, eps: float = 1e-9) -> bool:
    """Check if two 3D vectors are parallel (cross product ~ 0)."""
    a3 = as_vec3(a)
    b3 = as_vec3(b)
    cr = cross(a3, b3)
    return norm(cr) <= eps * max(norm(a3) * norm(b3), 1.0)


def segment_ratio(point, seg_start, seg_end, eps: float = 1e-9) -> float | None:
    """Compute parameter t such that point = seg_start + t*(seg_end - seg_start).

    Returns None if the segment is degenerate (start == end) or point is not on the line.
    """
    d = sub(seg_end, seg_start)
    d_len = norm(d)
    if d_len <= eps:
        return None
    v = sub(point, seg_start)
    # Check point is on the line
    cr = cross(as_vec3(d), as_vec3(v))
    if norm(cr) > eps * max(d_len * norm(v), 1.0):
        return None
    return dot(v, d) / (d_len * d_len)


def project_point_to_line(point, line_start, line_end, eps: float = 1e-9) -> Vec3 | None:
    """Project point onto the line through line_start and line_end.

    Returns None if line_start == line_end (degenerate).
    """
    d = sub(line_end, line_start)
    d_len = norm(d)
    if d_len <= eps:
        return None
    t = dot(sub(point, line_start), d) / (d_len * d_len)
    return add(line_start, scale(d, t))

