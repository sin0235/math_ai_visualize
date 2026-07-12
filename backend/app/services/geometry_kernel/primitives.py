from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from app.schemas.scene_v3 import (
    Circle2DV3,
    FaceV3,
    Line2DV3,
    Line3DV3,
    MathSceneV3,
    PlaneV3,
    Point2DV3,
    Point3DV3,
    SceneObjectV3,
    SegmentV3,
    SphereV3,
    Vector2DV3,
    Vector3DV3,
)

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class NumericPolicy:
    relative_tolerance: float = 1e-7
    minimum_tolerance: float = 1e-9
    angular_tolerance: float = 1e-7

    def distance_tolerance(self, scale: float) -> float:
        return max(self.minimum_tolerance, abs(scale) * self.relative_tolerance)


@dataclass(frozen=True)
class GeometryIndex:
    objects: Mapping[str, SceneObjectV3]
    points: Mapping[str, Vec3]
    scale: float
    policy: NumericPolicy

    @property
    def tolerance(self) -> float:
        return self.policy.distance_tolerance(self.scale)

    def point(self, point_id: str) -> Vec3:
        try:
            return self.points[point_id]
        except KeyError as error:
            raise ValueError(f"Không tìm thấy point ID {point_id}") from error

    def line_points(self, object_id: str) -> tuple[Vec3, Vec3]:
        obj = self.objects.get(object_id)
        if isinstance(obj, (SegmentV3, Line2DV3, Line3DV3)):
            return self.point(obj.point_ids[0]), self.point(obj.point_ids[1])
        if isinstance(obj, (Vector2DV3, Vector3DV3)):
            return self.point(obj.from_point_id), self.point(obj.to_point_id)
        raise ValueError(f"Object {object_id} không phải đường/đoạn/vector")

    def plane_points(self, object_id: str) -> tuple[Vec3, ...]:
        obj = self.objects.get(object_id)
        if isinstance(obj, (PlaneV3, FaceV3)):
            return tuple(self.point(point_id) for point_id in obj.point_ids)
        raise ValueError(f"Object {object_id} không phải mặt phẳng/mặt")

    def circle(self, object_id: str) -> tuple[Vec3, float]:
        obj = self.objects.get(object_id)
        if not isinstance(obj, Circle2DV3):
            raise ValueError(f"Object {object_id} không phải đường tròn")
        center = self.point(obj.center_point_id)
        if obj.radius is not None:
            return center, obj.radius
        if obj.through_point_id:
            return center, norm(sub(self.point(obj.through_point_id), center))
        raise ValueError(f"Đường tròn {object_id} thiếu bán kính")

    def sphere(self, object_id: str) -> tuple[Vec3, float]:
        obj = self.objects.get(object_id)
        if not isinstance(obj, SphereV3):
            raise ValueError(f"Object {object_id} không phải mặt cầu")
        return self.point(obj.center_point_id), obj.radius


def build_geometry_index(scene: MathSceneV3, policy: NumericPolicy | None = None) -> GeometryIndex:
    objects = {obj.id: obj for obj in scene.objects}
    points = {
        obj.id: (obj.x, obj.y, obj.z if isinstance(obj, Point3DV3) else 0.0)
        for obj in scene.objects
        if isinstance(obj, (Point2DV3, Point3DV3))
    }
    return GeometryIndex(
        objects=MappingProxyType(objects),
        points=MappingProxyType(points),
        scale=scene_scale(tuple(points.values())),
        policy=policy or NumericPolicy(),
    )


def scene_scale(points: tuple[Vec3, ...]) -> float:
    if not points:
        return 1.0
    minimum = tuple(min(point[axis] for point in points) for axis in range(3))
    maximum = tuple(max(point[axis] for point in points) for axis in range(3))
    return max(norm(sub(maximum, minimum)), 1.0)


def add(first: Vec3, second: Vec3) -> Vec3:
    return first[0] + second[0], first[1] + second[1], first[2] + second[2]


def sub(first: Vec3, second: Vec3) -> Vec3:
    return first[0] - second[0], first[1] - second[1], first[2] - second[2]


