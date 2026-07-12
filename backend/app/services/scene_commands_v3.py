from __future__ import annotations

from dataclasses import dataclass

from app.schemas.scene_v3 import (
    AddPointCommand,
    ConnectPointsCommand,
    DeleteObjectCommand,
    FaceV3,
    IntersectObjectsCommand,
    Line2DV3,
    Line3DV3,
    MathSceneV3,
    MovePointCommand,
    PlaneV3,
    Point2DV3,
    Point3DV3,
    ProjectPointCommand,
    RelationV3,
    RemoveGeneratedCommand,
    RestoreGeneratedCommand,
    RestoreObjectCommand,
    SceneCommand,
    SceneObjectV3,
    SegmentV3,
    SetParameterCommand,
    SetVisibilityCommand,
    object_reference_ids,
)
from app.services.geometry_kernel import build_geometry_index
from app.services.geometry_kernel.primitives import (
    intersect_lines,
    project_point_to_line,
    project_point_to_plane,
)
from app.services.scene_pipeline_v3 import affected_relation_ids


CommandErrorCode = str


class SceneCommandError(ValueError):
    def __init__(self, code: CommandErrorCode, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AppliedSceneCommand:
    scene: MathSceneV3
    inverse: SceneCommand
    changed_object_ids: frozenset[str]
    affected_relation_ids: frozenset[str]


def apply_scene_command(scene: MathSceneV3, command: SceneCommand) -> AppliedSceneCommand:
    _validate_command_revision(scene, command)
    next_scene, inverse, changed_ids = _apply(scene, command)
    changed = frozenset(changed_ids)
    affected = affected_relation_ids(next_scene, set(changed)) | affected_relation_ids(scene, set(changed))
    next_scene = next_scene.model_copy(update={"revision": scene.revision + 1})
    inverse = inverse.model_copy(update={"base_revision": next_scene.revision})
    return AppliedSceneCommand(scene=next_scene, inverse=inverse, changed_object_ids=changed, affected_relation_ids=affected)


def _validate_command_revision(scene: MathSceneV3, command: SceneCommand) -> None:
    if command.scene_id != scene.scene_id:
        raise SceneCommandError("SCENE_COMMAND_WRONG_SCENE", "Command không thuộc scene hiện tại.")
    if command.base_revision != scene.revision:
        raise SceneCommandError(
            "SCENE_EDIT_STALE",
            f"Revision chỉnh sửa không hợp lệ: cần {scene.revision}, nhận {command.base_revision}.",
        )


def _apply(scene: MathSceneV3, command: SceneCommand) -> tuple[MathSceneV3, SceneCommand, set[str]]:
    if isinstance(command, MovePointCommand):
        return _move_point(scene, command)
    if isinstance(command, AddPointCommand):
        return _add_point(scene, command)
    if isinstance(command, DeleteObjectCommand):
        return _delete_object(scene, command)
    if isinstance(command, RestoreObjectCommand):
        return _restore_object(scene, command)
    if isinstance(command, RemoveGeneratedCommand):
        return _remove_generated(scene, command)
    if isinstance(command, RestoreGeneratedCommand):
        return _restore_generated(scene, command)
    if isinstance(command, ConnectPointsCommand):
        return _connect_points(scene, command)
    if isinstance(command, ProjectPointCommand):
        return _project_point(scene, command)
    if isinstance(command, IntersectObjectsCommand):
        return _intersect_objects(scene, command)
    if isinstance(command, SetParameterCommand):
        return _set_parameter(scene, command)
    if isinstance(command, SetVisibilityCommand):
        return _set_visibility(scene, command)
    raise SceneCommandError("SCENE_COMMAND_UNSUPPORTED", f"Command {command.type} chưa được hỗ trợ.")


def _move_point(scene: MathSceneV3, command: MovePointCommand):
    point = _object(scene, command.point_id)
    if not isinstance(point, (Point2DV3, Point3DV3)):
        raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Đối tượng cần di chuyển không phải point.")
    if point.locked:
        raise SceneCommandError("SCENE_OBJECT_LOCKED", f"Point {point.id} đang bị khóa.")
    previous = (point.x, point.y, point.z if isinstance(point, Point3DV3) else 0.0)
    x, y, z = command.position
    update = {"x": x, "y": y, "source": "user_edited", "user_edited": True, "x_expr": None, "y_expr": None}
    if isinstance(point, Point3DV3):
        update.update({"z": z, "z_expr": None})
    moved = point.model_copy(update=update)
    inverse = MovePointCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, point_id=point.id, position=previous,
    )
    return _replace_objects(scene, {point.id: moved}), inverse, {point.id}


