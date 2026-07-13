from __future__ import annotations

from typing import Any, Iterable

from app.schemas.scene_v3 import ConstraintResultV3, MathSceneV3, SceneObjectV3


def scene_v3_to_solver_input(
    scene: MathSceneV3,
    verification: Iterable[ConstraintResultV3] = (),
) -> dict[str, Any]:
    names = _object_names(scene)
    by_id = {obj.id: obj for obj in scene.objects}
    verification_by_relation = {
        relation.id: relation.verification
        for relation in scene.relations
        if relation.verification is not None
    }
    verification_by_relation.update({item.relation_id: item for item in verification})
    return {
        "schema_version": scene.schema_version,
        "scene_id": scene.scene_id,
        "revision": scene.revision,
        "problem_text": scene.problem_text,
        "topic": scene.topic,
        "renderer": scene.renderer,
        "objects": [_solver_object(obj, names) for obj in scene.objects],
        "relations": [
            _solver_relation(
                relation,
                names,
                by_id,
                verification_by_relation.get(relation.id),
            )
            for relation in scene.relations
        ],
        "annotations": [
            {
                "id": annotation.id,
                "type": annotation.type,
                "target_ids": list(annotation.target_ids),
                "target": "-".join(names.get(target_id, target_id) for target_id in annotation.target_ids),
                "label": annotation.label,
                "provenance": annotation.provenance,
                "relation_id": annotation.relation_id,
                "metadata": {
                    **annotation.metadata,
                    "source": "given" if annotation.provenance == "given" else annotation.provenance,
                    "confidence": "verified" if annotation.provenance == "verified" else "partial",
                },
            }
            for annotation in scene.annotations
        ],
        "derived_facts": [fact.model_dump(mode="json", exclude_none=True) for fact in scene.derived_facts],
        "construction_steps": [step.model_dump(mode="json", exclude_none=True) for step in scene.construction_steps],
        "parameters": [parameter.model_dump(mode="json") for parameter in scene.parameters],
    }


def scene_v3_to_variants_input(scene: MathSceneV3) -> dict[str, Any]:
    return scene.model_dump(mode="json", exclude_none=True, exclude_defaults=False)


def _object_names(scene: MathSceneV3) -> dict[str, str]:
    names = {obj.id: (obj.label or obj.id) for obj in scene.objects}
    point_names = [names[obj.id] for obj in scene.objects if obj.type in {"point_2d", "point_3d"}]
    duplicates = sorted({name for name in point_names if point_names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Label điểm không duy nhất: {', '.join(duplicates)}")
    return names


def _solver_object(obj: SceneObjectV3, names: dict[str, str]) -> dict[str, Any]:
    data = obj.model_dump(mode="json", exclude_none=True)
    data["object_id"] = obj.id
    data["name"] = names[obj.id]
    data.pop("label", None)
    if "point_ids" in data:
        refs = [names[point_id] for point_id in data.pop("point_ids")]
        data["through" if obj.type in {"line_2d", "line_3d"} else "points"] = refs
    if "from_point_id" in data:
        data["from_point"] = names[data.pop("from_point_id")]
        data["to_point"] = names[data.pop("to_point_id")]
    if "center_point_id" in data:
        data["center"] = names[data.pop("center_point_id")]
    if data.get("through_point_id") is not None:
        data["through"] = names[data.pop("through_point_id")]
    else:
        data.pop("through_point_id", None)
    return data


def _solver_relation(
    relation,
    names: dict[str, str],
    by_id: dict[str, SceneObjectV3],
    verification: ConstraintResultV3 | None,
) -> dict[str, Any]:
    operand_names = [names.get(operand.ref_id, operand.ref_id) for operand in relation.operands]
    classic_tokens = [
        _classic_token(operand, names, by_id)
        for operand in relation.operands
    ]
    confidence = verification.status if verification is not None else "unverified"
    metadata = {
        **relation.metadata,
        **relation.args,
        "source": "given" if relation.source == "given" else "inferred",
        "confidence": confidence,
    }
    return {
        "id": relation.id,
        "type": relation.type,
        "operands": [operand.model_dump(mode="json") for operand in relation.operands],
        "operand_names": operand_names,
        # Classical engines parse edge/plane tokens; expand segment/plane to A-B / plane(ABC).
        "object_1": classic_tokens[0] if classic_tokens else None,
        "object_2": classic_tokens[1] if len(classic_tokens) > 1 else None,
        "args": relation.args,
        "source": relation.source,
        "verification": verification.model_dump(mode="json", exclude_none=True) if verification is not None else None,
        "metadata": metadata,
    }


def _classic_token(operand, names: dict[str, str], by_id: dict[str, SceneObjectV3]) -> str:
    """Map typed operand to classical label token used by geometry_facts parsers."""
    obj = by_id.get(operand.ref_id)
    label = names.get(operand.ref_id, operand.ref_id)
    if obj is None:
        return label
    if obj.type in {"segment", "line_2d", "line_3d"}:
        point_ids = list(getattr(obj, "point_ids", ()) or ())
        if len(point_ids) >= 2:
            a = names.get(point_ids[0], point_ids[0])
            b = names.get(point_ids[1], point_ids[1])
            return f"{a}-{b}"
    if obj.type in {"vector_2d", "vector_3d"}:
        a = names.get(obj.from_point_id, obj.from_point_id)
        b = names.get(obj.to_point_id, obj.to_point_id)
        return f"{a}-{b}"
    if obj.type in {"face", "plane"}:
        pts = [names.get(pid, pid) for pid in list(getattr(obj, "point_ids", []) or [])]
        if len(pts) >= 3:
            return f"plane({''.join(pts)})"
    return label


__all__ = ["scene_v3_to_solver_input", "scene_v3_to_variants_input"]
