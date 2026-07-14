from __future__ import annotations

from app.schemas.scene_v3 import AnnotationV3, MathSceneV3, Point2DV3, Point3DV3, SegmentV3
from app.services.geometry.parser import AngleGoal, parse_angle_goal
from app.services.geometry_kernel import build_geometry_index
from app.services.geometry_kernel.primitives import (
    add,
    cross,
    dot,
    norm,
    normalized,
    plane_normal,
    project_point_to_plane,
    scale,
    sub,
)
from app.services.scene_goal_visualization_v3 import reserved_annotation_metadata_key


_ANGLE_COLOR = "#b45309"
_PROJECTION_COLOR = "#0f766e"


def complete_angle_goal_visualization(scene: MathSceneV3) -> MathSceneV3:
    """Dựng arms xác định cho goal góc; không tính hoặc gắn đáp số."""
    goal = parse_angle_goal(scene.problem_text)
    if goal is None or any(
        annotation.metadata.get("visualization_role") == "angle_goal"
        for annotation in scene.annotations
    ):
        return scene
    points = _unique_points_by_label(scene)
    try:
        if goal.kind == "point_angle":
            return _complete_point_angle(scene, goal, points)
        if goal.kind == "line_line":
            return _complete_line_line_angle(scene, goal, points)
        if goal.kind == "line_plane":
            return _complete_line_plane_angle(scene, goal, points)
        if goal.kind == "plane_plane":
            return _complete_plane_plane_angle(scene, goal, points)
    except (KeyError, ValueError):
        return scene
    return scene


def _complete_point_angle(scene: MathSceneV3, goal: AngleGoal, points):
    first, vertex, second = _resolve_points(goal.components[0], points)
    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    _ensure_segment(objects, used_ids, vertex, first, "angle_goal_arm")
    _ensure_segment(objects, used_ids, vertex, second, "angle_goal_arm")
    annotation = _angle_annotation(used_ids, goal, first.id, vertex.id, second.id)
    return scene.model_copy(update={"objects": objects, "annotations": [*scene.annotations, annotation]})


def _complete_line_line_angle(scene: MathSceneV3, goal: AngleGoal, points):
    first_start, first_end = _resolve_points(goal.components[0], points)
    second_start, second_end = _resolve_points(goal.components[1], points)
    shared = {first_start.id, first_end.id}.intersection({second_start.id, second_end.id})
    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    _ensure_segment(objects, used_ids, first_start, first_end, "angle_goal_source")
    _ensure_segment(objects, used_ids, second_start, second_end, "angle_goal_source")
    if shared:
        vertex_id = next(iter(shared))
        first_arm = first_end if first_start.id == vertex_id else first_start
        second_arm = second_end if second_start.id == vertex_id else second_start
        annotation = _angle_annotation(used_ids, goal, first_arm.id, vertex_id, second_arm.id)
        return scene.model_copy(update={"objects": objects, "annotations": [*scene.annotations, annotation]})

    geometry = build_geometry_index(scene.model_copy(update={"objects": objects}))
    vertex = first_start
    first_direction = normalized(sub(geometry.point(first_end.id), geometry.point(first_start.id)), geometry.tolerance)
    second_direction = normalized(sub(geometry.point(second_end.id), geometry.point(second_start.id)), geometry.tolerance)
    if dot(first_direction, second_direction) < 0:
        second_direction = scale(second_direction, -1)
    arm_length = max(norm(sub(geometry.point(first_end.id), geometry.point(first_start.id))), geometry.scale * 0.35)
    translated = _new_hidden_point_like(
        vertex,
        _unique_id("goal_angle_parallel_arm", used_ids),
        add(geometry.point(vertex.id), scale(second_direction, arm_length)),
        "angle_goal_parallel_translation",
    )
    objects.append(translated)
    _ensure_segment(objects, used_ids, vertex, translated, "angle_goal_parallel_translation", style="dashed")
    annotation = _angle_annotation(used_ids, goal, first_end.id, vertex.id, translated.id)
    return scene.model_copy(update={"objects": objects, "annotations": [*scene.annotations, annotation]})


