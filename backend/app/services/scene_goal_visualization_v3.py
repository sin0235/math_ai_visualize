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
from app.services.geometry.parser import parse_point_plane_distance_goal


_GOAL_COLOR = "#0f766e"
_GOAL_PLANE_COLOR = "#f59e0b"
_GOAL_PLANE_BOUNDARY_ROLE = "distance_goal_plane_boundary"
_RESERVED_METADATA_KEY = "_backend_render_safe"


def complete_metric_goal_visualizations(scene: MathSceneV3) -> MathSceneV3:
    """Dựng minh họa xác định cho goal định lượng mà không tạo thêm constraint."""
    result = _ensure_problem_point_plane_distance_goal(scene)
    for fact in result.derived_facts:
        if _is_distance_goal(fact):
            result = _complete_point_plane_distance(result, fact)
    return result


def _ensure_problem_point_plane_distance_goal(scene: MathSceneV3) -> MathSceneV3:
    parsed = parse_point_plane_distance_goal(scene.problem_text)
    if parsed is None:
        return scene
    point_label, plane_labels = parsed
    points_by_label = _unique_points_by_label(scene)
    point = points_by_label.get(_normalize_label(point_label))
    plane_points = [points_by_label.get(_normalize_label(label)) for label in plane_labels]
    if not isinstance(point, Point3DV3) or any(not isinstance(item, Point3DV3) for item in plane_points):
        return scene
    resolved_plane_points = [item for item in plane_points if isinstance(item, Point3DV3)]

    target_ids = [item.id for item in resolved_plane_points]
    target_key = frozenset(target_ids)
    planar = next(
        (
            obj
            for obj in scene.objects
            if isinstance(obj, (PlaneV3, FaceV3)) and frozenset(obj.point_ids) == target_key
        ),
        None,
    )
    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    plane_label = "".join(plane_labels)
    if planar is None:
        planar = FaceV3(
            id=_unique_id(f"goal_plane_{_slug(plane_label)}", used_ids),
            label=plane_label,
            point_ids=target_ids,
            color=_GOAL_PLANE_COLOR,
            opacity=0.5,
            source="construction",
            metadata={"visualization_role": "distance_goal_plane"},
        )
        objects.append(planar)
    elif not _style_is_user_owned(planar):
        styled = planar.model_copy(update={
            "label": plane_label,
            "color": _GOAL_PLANE_COLOR,
            "opacity": 0.5 if isinstance(planar, FaceV3) else 0.24,
            "metadata": {**planar.metadata, "visualization_role": "distance_goal_plane"},
        })
        objects = [styled if obj.id == planar.id else obj for obj in objects]
        planar = styled

    objects = _ensure_planar_boundary(objects, planar, plane_label, used_ids)

    facts = list(scene.derived_facts)
    existing = next(
        (
            fact
            for fact in facts
            if _is_distance_goal(fact)
            and point.id in fact.source_ids
            and planar.id in fact.source_ids
        ),
        None,
    )
    if existing is None:
        facts.append(DerivedFactV3(
            id=_unique_id(f"goal_distance_{_slug(point_label)}_{_slug(plane_label)}", used_ids),
            kind="measurement",
            source_ids=[point.id, planar.id],
            value={
                "role": "goal",
                "quantity": "distance",
                "point_label": point_label,
                "plane_label": plane_label,
            },
            provenance="render_only",
        ))
    return scene.model_copy(update={"objects": objects, "derived_facts": facts})


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

    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    objects = _ensure_planar_boundary(objects, planar, planar.label or planar.id, used_ids)
    scene = scene.model_copy(update={"objects": objects})

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
            line_width=3,
            style="dashed",
            source="construction",
            metadata={"visualization_role": "distance_goal", "goal_fact_id": fact.id},
        )
        objects.append(connector)
    elif not _style_is_user_owned(connector):
        connector = connector.model_copy(update={
            "hidden": False,
            "color": _GOAL_COLOR,
            "line_width": 3,
            "style": "dashed",
            "metadata": {
                **connector.metadata,
                "visualization_role": "distance_goal",
                "goal_fact_id": fact.id,
            },
        })
        objects = [connector if obj.id == connector.id else obj for obj in objects]

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


def _ensure_planar_boundary(
    objects: list,
    planar: PlaneV3 | FaceV3,
    plane_label: str,
    used_ids: set[str],
) -> list:
    existing_edges = {
        frozenset(obj.point_ids)
        for obj in objects
        if isinstance(obj, SegmentV3)
    }
    point_ids = list(planar.point_ids)
    for index, start_id in enumerate(point_ids):
        end_id = point_ids[(index + 1) % len(point_ids)]
        edge = frozenset((start_id, end_id))
        if edge in existing_edges:
            continue
        objects.append(SegmentV3(
            id=_unique_id(f"goal_plane_{_slug(plane_label)}_boundary_{index + 1}", used_ids),
            point_ids=(start_id, end_id),
            hidden=False,
            color=_GOAL_PLANE_COLOR,
            line_width=3,
            style="solid",
            source="construction",
            metadata={"visualization_role": _GOAL_PLANE_BOUNDARY_ROLE, "planar_id": planar.id},
        ))
        existing_edges.add(edge)
    return objects


def _plane_arm_point(planar: PlaneV3 | FaceV3, foot_id: str) -> str | None:
    return next((point_id for point_id in planar.point_ids if point_id != foot_id), None)


def _distance_label(point: Point2DV3 | Point3DV3, planar: PlaneV3 | FaceV3) -> str:
    point_label = point.label or point.id
    plane_label = planar.label or planar.id
    return f"d({point_label},({plane_label}))"


def _unique_points_by_label(scene: MathSceneV3) -> dict[str, Point2DV3 | Point3DV3]:
    points: dict[str, Point2DV3 | Point3DV3] = {}
    duplicates: set[str] = set()
    for obj in scene.objects:
        if not isinstance(obj, (Point2DV3, Point3DV3)) or not obj.label:
            continue
        label = _normalize_label(obj.label)
        if label in points:
            duplicates.add(label)
        else:
            points[label] = obj
    for label in duplicates:
        points.pop(label, None)
    return points


def _normalize_label(label: str) -> str:
    return label.strip().upper().replace("’", "'").replace("′", "'")


def _scene_ids(scene: MathSceneV3) -> set[str]:
    return {
        *(obj.id for obj in scene.objects),
        *(relation.id for relation in scene.relations),
        *(annotation.id for annotation in scene.annotations),
        *(fact.id for fact in scene.derived_facts),
    }


def _style_is_user_owned(obj) -> bool:
    return bool(
        getattr(obj, "locked", False)
        or getattr(obj, "user_edited", False)
        or getattr(obj, "source", None) in {"user_created", "user_edited"}
    )


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
