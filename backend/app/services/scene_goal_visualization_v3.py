from __future__ import annotations

import re

from app.schemas.scene_v3 import (
    AnnotationV3,
    DerivedFactV3,
    FaceV3,
    MathSceneV3,
    PlaneV3,
    Point2DV3,
    Point3DV3,
    SegmentV3,
)
from app.services.geometry_kernel import build_geometry_index
from app.services.geometry_kernel.primitives import distance, project_point_to_plane


_GOAL_COLOR = "#7c3aed"
_RESERVED_METADATA_KEY = "_backend_render_safe"


def complete_metric_goal_visualizations(scene: MathSceneV3) -> MathSceneV3:
    """Dựng minh họa xác định cho goal định lượng mà không tạo thêm constraint."""
    result = scene
    for fact in scene.derived_facts:
        if _is_distance_goal(fact):
            result = _complete_point_plane_distance(result, fact)
    return result


def reserved_annotation_metadata_key() -> str:
    return _RESERVED_METADATA_KEY


def _is_distance_goal(fact: DerivedFactV3) -> bool:
    return (
        fact.kind == "measurement"
        and fact.provenance == "render_only"
        and fact.value.get("role") == "goal"
        and fact.value.get("quantity") == "distance"
    )


def _complete_point_plane_distance(scene: MathSceneV3, fact: DerivedFactV3) -> MathSceneV3:
    objects_by_id = {obj.id: obj for obj in scene.objects}
    point = next(
        (objects_by_id.get(object_id) for object_id in fact.source_ids if isinstance(objects_by_id.get(object_id), (Point2DV3, Point3DV3))),
        None,
    )
    planar = next(
        (objects_by_id.get(object_id) for object_id in fact.source_ids if isinstance(objects_by_id.get(object_id), (PlaneV3, FaceV3))),
        None,
    )
    if not isinstance(point, (Point2DV3, Point3DV3)) or not isinstance(planar, (PlaneV3, FaceV3)):
        return scene

    geometry = build_geometry_index(scene)
    try:
        projected = project_point_to_plane(
            geometry.point(point.id),
            geometry.plane_points(planar.id),
            geometry.tolerance,
        )
    except ValueError:
        return scene
    if distance(geometry.point(point.id), projected) <= geometry.tolerance:
        return scene

    objects = list(scene.objects)
    used_ids = {obj.id for obj in objects} | {annotation.id for annotation in scene.annotations}
    foot = _find_point_at(scene, projected, geometry.tolerance * 10)
    if foot is None:
        foot_id = _unique_id(f"goal_{_slug(fact.id)}_foot", used_ids)
        foot = _new_point_like(point, foot_id, _unique_foot_label(scene), projected)
        objects.append(foot)

    connector = next(
        (
            obj
            for obj in objects
            if isinstance(obj, SegmentV3) and frozenset(obj.point_ids) == frozenset((point.id, foot.id))
        ),
        None,
    )
    if connector is None:
        connector = SegmentV3(
            id=_unique_id(f"goal_{_slug(fact.id)}_segment", used_ids),
            label=f"{point.label or point.id}{foot.label or foot.id}",
            point_ids=(point.id, foot.id),
            hidden=False,
            color=_GOAL_COLOR,
            line_width=2.5,
            style="dashed",
            source="construction",
            metadata={"visualization_role": "distance_goal", "goal_fact_id": fact.id},
        )
        objects.append(connector)

    annotations = list(scene.annotations)
    safe_metadata = {
        _RESERVED_METADATA_KEY: True,
        "visualization_role": "distance_goal",
        "goal_fact_id": fact.id,
    }
    if not any(annotation.type == "measurement" and annotation.target_ids == [connector.id] for annotation in annotations):
        annotations.append(AnnotationV3(
            id=_unique_id(f"goal_{_slug(fact.id)}_label", used_ids),
            type="measurement",
            target_ids=[connector.id],
            label=_distance_label(point, planar),
            color=_GOAL_COLOR,
            provenance="render_only",
            metadata=safe_metadata,
        ))

    plane_arm = _plane_arm_point(planar, foot.id)
    if plane_arm and not any(
        annotation.type == "right_angle"
        and len(annotation.target_ids) == 3
        and annotation.target_ids[1] == foot.id
        and annotation.target_ids[0] == point.id
        for annotation in annotations
    ):
        annotations.append(AnnotationV3(
            id=_unique_id(f"goal_{_slug(fact.id)}_right_angle", used_ids),
            type="right_angle",
            target_ids=[point.id, foot.id, plane_arm],
            color=_GOAL_COLOR,
            provenance="render_only",
            metadata=safe_metadata,
        ))

    return scene.model_copy(update={"objects": objects, "annotations": annotations})


def _find_point_at(scene: MathSceneV3, position: tuple[float, float, float], tolerance: float):
    geometry = build_geometry_index(scene)
    for obj in scene.objects:
        if isinstance(obj, (Point2DV3, Point3DV3)) and distance(geometry.point(obj.id), position) <= tolerance:
            return obj
    return None


def _new_point_like(
    source: Point2DV3 | Point3DV3,
    object_id: str,
    label: str,
    position: tuple[float, float, float],
) -> Point2DV3 | Point3DV3:
    common = {
        "id": object_id,
        "label": label,
        "source": "construction",
        "metadata": {"visualization_role": "projection_foot"},
    }
    if isinstance(source, Point3DV3):
        return Point3DV3(**common, x=position[0], y=position[1], z=position[2])
    return Point2DV3(**common, x=position[0], y=position[1])


def _unique_foot_label(scene: MathSceneV3) -> str:
    labels = {obj.label for obj in scene.objects if isinstance(obj, (Point2DV3, Point3DV3)) and obj.label}
    if "H" not in labels:
        return "H"
    index = 1
    while f"H{index}" in labels:
        index += 1
    return f"H{index}"


def _plane_arm_point(planar: PlaneV3 | FaceV3, foot_id: str) -> str | None:
    return next((point_id for point_id in planar.point_ids if point_id != foot_id), None)


def _distance_label(point: Point2DV3 | Point3DV3, planar: PlaneV3 | FaceV3) -> str:
    point_label = point.label or point.id
    plane_label = planar.label or planar.id
    return f"d({point_label}, ({plane_label}))"


def _unique_id(preferred: str, used_ids: set[str]) -> str:
    if preferred not in used_ids:
        used_ids.add(preferred)
        return preferred
    index = 2
    while f"{preferred}_{index}" in used_ids:
        index += 1
    result = f"{preferred}_{index}"
    used_ids.add(result)
    return result


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "metric"