def _complete_line_plane_angle(scene: MathSceneV3, goal: AngleGoal, points):
    line_start, line_end = _resolve_points(goal.components[0], points)
    plane_points = _resolve_points(goal.components[1], points)
    if not all(isinstance(point, Point3DV3) for point in (line_start, line_end, *plane_points)):
        return scene
    geometry = build_geometry_index(scene)
    origin = geometry.point(line_start.id)
    direction = normalized(sub(geometry.point(line_end.id), origin), geometry.tolerance)
    plane_positions = tuple(geometry.point(point.id) for point in plane_points)
    normal = plane_normal(plane_positions, geometry.tolerance)
    denominator = dot(direction, normal)
    projected_direction = sub(direction, scale(normal, denominator))
    if norm(projected_direction) <= geometry.tolerance:
        projected_direction = normalized(sub(plane_positions[1], plane_positions[0]), geometry.tolerance)
    else:
        projected_direction = normalized(projected_direction, geometry.tolerance)
    if dot(direction, projected_direction) < 0:
        projected_direction = scale(projected_direction, -1)

    if abs(denominator) > geometry.policy.angular_tolerance:
        parameter = dot(sub(plane_positions[0], origin), normal) / denominator
        vertex_position = add(origin, scale(direction, parameter))
    else:
        vertex_position = project_point_to_plane(origin, plane_positions, geometry.tolerance)
    arm_length = geometry.scale * 0.35
    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    vertex = _new_hidden_point_like(line_start, _unique_id("goal_angle_vertex", used_ids), vertex_position, "angle_goal_vertex")
    line_arm = _new_hidden_point_like(
        line_start,
        _unique_id("goal_angle_line_arm", used_ids),
        add(vertex_position, scale(direction, arm_length)),
        "angle_goal_line_arm",
    )
    plane_arm = _new_hidden_point_like(
        line_start,
        _unique_id("goal_angle_plane_arm", used_ids),
        add(vertex_position, scale(projected_direction, arm_length)),
        "angle_goal_plane_projection",
    )
    objects.extend((vertex, line_arm, plane_arm))
    _ensure_segment(objects, used_ids, vertex, line_arm, "angle_goal_line_arm")
    _ensure_segment(objects, used_ids, vertex, plane_arm, "angle_goal_plane_projection", color=_PROJECTION_COLOR, style="dashed")
    annotation = _angle_annotation(used_ids, goal, line_arm.id, vertex.id, plane_arm.id)
    return scene.model_copy(update={"objects": objects, "annotations": [*scene.annotations, annotation]})


