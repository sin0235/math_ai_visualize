from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.render_projection_v3 import (
    ProjectionAnnotationV3,
    ProjectionBoundsV3,
    ProjectionCircleV3,
    ProjectionFunctionV3,
    ProjectionLinearV3,
    ProjectionPointV3,
    ProjectionSphereV3,
    ProjectionSurfaceV3,
    RenderProjectionV3,
)
from app.schemas.scene_v3 import (
    Circle2DV3,
    FaceV3,
    FunctionGraphV3,
    Line2DV3,
    Line3DV3,
    MathSceneV3,
    PlaneV3,
    Point2DV3,
    Point3DV3,
    SegmentV3,
    SphereV3,
    Vector2DV3,
    Vector3DV3,
)
from app.services.geometry_kernel import build_geometry_index
from app.services.scene_goal_visualization_v3 import reserved_annotation_metadata_key


_SAFE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SEMANTIC_ANNOTATIONS = {"length", "measurement", "equal_marks", "angle", "right_angle"}


@dataclass(frozen=True)
class ProjectionError(ValueError):
    code: str
    message: str
    unsupported_ids: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.message


def build_render_projection_v3(scene: MathSceneV3) -> RenderProjectionV3:
    _validate_renderer_objects(scene)
    geometry = build_geometry_index(scene)
    object_names = _object_names(scene)
    def visible(obj) -> bool:
        return not bool(obj.metadata.get("tree_hidden"))
    point_items = [
        ProjectionPointV3(
            object_id=obj.id,
            name=object_names[obj.id],
            label=obj.label,
            position=geometry.point(obj.id),
            visible=visible(obj),
        )
        for obj in scene.objects
        if isinstance(obj, (Point2DV3, Point3DV3))
    ]

    coordinates = [item.position for item in point_items]
    for obj in scene.objects:
        if isinstance(obj, Circle2DV3):
            center, radius = geometry.circle(obj.id)
            coordinates.extend(_axis_extents(center, radius))
        elif isinstance(obj, SphereV3):
            center, radius = geometry.sphere(obj.id)
            coordinates.extend(_axis_extents(center, radius))
    bounds = _bounds(coordinates, default_radius=5.0 if any(isinstance(obj, FunctionGraphV3) for obj in scene.objects) else 1.0)
    infinite_extent = max(bounds.radius * 1.25, geometry.scale)

    linear: list[ProjectionLinearV3] = []
    for obj in scene.objects:
        if isinstance(obj, (SegmentV3, Line2DV3, Line3DV3)):
            linear.append(ProjectionLinearV3(
                object_id=obj.id,
                name=object_names[obj.id],
                kind="segment" if isinstance(obj, SegmentV3) else "line",
                point_ids=obj.point_ids,
                positions=geometry.line_points(obj.id),
                visible=visible(obj) and not obj.hidden,
                color=obj.color,
                line_width=obj.line_width,
                style=obj.style,
                extent=infinite_extent if isinstance(obj, (Line2DV3, Line3DV3)) else None,
            ))
        elif isinstance(obj, (Vector2DV3, Vector3DV3)):
            linear.append(ProjectionLinearV3(
                object_id=obj.id,
                name=object_names[obj.id],
                kind="vector",
                point_ids=(obj.from_point_id, obj.to_point_id),
                positions=geometry.line_points(obj.id),
                visible=visible(obj) and not obj.hidden,
                color=obj.color,
                line_width=obj.line_width,
                style=obj.style,
            ))

    circles = [
        ProjectionCircleV3(
            object_id=obj.id,
            name=object_names[obj.id],
            center_point_id=obj.center_point_id,
            center=geometry.circle(obj.id)[0],
            radius=geometry.circle(obj.id)[1],
            visible=visible(obj),
        )
        for obj in scene.objects
        if isinstance(obj, Circle2DV3)
    ]
    functions = [
        ProjectionFunctionV3(
            object_id=obj.id,
            name=object_names[obj.id],
            expression=obj.expression,
            domain=obj.domain,
            visible=visible(obj),
        )
        for obj in scene.objects
        if isinstance(obj, FunctionGraphV3)
    ]
    surfaces = [
        ProjectionSurfaceV3(
            object_id=obj.id,
            name=object_names[obj.id],
            kind="plane" if isinstance(obj, PlaneV3) else "face",
            point_ids=obj.point_ids,
            positions=list(geometry.plane_points(obj.id)),
            color=obj.color,
            opacity=obj.opacity,
            visible=visible(obj),
            extent=None,
            show_normal=obj.show_normal if isinstance(obj, PlaneV3) else False,
        )
        for obj in scene.objects
        if isinstance(obj, (FaceV3, PlaneV3))
    ]
    spheres = [
        ProjectionSphereV3(
            object_id=obj.id,
            name=object_names[obj.id],
            center_point_id=obj.center_point_id,
            center=geometry.sphere(obj.id)[0],
            radius=geometry.sphere(obj.id)[1],
            color=obj.color,
            opacity=obj.opacity,
            visible=visible(obj),
        )
        for obj in scene.objects
        if isinstance(obj, SphereV3)
    ]
    annotations = [projected for annotation in scene.annotations if (projected := _project_annotation(scene, annotation, object_names))]

    return RenderProjectionV3(
        scene_id=scene.scene_id,
        revision=scene.revision,
        renderer=scene.renderer,
        dimension=scene.view.dimension,
        object_names=object_names,
        points=point_items,
        linear=linear,
        circles=circles,
        functions=functions,
        surfaces=surfaces,
        spheres=spheres,
        annotations=annotations,
        bounds=bounds,
        view=scene.view,
    )


