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


def migrate_scene_v2_dict(scene: dict[str, Any]) -> tuple[MathSceneV3, SceneMigrationReport]:
    if scene.get("schema_version") == "3.0":
        return MathSceneV3.model_validate(scene), SceneMigrationReport(source_version="3.0")

    source_version = str(scene.get("schema_version") or "2.0")
    scene_id = str(scene.get("scene_id") or _stable_scene_id(scene))
    state = _MigrationState(scene_id=scene_id)
    objects = _migrate_objects(scene.get("objects"), state)
    relations = _migrate_relations(scene.get("relations"), state)
    annotations = _migrate_annotations(scene.get("annotations"), state)
    parameters = _migrate_parameters(scene.get("parameters"), state)
    steps = _migrate_construction_steps(scene.get("construction_steps"), state)
    interpretation = scene.get("interpretation") if isinstance(scene.get("interpretation"), dict) else {}
    audit = scene.get("audit") if isinstance(scene.get("audit"), dict) else {}

    migrated = MathSceneV3.model_validate({
        "scene_id": scene_id,
        "schema_version": "3.0",
        "revision": max(1, int(scene.get("revision") or 1)),
        "problem_text": str(scene.get("problem_text") or ""),
        "grade": scene.get("grade"),
        "topic": scene.get("topic") or "unknown",
        "renderer": scene.get("renderer") or "geogebra_2d",
        "objects": objects,
        "relations": relations,
        "annotations": annotations,
        "derived_facts": [],
        "parameters": parameters,
        "view": scene.get("view") or {"dimension": "2d"},
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
            obj["point_ids"] = _resolve_many(obj.pop("through", []), state, f"objects[{index}].through")
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
        migrated.append(obj)
    return migrated


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
        relation = {
            "id": relation_id,
            "type": str(raw.get("type") or "unknown"),
            "operands": operands,
            "args": raw.get("args") if isinstance(raw.get("args"), dict) else {},
            "source": raw.get("source") or "ai_inferred",
            "verification": None,
            "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
        }
        state.relation_ids.add(relation_id)
        relations.append(relation)
    return relations


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