def _complete_plane_plane_angle(scene: MathSceneV3, goal: AngleGoal, points):
    first_points = _resolve_points(goal.components[0], points)
    second_points = _resolve_points(goal.components[1], points)
    if not all(isinstance(point, Point3DV3) for point in (*first_points, *second_points)):
        return scene
    geometry = build_geometry_index(scene)
    first_positions = tuple(geometry.point(point.id) for point in first_points)
    second_positions = tuple(geometry.point(point.id) for point in second_points)
    first_normal = plane_normal(first_positions, geometry.tolerance)
    second_normal = plane_normal(second_positions, geometry.tolerance)
    intersection_direction = cross(first_normal, second_normal)
    denominator = dot(intersection_direction, intersection_direction)
    if denominator <= geometry.tolerance * geometry.tolerance:
        return scene
    first_constant = dot(first_normal, first_positions[0])
    second_constant = dot(second_normal, second_positions[0])
    vertex_position = scale(
        add(
            scale(cross(second_normal, intersection_direction), first_constant),
            scale(cross(intersection_direction, first_normal), second_constant),
        ),
        1.0 / denominator,
    )
    first_arm_direction = normalized(cross(first_normal, intersection_direction), geometry.tolerance)
    second_arm_direction = normalized(cross(second_normal, intersection_direction), geometry.tolerance)
    if dot(first_arm_direction, second_arm_direction) < 0:
        second_arm_direction = scale(second_arm_direction, -1)
    arm_length = geometry.scale * 0.35
    template = first_points[0]
    objects = list(scene.objects)
    used_ids = _scene_ids(scene)
    vertex = _new_hidden_point_like(template, _unique_id("goal_dihedral_vertex", used_ids), vertex_position, "angle_goal_intersection")
    first_arm = _new_hidden_point_like(
        template,
        _unique_id("goal_dihedral_first_arm", used_ids),
        add(vertex_position, scale(first_arm_direction, arm_length)),
        "angle_goal_first_plane_arm",
    )
    second_arm = _new_hidden_point_like(
        template,
        _unique_id("goal_dihedral_second_arm", used_ids),
        add(vertex_position, scale(second_arm_direction, arm_length)),
        "angle_goal_second_plane_arm",
    )
    objects.extend((vertex, first_arm, second_arm))
    _ensure_segment(objects, used_ids, vertex, first_arm, "angle_goal_first_plane_arm")
    _ensure_segment(objects, used_ids, vertex, second_arm, "angle_goal_second_plane_arm", color=_PROJECTION_COLOR)
    annotation = _angle_annotation(used_ids, goal, first_arm.id, vertex.id, second_arm.id)
    return scene.model_copy(update={"objects": objects, "annotations": [*scene.annotations, annotation]})


def _angle_annotation(used_ids: set[str], goal: AngleGoal, first_id: str, vertex_id: str, second_id: str) -> AnnotationV3:
    return AnnotationV3(
        id=_unique_id("goal_angle_annotation", used_ids),
        type="angle",
        target_ids=[first_id, vertex_id, second_id],
        label=goal.label,
        color=_ANGLE_COLOR,
        provenance="render_only",
        metadata={
            reserved_annotation_metadata_key(): True,
            "visualization_role": "angle_goal",
            "goal_kind": goal.kind,
        },
    )


def _ensure_segment(
    objects: list,
    used_ids: set[str],
    start,
    end,
    role: str,
    *,
    color: str = _ANGLE_COLOR,
    style: str = "solid",
) -> None:
    if any(isinstance(obj, SegmentV3) and frozenset(obj.point_ids) == frozenset((start.id, end.id)) for obj in objects):
        return
    objects.append(SegmentV3(
        id=_unique_id(f"goal_segment_{start.id}_{end.id}", used_ids),
        label=None,
        point_ids=(start.id, end.id),
        hidden=False,
        color=color,
        line_width=3,
        style=style,
        source="construction",
        metadata={"visualization_role": role},
    ))


def _new_hidden_point_like(template, object_id: str, position, role: str):
    common = {
        "id": object_id,
        "label": None,
        "source": "construction",
        "metadata": {"visualization_role": role, "tree_hidden": True},
    }
    if isinstance(template, Point3DV3):
        return Point3DV3(**common, x=position[0], y=position[1], z=position[2])
    return Point2DV3(**common, x=position[0], y=position[1])


def _resolve_points(labels: tuple[str, ...], points):
    return tuple(points[label] for label in labels)


def _unique_points_by_label(scene: MathSceneV3):
    result = {}
    duplicates = set()
    for obj in scene.objects:
        if not isinstance(obj, (Point2DV3, Point3DV3)) or not obj.label:
            continue
        label = obj.label.strip().upper().replace("’", "'").replace("′", "'")
        if label in result:
            duplicates.add(label)
        else:
            result[label] = obj
    for label in duplicates:
        result.pop(label, None)
    return result


def _scene_ids(scene: MathSceneV3) -> set[str]:
    return {
        *(obj.id for obj in scene.objects),
        *(relation.id for relation in scene.relations),
        *(annotation.id for annotation in scene.annotations),
        *(fact.id for fact in scene.derived_facts),
    }


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