def _validate_renderer_objects(scene: MathSceneV3) -> None:
    unsupported: list[str] = []
    if scene.renderer == "geogebra_2d":
        unsupported = [
            obj.id for obj in scene.objects
            if isinstance(obj, (Point3DV3, Line3DV3, Vector3DV3, FaceV3, PlaneV3, SphereV3))
        ]
    elif scene.renderer == "threejs_3d":
        unsupported = [obj.id for obj in scene.objects if isinstance(obj, (Point2DV3, Line2DV3, Vector2DV3, Circle2DV3, FunctionGraphV3))]
    if unsupported:
        raise ProjectionError(
            code="RENDERER_UNSUPPORTED",
            message=f"Renderer {scene.renderer} không hỗ trợ object: {sorted(unsupported)}.",
            unsupported_ids=tuple(sorted(unsupported)),
        )


def _object_names(scene: MathSceneV3) -> dict[str, str]:
    names: dict[str, str] = {}
    used: set[str] = set()
    for index, obj in enumerate(scene.objects, start=1):
        candidates = (obj.label, obj.id, f"obj{index}")
        name = next((value for value in candidates if value and _SAFE_NAME.fullmatch(value) and value not in used), f"obj{index}")
        while name in used:
            name = f"obj{index}_{len(used)}"
        names[obj.id] = name
        used.add(name)
    return names


def _project_annotation(scene, annotation, object_names: dict[str, str]) -> ProjectionAnnotationV3 | None:
    if any(target_id not in object_names for target_id in annotation.target_ids):
        return None
    backend_render_safe = annotation.metadata.get(reserved_annotation_metadata_key()) is True
    if annotation.type in _SEMANTIC_ANNOTATIONS and annotation.provenance != "given" and not backend_render_safe:
        relation = next((item for item in scene.relations if item.id == annotation.relation_id), None)
        if relation is None or relation.verification is None or relation.verification.status != "verified":
            return None
    return ProjectionAnnotationV3(
        annotation_id=annotation.id,
        type=annotation.type,
        target_ids=annotation.target_ids,
        label=annotation.label,
        color=annotation.color,
        provenance=annotation.provenance,
        relation_id=annotation.relation_id,
        metadata=annotation.metadata,
    )


def _bounds(coordinates: list[tuple[float, float, float]], default_radius: float) -> ProjectionBoundsV3:
    if not coordinates:
        return ProjectionBoundsV3(
            minimum=(-default_radius, -default_radius, -default_radius),
            maximum=(default_radius, default_radius, default_radius),
            center=(0.0, 0.0, 0.0),
            radius=default_radius,
        )
    minimum = tuple(min(point[axis] for point in coordinates) for axis in range(3))
    maximum = tuple(max(point[axis] for point in coordinates) for axis in range(3))
    center = tuple((minimum[axis] + maximum[axis]) / 2 for axis in range(3))
    radius = max(
        sum((point[axis] - center[axis]) ** 2 for axis in range(3)) ** 0.5
        for point in coordinates
    )
    return ProjectionBoundsV3(minimum=minimum, maximum=maximum, center=center, radius=max(radius, 1.0))


def _axis_extents(center: tuple[float, float, float], radius: float) -> list[tuple[float, float, float]]:
    return [
        tuple(center[axis] + (radius if axis == changed_axis else 0.0) for axis in range(3))
        for changed_axis in range(3)
    ] + [
        tuple(center[axis] - (radius if axis == changed_axis else 0.0) for axis in range(3))
        for changed_axis in range(3)
    ]
