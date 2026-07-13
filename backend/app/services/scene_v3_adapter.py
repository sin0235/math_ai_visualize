from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.scene_v3 import MathSceneV3


@dataclass(frozen=True)
class SceneMigrationReport:
    source_version: str
    target_version: str = "3.0"
    unresolved_references: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def requires_confirmation(self) -> bool:
        return bool(self.unresolved_references)

    def model_dump(self) -> dict[str, Any]:
        return {
            "source_version": self.source_version,
            "target_version": self.target_version,
            "unresolved_references": list(self.unresolved_references),
            "warnings": list(self.warnings),
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class _MigrationState:
    scene_id: str
    labels: dict[str, list[str]] = field(default_factory=dict)
    object_ids: set[str] = field(default_factory=set)
    object_kinds: dict[str, str] = field(default_factory=dict)
    object_point_ids: dict[str, tuple[str, ...]] = field(default_factory=dict)
    relation_ids: set[str] = field(default_factory=set)
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def stable_id(self, kind: str, index: int, label: str | None = None) -> str:
        seed = f"{self.scene_id}:{kind}:{index}:{label or ''}"
        suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        return f"{kind}_{suffix}"

    def resolve_label(self, value: str | None, context: str) -> str | None:
        if not value:
            return None
        candidates = self.labels.get(value.strip(), [])
        if len(candidates) == 1:
            return candidates[0]
        reason = "không tồn tại" if not candidates else "không duy nhất"
        self.unresolved.append(f"{context}: '{value}' {reason}")
        return None


# Ánh xạ coerce type 2D → 3D tương đương khi renderer yêu cầu không gian 3D.
_COERCE_2D_TO_3D: dict[str, str] = {
    "point_2d": "point_3d",
    "line_2d": "line_3d",
    "vector_2d": "vector_3d",
}
_3D_RENDERERS = {"threejs_3d"}


def _coerce_objects_for_renderer(objects: list[dict[str, Any]], renderer: str, state: _MigrationState) -> list[dict[str, Any]]:
    """Khi renderer yêu cầu 3D, tự động nâng object 2D lên type 3D tương đương.
    Điều này vá lỗi AI hay sinh scene threejs_3d nhưng lẫn point_2d/line_2d bên trong."""
    if renderer not in _3D_RENDERERS:
        return objects
    coerced: list[dict[str, Any]] = []
    for obj in objects:
        obj_type = obj.get("type", "")
        if obj_type in _COERCE_2D_TO_3D:
            new_type = _COERCE_2D_TO_3D[obj_type]
            obj = {**obj, "type": new_type}
            # Đảm bảo có z=0 nếu thiếu
            if new_type == "point_3d" and "z" not in obj:
                obj["z"] = 0.0
            state.warnings.append(f"Object '{obj.get('id', '')}': coerce {obj_type} → {new_type} do renderer {renderer}.")
            # Cập nhật kind trong registry
            obj_id = obj.get("id", "")
            if obj_id in state.object_kinds:
                state.object_kinds[obj_id] = _reference_kind_for_object_type(new_type)
        coerced.append(obj)
    return coerced


def migrate_scene_v2_dict(scene: dict[str, Any]) -> tuple[MathSceneV3, SceneMigrationReport]:
    if scene.get("schema_version") == "3.0":
        return MathSceneV3.model_validate(scene), SceneMigrationReport(source_version="3.0")

    source_version = str(scene.get("schema_version") or "2.0")
    scene_id = str(scene.get("scene_id") or _stable_scene_id(scene))
    renderer = scene.get("renderer") or "geogebra_2d"
    state = _MigrationState(scene_id=scene_id)
    objects = _migrate_objects(scene.get("objects"), state)
    objects = _coerce_objects_for_renderer(objects, renderer, state)
    relations = _migrate_relations(scene.get("relations"), state)
    annotations = _migrate_annotations(scene.get("annotations"), state)
    parameters = _migrate_parameters(scene.get("parameters"), state)
    steps = _migrate_construction_steps(scene.get("construction_steps"), state)
    interpretation = scene.get("interpretation") if isinstance(scene.get("interpretation"), dict) else {}
    audit = scene.get("audit") if isinstance(scene.get("audit"), dict) else {}

    # Đồng bộ view.dimension với renderer nếu không khớp.
    view = scene.get("view") or {"dimension": "2d"}
    if renderer in _3D_RENDERERS and isinstance(view, dict) and view.get("dimension") != "3d":
        view = {**view, "dimension": "3d"}
        state.warnings.append("view.dimension đã được tự động đặt thành '3d' cho renderer threejs_3d.")

    migrated = MathSceneV3.model_validate({
        "scene_id": scene_id,
        "schema_version": "3.0",
        "revision": max(1, int(scene.get("revision") or 1)),
        "problem_text": str(scene.get("problem_text") or ""),
        "grade": scene.get("grade"),
        "topic": scene.get("topic") or "unknown",
        "renderer": renderer,
        "objects": objects,
        "relations": relations,
        "annotations": annotations,
        "derived_facts": [],
        "parameters": parameters,
        "view": view,
        "interpretation": {
            "object_ids": [obj["id"] for obj in objects],
            "relation_ids": [relation["id"] for relation in relations],
            "values": interpretation.get("values") if isinstance(interpretation.get("values"), list) else [],
            "missing_data": interpretation.get("missing_data") if isinstance(interpretation.get("missing_data"), list) else [],
            "assumptions": interpretation.get("assumptions") if isinstance(interpretation.get("assumptions"), list) else [],
        },
        "construction_steps": steps,
        "audit": {
            "created_by": audit.get("created_by") or "ai",
            "generator_provider": audit.get("generator_provider"),
            "generator_model": audit.get("generator_model"),
            "generator_prompt_version": audit.get("generator_prompt_version"),
            "migrated_from": source_version,
            "updated_at": audit.get("updated_at"),
        },
    })
    report = SceneMigrationReport(
        source_version=source_version,
        unresolved_references=tuple(dict.fromkeys(state.unresolved)),
        warnings=tuple(dict.fromkeys(state.warnings)),
    )
    return migrated, report


def migrate_render_response_v2_dict(response: dict[str, Any]) -> tuple[dict[str, Any], SceneMigrationReport]:
    raw_scene = response.get("scene")
    if not isinstance(raw_scene, dict):
        raise ValueError("Render response không chứa scene hợp lệ")
    scene, report = migrate_scene_v2_dict(raw_scene)
    migrated = dict(response)
    migrated["scene"] = scene.model_dump(mode="json")
    migrated["schema_version"] = "3.0"
    migrated["migration_report"] = report.model_dump()
    if report.requires_confirmation:
        migrated["status"] = "needs_confirmation"
        migrated["requires_user_confirmation"] = True
        migrated["warnings"] = [*list(migrated.get("warnings") or []), "Scene v2 có tham chiếu mơ hồ khi chuyển sang v3; cần xác nhận lại."]
    return migrated, report


def _migrate_objects(raw_objects: Any, state: _MigrationState) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    source = raw_objects if isinstance(raw_objects, list) else []
    for index, raw in enumerate(source):
        if not isinstance(raw, dict) or not isinstance(raw.get("type"), str):
            state.warnings.append(f"objects[{index}] không hợp lệ; đã bỏ")
            continue
        obj = dict(raw)
        obj_type = str(obj["type"])
        label = obj.pop("name", None)
        object_id = str(obj.get("id") or state.stable_id("obj", index, label))
        obj["id"] = object_id
        obj["label"] = label
        state.object_ids.add(object_id)
        state.object_kinds[object_id] = _reference_kind_for_object_type(obj_type)
        if isinstance(label, str) and label:
            state.labels.setdefault(label, []).append(object_id)
        objects.append(obj)

    migrated: list[dict[str, Any]] = []
    for index, obj in enumerate(objects):
        obj_type = obj["type"]
        if obj_type in {"segment", "face", "plane"}:
            refs = obj.pop("points", [])
            obj["point_ids"] = _resolve_many(refs, state, f"objects[{index}].points")
        elif obj_type in {"line_2d", "line_3d"}:
            refs = obj.pop("through", [])
            obj["point_ids"] = _resolve_many(refs, state, f"objects[{index}].through")
        elif obj_type in {"vector_2d", "vector_3d"}:
            obj["from_point_id"] = state.resolve_label(obj.pop("from_point", None), f"objects[{index}].from_point")
            obj["to_point_id"] = state.resolve_label(obj.pop("to_point", None), f"objects[{index}].to_point")
        elif obj_type == "circle_2d":
            obj["center_point_id"] = state.resolve_label(obj.pop("center", None), f"objects[{index}].center")
            through = obj.pop("through", None)
            obj["through_point_id"] = state.resolve_label(through, f"objects[{index}].through") if through else None
        elif obj_type == "sphere":
            obj["center_point_id"] = state.resolve_label(obj.pop("center", None), f"objects[{index}].center")
        if _has_missing_required_reference(obj):
            state.warnings.append(f"Object {obj['id']} có tham chiếu không chuyển được; đã bỏ")
            state.object_ids.discard(obj["id"])
            state.object_kinds.pop(obj["id"], None)
            label = obj.get("label")
            if isinstance(label, str) and label in state.labels:
                state.labels[label] = [candidate for candidate in state.labels[label] if candidate != obj["id"]]
            continue
        _register_linear_aliases(obj, refs if obj_type in {"segment", "line_2d", "line_3d"} else None, state)
        migrated.append(obj)
    return migrated


def _register_linear_aliases(obj: dict[str, Any], raw_points: Any, state: _MigrationState) -> None:
    point_ids = obj.get("point_ids")
    if isinstance(point_ids, list):
        state.object_point_ids[obj["id"]] = tuple(point_ids)
    if obj.get("label") or not isinstance(raw_points, (list, tuple)) or len(raw_points) != 2:
        return
    labels = [str(value).strip() for value in raw_points]
    if any(not label or len(label) != 1 for label in labels):
        return
    for alias in ("".join(labels), "".join(reversed(labels))):
        candidates = state.labels.setdefault(alias, [])
        if obj["id"] not in candidates:
            candidates.append(obj["id"])


def _migrate_relations(raw_relations: Any, state: _MigrationState) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    source = raw_relations if isinstance(raw_relations, list) else []
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            state.warnings.append(f"relations[{index}] không hợp lệ; đã bỏ")
            continue
        relation_id = str(raw.get("id") or state.stable_id("rel", index, str(raw.get("type") or "")))
        operands = _relation_operands(raw, state, index)
        if not operands:
            state.warnings.append(f"Relation {relation_id} không chuyển được operand; đã bỏ")
            continue
        relation_type = str(raw.get("type") or "unknown")
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        args = dict(raw.get("args")) if isinstance(raw.get("args"), dict) else {}
        if relation_type == "distance" and "value" not in args and isinstance(metadata.get("value"), (int, float)):
            args["value"] = metadata["value"]
        # Repair: AI hay sinh midpoint với 3 point thay vì (linear + point).
        if relation_type == "midpoint":
            operands, relation_type, repair_warning = _repair_midpoint_operands(operands, state, relation_id)
            if repair_warning:
                state.warnings.append(repair_warning)
        relation = {
            "id": relation_id,
            "type": relation_type,
            "operands": operands,
            "args": args,
            "source": raw.get("source") or "ai_inferred",
            "verification": None,
            "metadata": metadata,
        }
        state.relation_ids.add(relation_id)
        relations.append(relation)
    return relations


def _repair_midpoint_operands(
    operands: list[dict[str, str]],
    state: _MigrationState,
    relation_id: str,
) -> tuple[list[dict[str, str]], str, str | None]:
    """Sửa relation midpoint khi AI truyền 3 points thay vì (linear + point).

    Contract đúng: midpoint cần đúng 1 point (điểm giữa) + 1 linear (đoạn thẳng).
    AI hay truyền: 3 points [A, B, E] trong đó E là midpoint của AB.

    Chiến lược:
    1. Đúng contract (linear + point) → không làm gì.
    2. Ba points → tìm segment khớp 2 endpoint trong registry.
       - Tìm được → coerce (segment, điểm còn lại) đúng contract.
       - Không tìm được → downgrade sang collinear để tránh 422.
    3. Trường hợp khác → trả nguyên.
    """
    point_ops = [op for op in operands if op.get("ref_kind") == "point"]
    linear_ops = [op for op in operands if op.get("ref_kind") in {"segment", "line", "vector", "linear"}]

    # Đã đúng contract → không làm gì.
    if len(point_ops) == 1 and len(linear_ops) == 1:
        return operands, "midpoint", None

    # AI truyền 3 points.
    if len(point_ops) == 3 and len(linear_ops) == 0:
        p_ids = [op["ref_id"] for op in point_ops]
        segment_id = _find_segment_for_points(p_ids, state)
        if segment_id is not None:
            seg_points = set(state.object_point_ids.get(segment_id, ()))
            midpoint_ops = [op for op in point_ops if op["ref_id"] not in seg_points]
            if len(midpoint_ops) == 1:
                repaired = [
                    {"role": "point_1", "ref_id": midpoint_ops[0]["ref_id"], "ref_kind": "point"},
                    {"role": "linear_1", "ref_id": segment_id, "ref_kind": "segment"},
                ]
                return repaired, "midpoint", (
                    f"Relation {relation_id}: midpoint 3-point coerced "
                    f"\u2192 (segment={segment_id}, midpoint={midpoint_ops[0]['ref_id']})."
                )
        # Không tìm được segment → downgrade sang collinear.
        collinear_ops = [
            {"role": f"point_{i + 1}", "ref_id": op["ref_id"], "ref_kind": "point"}
            for i, op in enumerate(point_ops)
        ]
        return collinear_ops, "collinear", (
            f"Relation {relation_id}: midpoint 3-point không tìm được segment; downgrade \u2192 collinear."
        )

    return operands, "midpoint", None


def _find_segment_for_points(point_ids: list[str], state: _MigrationState) -> str | None:
    """Tìm segment_id có point_ids khớp với bất kỳ cặp nào trong point_ids."""
    id_set = set(point_ids)
    for seg_id, seg_points in state.object_point_ids.items():
        if state.object_kinds.get(seg_id) == "segment" and set(seg_points) <= id_set:
            return seg_id
    return None


def _relation_operands(raw: dict[str, Any], state: _MigrationState, index: int) -> list[dict[str, str]]:
    refs: list[tuple[str, str]] = []
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    metadata_objects = metadata.get("objects")
    if isinstance(metadata_objects, list):
        for item in metadata_objects:
            if isinstance(item, str):
                refs.append(("object", item))
            elif isinstance(item, list):
                refs.extend(("point", str(value)) for value in item if isinstance(value, str))
    if not refs:
        for role, value in (("object_1", raw.get("object_1")), ("object_2", raw.get("object_2"))):
            refs.extend((role, token) for token in _legacy_relation_tokens(value, state))

    operands: list[dict[str, str]] = []
    for position, (role, label) in enumerate(refs):
        ref_id = state.resolve_label(label, f"relations[{index}].{role}")
        if ref_id:
            operands.append({"role": role if role != "object" else f"object_{position + 1}", "ref_id": ref_id, "ref_kind": state.object_kinds.get(ref_id, "object")})
    if str(raw.get("type") or "") == "distance" and len(operands) == 1:
        linear = operands[0]
        point_ids = state.object_point_ids.get(linear["ref_id"], ())
        if linear["ref_kind"] in {"segment", "line"} and len(point_ids) == 2:
            return [
                {"role": f"point_{position + 1}", "ref_id": point_id, "ref_kind": "point"}
                for position, point_id in enumerate(point_ids)
            ]
    return operands

def _migrate_annotations(raw_annotations: Any, state: _MigrationState) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    source = raw_annotations if isinstance(raw_annotations, list) else []
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            continue
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        labels = _legacy_tokens(raw.get("target"))
        arms = metadata.get("arms")
        if isinstance(arms, list):
            labels.extend(str(value) for value in arms if isinstance(value, str))
        target_ids = [state.resolve_label(label, f"annotations[{index}].target") for label in labels]
        resolved = list(dict.fromkeys(ref for ref in target_ids if ref))
        if not resolved:
            state.warnings.append(f"annotations[{index}] không chuyển được target; đã bỏ")
            continue
        confidence = metadata.get("confidence")
        provenance = "verified" if confidence == "verified" else "given" if metadata.get("source") == "given" else "render_only"
        annotations.append({
            "id": str(raw.get("id") or state.stable_id("ann", index, str(raw.get("type") or ""))),
            "type": str(raw.get("type") or "annotation"),
            "target_ids": resolved,
            "label": raw.get("label"),
            "color": raw.get("color"),
            "provenance": provenance,
            "metadata": metadata,
        })
    return annotations


def _migrate_parameters(raw_parameters: Any, state: _MigrationState) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    source = raw_parameters if isinstance(raw_parameters, list) else []
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            continue
        parameter = dict(raw)
        parameter["id"] = str(raw.get("id") or state.stable_id("param", index, str(raw.get("name") or "")))
        parameters.append(parameter)
    return parameters


def _migrate_construction_steps(raw_steps: Any, state: _MigrationState) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    source = raw_steps if isinstance(raw_steps, list) else []
    for index, raw in enumerate(source):
        if not isinstance(raw, dict):
            continue
        object_ids = [value for value in raw.get("object_ids", []) if value in state.object_ids]
        relation_ids = [value for value in raw.get("relation_ids", []) if value in state.relation_ids]
        steps.append({
            "id": str(raw.get("id") or state.stable_id("step", index)),
            "description": str(raw.get("description") or ""),
            "object_ids": object_ids,
            "relation_ids": relation_ids,
        })
    return steps


def _resolve_many(values: Any, state: _MigrationState, context: str) -> list[str]:
    if not isinstance(values, (list, tuple)):
        state.unresolved.append(f"{context}: danh sách tham chiếu không hợp lệ")
        return []
    return [ref for index, value in enumerate(values) if (ref := state.resolve_label(str(value), f"{context}[{index}]"))]


def _has_missing_required_reference(obj: dict[str, Any]) -> bool:
    if obj["type"] in {"segment", "line_2d", "line_3d"}:
        return len(obj.get("point_ids") or []) != 2
    if obj["type"] in {"face", "plane"}:
        return len(obj.get("point_ids") or []) < 3
    if obj["type"] in {"vector_2d", "vector_3d"}:
        return not obj.get("from_point_id") or not obj.get("to_point_id")
    if obj["type"] in {"circle_2d", "sphere"}:
        return not obj.get("center_point_id")
    return False


def _legacy_relation_tokens(value: Any, state: _MigrationState) -> list[str]:
    if isinstance(value, str) and value.strip() in state.labels:
        return [value.strip()]
    return _legacy_tokens(value)


def _legacy_tokens(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    cleaned = re.sub(r"^(segment|line|plane)\((.*)\)$", r"\2", value.strip(), flags=re.IGNORECASE)
    if any(separator in cleaned for separator in ("-", ",", ":")):
        return [token.strip() for token in re.split(r"[-,:]", cleaned) if token.strip()]
    if len(cleaned) == 2 and cleaned.isalpha() and cleaned.upper() == cleaned:
        return list(cleaned)
    return [cleaned]


def _reference_kind_for_object_type(object_type: str) -> str:
    return {
        "point_2d": "point",
        "point_3d": "point",
        "segment": "segment",
        "line_2d": "line",
        "line_3d": "line",
        "vector_2d": "vector",
        "vector_3d": "vector",
        "circle_2d": "circle",
        "face": "face",
        "sphere": "sphere",
        "plane": "plane",
    }.get(object_type, "object")


def _stable_scene_id(scene: dict[str, Any]) -> str:
    seed = f"{scene.get('problem_text', '')}:{scene.get('renderer', '')}"
    return f"scene_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"