def _add_point(scene: MathSceneV3, command: AddPointCommand):
    _ensure_new_id(scene, command.point.id)
    point = command.point.model_copy(update={"source": "user_created", "user_edited": True})
    inverse = DeleteObjectCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object_id=point.id,
    )
    return scene.model_copy(update={"objects": [*scene.objects, point]}), inverse, {point.id}


def _delete_object(scene: MathSceneV3, command: DeleteObjectCommand):
    target = _object(scene, command.object_id)
    if target.locked:
        raise SceneCommandError("SCENE_OBJECT_LOCKED", f"Object {target.id} đang bị khóa.")
    references = _object_referrers(scene, target.id)
    relation_refs = [relation.id for relation in scene.relations if target.id in {operand.ref_id for operand in relation.operands}]
    annotation_refs = [annotation.id for annotation in scene.annotations if target.id in annotation.target_ids]
    if references or relation_refs or annotation_refs:
        raise SceneCommandError(
            "SCENE_OBJECT_IN_USE",
            f"Object {target.id} còn được tham chiếu bởi {references + relation_refs + annotation_refs}.",
        )
    inverse = RestoreObjectCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object=target,
    )
    objects = [obj for obj in scene.objects if obj.id != target.id]
    return scene.model_copy(update={"objects": objects}), inverse, {target.id}


def _restore_object(scene: MathSceneV3, command: RestoreObjectCommand):
    _ensure_new_id(scene, command.object.id)
    inverse = DeleteObjectCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object_id=command.object.id,
    )
    return scene.model_copy(update={"objects": [*scene.objects, command.object]}), inverse, {command.object.id}


def _remove_generated(scene: MathSceneV3, command: RemoveGeneratedCommand):
    object_ids = set(command.object_ids)
    relation_ids = set(command.relation_ids)
    objects = [obj for obj in scene.objects if obj.id in object_ids]
    relations = [relation for relation in scene.relations if relation.id in relation_ids]
    if len(objects) != len(object_ids) or len(relations) != len(relation_ids):
        raise SceneCommandError("REFERENCE_NOT_FOUND", "Không tìm thấy đủ construction cần hoàn tác.")
    external_object_refs = [
        obj.id for obj in scene.objects
        if obj.id not in object_ids and object_ids.intersection(object_reference_ids(obj))
    ]
    external_relation_refs = [
        relation.id for relation in scene.relations
        if relation.id not in relation_ids and object_ids.intersection(operand.ref_id for operand in relation.operands)
    ]
    if external_object_refs or external_relation_refs:
        raise SceneCommandError("SCENE_OBJECT_IN_USE", "Construction còn được scene tham chiếu, không thể hoàn tác.")
    next_scene = scene.model_copy(update={
        "objects": [obj for obj in scene.objects if obj.id not in object_ids],
        "relations": [relation for relation in scene.relations if relation.id not in relation_ids],
    })
    inverse = RestoreGeneratedCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, objects=objects, relations=relations,
    )
    return next_scene, inverse, object_ids


def _restore_generated(scene: MathSceneV3, command: RestoreGeneratedCommand):
    for obj in command.objects:
        _ensure_new_id(scene, obj.id)
    existing_relation_ids = {relation.id for relation in scene.relations}
    if any(relation.id in existing_relation_ids for relation in command.relations):
        raise SceneCommandError("SCENE_ID_CONFLICT", "Relation cần khôi phục đã tồn tại.")
    object_ids = [obj.id for obj in command.objects]
    relation_ids = [relation.id for relation in command.relations]
    next_scene = scene.model_copy(update={
        "objects": [*scene.objects, *command.objects],
        "relations": [*scene.relations, *command.relations],
    })
    inverse = RemoveGeneratedCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object_ids=object_ids, relation_ids=relation_ids,
    )
    return next_scene, inverse, set(object_ids)


def _connect_points(scene: MathSceneV3, command: ConnectPointsCommand):
    _ensure_new_id(scene, command.object_id)
    start = _point(scene, command.start_point_id)
    end = _point(scene, command.end_point_id)
    if start.id == end.id:
        raise SceneCommandError("SCENE_COMMAND_DEGENERATE", "Cần hai point khác nhau.")
    if command.connection == "segment":
        obj: SceneObjectV3 = SegmentV3(id=command.object_id, point_ids=(start.id, end.id), source="user_created")
    elif isinstance(start, Point3DV3) or isinstance(end, Point3DV3):
        obj = Line3DV3(id=command.object_id, point_ids=(start.id, end.id), source="user_created")
    else:
        obj = Line2DV3(id=command.object_id, point_ids=(start.id, end.id), source="user_created")
    inverse = DeleteObjectCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object_id=obj.id,
    )
    return scene.model_copy(update={"objects": [*scene.objects, obj]}), inverse, {obj.id}