def scale(vector: Vec3, factor: float) -> Vec3:
    return vector[0] * factor, vector[1] * factor, vector[2] * factor


def dot(first: Vec3, second: Vec3) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def cross(first: Vec3, second: Vec3) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def norm(vector: Vec3) -> float:
    return sqrt(dot(vector, vector))


def distance(first: Vec3, second: Vec3) -> float:
    return norm(sub(first, second))


def midpoint(first: Vec3, second: Vec3) -> Vec3:
    return scale(add(first, second), 0.5)


def normalized(vector: Vec3, tolerance: float) -> Vec3:
    length = norm(vector)
    if length <= tolerance:
        raise ValueError("Vector suy biến")
    return scale(vector, 1.0 / length)


def point_line_distance(point: Vec3, first: Vec3, second: Vec3, tolerance: float) -> float:
    direction = sub(second, first)
    length = norm(direction)
    if length <= tolerance:
        raise ValueError("Đường xác định bởi hai điểm trùng nhau")
    return norm(cross(sub(point, first), direction)) / length


def point_segment_parameter(point: Vec3, first: Vec3, second: Vec3, tolerance: float) -> float:
    direction = sub(second, first)
    denominator = dot(direction, direction)
    if denominator <= tolerance * tolerance:
        raise ValueError("Đoạn thẳng suy biến")
    return dot(sub(point, first), direction) / denominator


def plane_normal(points: tuple[Vec3, ...], tolerance: float) -> Vec3:
    if len(points) < 3:
        raise ValueError("Mặt phẳng cần ít nhất ba điểm")
    origin = points[0]
    for first_index in range(1, len(points) - 1):
        for second_index in range(first_index + 1, len(points)):
            candidate = cross(sub(points[first_index], origin), sub(points[second_index], origin))
            if norm(candidate) > tolerance:
                return normalized(candidate, tolerance)
    raise ValueError("Mặt phẳng suy biến")


def point_plane_distance(point: Vec3, points: tuple[Vec3, ...], tolerance: float) -> float:
    normal = plane_normal(points, tolerance)
    return abs(dot(sub(point, points[0]), normal))


def project_point_to_line(point: Vec3, first: Vec3, second: Vec3, tolerance: float, *, clamp_to_segment: bool = False) -> tuple[Vec3, float]:
    direction = sub(second, first)
    denominator = dot(direction, direction)
    if denominator <= tolerance * tolerance:
        raise ValueError("Đường/đoạn suy biến")
    parameter = dot(sub(point, first), direction) / denominator
    applied_parameter = min(1.0, max(0.0, parameter)) if clamp_to_segment else parameter
    return add(first, scale(direction, applied_parameter)), parameter


def project_point_to_plane(point: Vec3, points: tuple[Vec3, ...], tolerance: float) -> Vec3:
    normal = plane_normal(points, tolerance)
    signed_distance = dot(sub(point, points[0]), normal)
    return sub(point, scale(normal, signed_distance))


def intersect_lines(first: tuple[Vec3, Vec3], second: tuple[Vec3, Vec3], tolerance: float) -> tuple[Vec3, float, float]:
    first_origin, first_end = first
    second_origin, second_end = second
    first_direction = sub(first_end, first_origin)
    second_direction = sub(second_end, second_origin)
    normal = cross(first_direction, second_direction)
    denominator = dot(normal, normal)
    if denominator <= tolerance * tolerance:
        raise ValueError("Hai đường song song hoặc trùng nhau")
    offset = sub(second_origin, first_origin)
    first_parameter = dot(cross(offset, second_direction), normal) / denominator
    second_parameter = dot(cross(offset, first_direction), normal) / denominator
    first_point = add(first_origin, scale(first_direction, first_parameter))
    second_point = add(second_origin, scale(second_direction, second_parameter))
    if distance(first_point, second_point) > tolerance:
        raise ValueError("Hai đường chéo nhau, không có giao điểm")
    return midpoint(first_point, second_point), first_parameter, second_parameter