def _project_point(scene: MathSceneV3, command: ProjectPointCommand):
    _ensure_new_id(scene, command.result_point_id)
    source = _point(scene, command.source_point_id)
    geometry = build_geometry_index(scene)
    source_position = geometry.point(source.id)
    if command.target_kind in {"line", "segment"}:
        target = _object(scene, command.target_id)
        if command.target_kind == "line" and not isinstance(target, (Line2DV3, Line3DV3)):
            raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Target không phải line.")
        if command.target_kind == "segment" and not isinstance(target, SegmentV3):
            raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Target không phải segment.")
        projected, raw_parameter = project_point_to_line(
            source_position, *geometry.line_points(target.id), geometry.tolerance, clamp_to_segment=command.target_kind == "segment",
        )
        relation_type = "point_on_segment" if command.target_kind == "segment" else "on_line"
        target_kind = "segment" if command.target_kind == "segment" else "line"
    else:
        target = _object(scene, command.target_id)
        if not isinstance(target, (PlaneV3, FaceV3)):
            raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Target không phải plane/face.")
        projected = project_point_to_plane(source_position, geometry.plane_points(target.id), geometry.tolerance)
        raw_parameter = 0.0
        relation_type = "on_plane"
        target_kind = "plane" if isinstance(target, PlaneV3) else "face"

    result = _new_point_like(source, command.result_point_id, projected)
    connector_id = f"{command.result_point_id}:projection"
    _ensure_new_id(scene, connector_id)
    connector = SegmentV3(id=connector_id, point_ids=(source.id, result.id), source="construction")
    on_target = RelationV3.model_validate({
        "id": f"rel:{command.command_id}:target",
        "type": relation_type,
        "operands": [
            {"role": "point", "ref_id": result.id, "ref_kind": "point"},
            {"role": "target", "ref_id": target.id, "ref_kind": target_kind},
        ],
        "source": "construction",
        "metadata": {"raw_parameter": raw_parameter},
    })
    relations = [*scene.relations, on_target]
    if command.target_kind in {"line", "segment"}:
        relations.append(RelationV3.model_validate({
            "id": f"rel:{command.command_id}:perpendicular",
            "type": "perpendicular",
            "operands": [
                {"role": "projection", "ref_id": connector.id, "ref_kind": "segment"},
                {"role": "target", "ref_id": target.id, "ref_kind": target_kind},
            ],
            "source": "construction",
        }))
    generated_relation_ids = [relation.id for relation in relations[len(scene.relations):]]
    inverse = RemoveGeneratedCommand(
        command_id=f"undo:{command.command_id}",
        scene_id=scene.scene_id,
        base_revision=scene.revision,
        object_ids=[result.id, connector.id],
        relation_ids=generated_relation_ids,
    )
    next_scene = scene.model_copy(update={"objects": [*scene.objects, result, connector], "relations": relations})
    return next_scene, inverse, {result.id, connector.id}


def _intersect_objects(scene: MathSceneV3, command: IntersectObjectsCommand):
    _ensure_new_id(scene, command.result_object_id)
    geometry = build_geometry_index(scene)
    first = _object(scene, command.object_ids[0])
    second = _object(scene, command.object_ids[1])
    if not isinstance(first, (Line2DV3, Line3DV3, SegmentV3)) or not isinstance(second, (Line2DV3, Line3DV3, SegmentV3)):
        raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Giao điểm hiện hỗ trợ line/segment.")
    position, first_parameter, second_parameter = intersect_lines(
        geometry.line_points(first.id), geometry.line_points(second.id), geometry.tolerance,
    )
    if isinstance(first, SegmentV3) and not -geometry.tolerance <= first_parameter <= 1 + geometry.tolerance:
        raise SceneCommandError("SCENE_COMMAND_NO_INTERSECTION", "Giao điểm nằm ngoài segment thứ nhất.")
    if isinstance(second, SegmentV3) and not -geometry.tolerance <= second_parameter <= 1 + geometry.tolerance:
        raise SceneCommandError("SCENE_COMMAND_NO_INTERSECTION", "Giao điểm nằm ngoài segment thứ hai.")
    template = next((obj for obj in scene.objects if isinstance(obj, (Point2DV3, Point3DV3))), None)
    if template is None:
        raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Scene không có point template.")
    result = _new_point_like(template, command.result_object_id, position)
    relation = RelationV3.model_validate({
        "id": f"rel:{command.command_id}:intersection",
        "type": "intersection",
        "operands": [
            {"role": "result", "ref_id": result.id, "ref_kind": "point"},
            {"role": "first", "ref_id": first.id, "ref_kind": "segment" if isinstance(first, SegmentV3) else "line"},
            {"role": "second", "ref_id": second.id, "ref_kind": "segment" if isinstance(second, SegmentV3) else "line"},
        ],
        "source": "construction",
    })
    inverse = RemoveGeneratedCommand(
        command_id=f"undo:{command.command_id}",
        scene_id=scene.scene_id,
        base_revision=scene.revision,
        object_ids=[result.id],
        relation_ids=[relation.id],
    )
    return scene.model_copy(update={"objects": [*scene.objects, result], "relations": [*scene.relations, relation]}), inverse, {result.id}


def _set_parameter(scene: MathSceneV3, command: SetParameterCommand):
    parameter = next((item for item in scene.parameters if item.id == command.parameter_id), None)
    if parameter is None:
        raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", "Không tìm thấy parameter.")
    if not parameter.min <= command.value <= parameter.max:
        raise SceneCommandError("SCENE_PARAMETER_OUT_OF_RANGE", "Giá trị parameter ngoài khoảng cho phép.")
    previous = parameter.default
    parameters = [item.model_copy(update={"default": command.value}) if item.id == parameter.id else item for item in scene.parameters]
    variables = {item.name: command.value if item.id == parameter.id else item.default for item in scene.parameters}
    objects = [_evaluate_object_expressions(obj, variables) for obj in scene.objects]
    inverse = SetParameterCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, parameter_id=parameter.id, value=previous,
    )
    changed = {obj.id for old, obj in zip(scene.objects, objects, strict=True) if old != obj}
    return scene.model_copy(update={"parameters": parameters, "objects": objects}), inverse, changed


def _set_visibility(scene: MathSceneV3, command: SetVisibilityCommand):
    target = _object(scene, command.object_id)
    previous = not bool(target.metadata.get("tree_hidden"))
    metadata = {**target.metadata, "tree_hidden": not command.visible}
    updated = target.model_copy(update={"metadata": metadata})
    inverse = SetVisibilityCommand(
        command_id=f"undo:{command.command_id}", scene_id=scene.scene_id, base_revision=scene.revision, object_id=target.id, visible=previous,
    )
    return _replace_objects(scene, {target.id: updated}), inverse, {target.id}


def _evaluate_object_expressions(obj: SceneObjectV3, variables: dict[str, float]) -> SceneObjectV3:
    if not isinstance(obj, (Point2DV3, Point3DV3)):
        return obj
    from app.services.expression_eval import safe_eval

    update = {}
    for axis in ("x", "y", "z"):
        expression = getattr(obj, f"{axis}_expr", None)
        if expression:
            update[axis] = safe_eval(expression, variables)
    return obj.model_copy(update=update) if update else obj


def _new_point_like(template: Point2DV3 | Point3DV3, identifier: str, position: tuple[float, float, float]):
    common = {"id": identifier, "label": identifier, "source": "construction", "user_edited": False}
    if isinstance(template, Point3DV3):
        return Point3DV3(**common, x=position[0], y=position[1], z=position[2])
    return Point2DV3(**common, x=position[0], y=position[1])


def _replace_objects(scene: MathSceneV3, replacements: dict[str, SceneObjectV3]) -> MathSceneV3:
    return scene.model_copy(update={"objects": [replacements.get(obj.id, obj) for obj in scene.objects]})


def _object(scene: MathSceneV3, object_id: str) -> SceneObjectV3:
    obj = next((item for item in scene.objects if item.id == object_id), None)
    if obj is None:
        raise SceneCommandError("REFERENCE_NOT_FOUND", f"Không tìm thấy object {object_id}.")
    return obj


def _point(scene: MathSceneV3, point_id: str) -> Point2DV3 | Point3DV3:
    obj = _object(scene, point_id)
    if not isinstance(obj, (Point2DV3, Point3DV3)):
        raise SceneCommandError("SCENE_COMMAND_TARGET_INVALID", f"Object {point_id} không phải point.")
    return obj


def _ensure_new_id(scene: MathSceneV3, object_id: str) -> None:
    if any(obj.id == object_id for obj in scene.objects) or any(relation.id == object_id for relation in scene.relations):
        raise SceneCommandError("SCENE_ID_CONFLICT", f"ID {object_id} đã tồn tại.")


def _object_referrers(scene: MathSceneV3, target_id: str) -> list[str]:
    return [obj.id for obj in scene.objects if obj.id != target_id and target_id in object_reference_ids(obj)]