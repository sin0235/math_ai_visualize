"""Native MathSceneV3 extraction and one-shot LLM repair.

Bypasses the v2 extractor + migrate_scene_v2_dict bridge that produced
RELATION_CONTRACT_INVALID when shorthand edges (AB) were split into points.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator

from pydantic import ValidationError

from app.db.session import DatabaseClient
from app.schemas.scene import AdvancedRenderSettings, RuntimeSettings
from app.schemas.scene_v3 import MathSceneV3
from app.services.ai_prompt import (
    SCENE_EXTRACTION_V3_SYSTEM_PROMPT,
    SCENE_REPAIR_V3_SYSTEM_PROMPT,
    build_scene_repair_v3_prompt,
    get_system_prompts,
)
from app.services.ai_provider_runtime import (
    RenderAttempt,
    RenderFallbackSource,
    _RENDER_MAX_ATTEMPT_SECONDS,
    _RENDER_MIN_ATTEMPT_SECONDS,
    _RENDER_TOTAL_BUDGET_SECONDS,
    _extract_with_provider,
    _format_tier_render_failure,
    _log_render_attempt_failure,
    _render_attempt_warnings,
    _render_budget_remaining,
    _run_reasoning_stage,
    _short_error,
)
from app.services.model_provider import canonical_provider_id
from app.services.model_registry import (
    load_model_registry,
    model_supports_thinking,
    registry_from_settings,
    resolve_effective_settings,
    resolve_render_tier_candidates,
    resolve_task_profile,
)
from app.services.scene_pipeline_v3 import PipelineIssueV3
from app.services.scene_fidelity_v3 import (
    complete_standard_solid_topology,
    repair_optional_scene_references,
    repair_standard_solid_references,
    validate_scene_fidelity,
)
from app.services.scene_goal_visualization_v3 import (
    complete_metric_goal_visualizations,
    reserved_annotation_metadata_key,
)
from app.services.scene_angle_goal_visualization_v3 import complete_angle_goal_visualization

logger = logging.getLogger(__name__)

_POINT_2D_RE = re.compile(r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_POINT_3D_RE = re.compile(
    r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)"
)
_RELATION_SOURCE_ALIASES = {
    "given": "given",
    "construction": "construction",
    "render_only": "construction",
    "inferred": "ai_inferred",
    "ai_inferred": "ai_inferred",
    "computed": "ai_inferred",
    "verified": "ai_inferred",
    "user_created": "user_created",
}
_DERIVED_PROVENANCE_ALIASES = {
    "given": "given",
    "verified": "verified",
    "computed": "computed",
    "inferred": "computed",
    "ai_inferred": "computed",
    "construction": "render_only",
    "render_only": "render_only",
}
_ANNOTATION_PROVENANCE_ALIASES = {
    **_DERIVED_PROVENANCE_ALIASES,
    "inferred": "render_only",
    "ai_inferred": "render_only",
}


@dataclass(frozen=True)
class ExtractSceneV3Result:
    scene: MathSceneV3
    warnings: list[str] = field(default_factory=list)
    degraded: bool = False
    fallback_source: RenderFallbackSource = "none"
    provider: str | None = None
    model: str | None = None
    attempts: list[RenderAttempt] = field(default_factory=list)
    repaired: bool = False

    def __iter__(self) -> Iterator[Any]:
        yield self.scene
        yield self.warnings


def _secure_v3_prompt() -> str:
    from app.services.ai_prompt import _secure_system_prompt

    return _secure_system_prompt(SCENE_EXTRACTION_V3_SYSTEM_PROMPT)


def _secure_repair_prompt() -> str:
    from app.services.ai_prompt import _secure_system_prompt

    return _secure_system_prompt(SCENE_REPAIR_V3_SYSTEM_PROMPT)


def _stable_scene_id(problem_text: str) -> str:
    digest = hashlib.sha256(problem_text.encode("utf-8")).hexdigest()[:12]
    return f"scene_{digest}"


def _compat_value(value: Any, mapping: dict[str, str], *, path: str) -> str:
    key = value.strip().lower() if isinstance(value, str) else ""
    if key not in mapping:
        raise ValueError(f"{path} có giá trị compatibility không hỗ trợ: {value!r}")
    return mapping[key]


def _log_compatibility(code: str, path: str) -> None:
    logger.warning(
        "Scene v3 compatibility normalization code=%s path=%s",
        code,
        path,
        extra={"compatibility_code": code, "path": path},
    )


def _normalize_relation_contract(relation: dict[str, Any], index: int) -> None:
    path = f"relations.{index}"
    source = relation.get("source")
    provenance = relation.get("provenance")
    normalized_source = (
        _compat_value(source, _RELATION_SOURCE_ALIASES, path=f"{path}.source")
        if source is not None
        else None
    )
    normalized_provenance = (
        _compat_value(provenance, _RELATION_SOURCE_ALIASES, path=f"{path}.provenance")
        if provenance is not None
        else None
    )
    if normalized_source is not None and normalized_provenance is not None and normalized_source != normalized_provenance:
        raise ValueError(f"{path}.source mâu thuẫn với {path}.provenance")
    if normalized_provenance is not None:
        relation.pop("provenance")
        _log_compatibility("relation_provenance_alias", f"{path}.provenance")
    normalized = normalized_source or normalized_provenance
    if normalized is not None:
        if source is not None and source != normalized:
            _log_compatibility("relation_source_alias", f"{path}.source")
        relation["source"] = normalized


def _normalize_annotation_contract(annotation: dict[str, Any], index: int) -> None:
    path = f"annotations.{index}"
    provenance = annotation.get("provenance")
    if provenance is not None:
        normalized = _compat_value(
            provenance,
            _ANNOTATION_PROVENANCE_ALIASES,
            path=f"{path}.provenance",
        )
        if normalized != provenance:
            annotation["provenance"] = normalized
            _log_compatibility("annotation_provenance_alias", f"{path}.provenance")

    if "render_only" not in annotation:
        return
    render_only = annotation.pop("render_only")
    if not isinstance(render_only, bool):
        raise ValueError(f"{path}.render_only phải là boolean")
    current = annotation.get("provenance")
    if render_only:
        if current is not None and current != "render_only":
            raise ValueError(f"{path}.render_only mâu thuẫn với {path}.provenance")
        annotation["provenance"] = "render_only"
    elif current is None:
        raise ValueError(f"{path}.render_only=false cần provenance tường minh")
    _log_compatibility("annotation_render_only_alias", f"{path}.render_only")


def _normalize_derived_fact_contract(fact: dict[str, Any], index: int) -> None:
    path = f"derived_facts.{index}"
    if "object_ids" in fact:
        object_ids = fact.pop("object_ids")
        if not isinstance(object_ids, list):
            raise ValueError(f"{path}.object_ids phải là list")
        if "source_ids" in fact and fact["source_ids"] != object_ids:
            raise ValueError(f"{path}.source_ids mâu thuẫn với {path}.object_ids")
        fact["source_ids"] = object_ids
        _log_compatibility("derived_fact_object_ids_alias", f"{path}.object_ids")

    text_values = [fact[key] for key in ("statement", "text") if key in fact]
    if text_values:
        if any(not isinstance(value, str) or not value.strip() for value in text_values):
            raise ValueError(f"{path}.statement/text phải là chuỗi không rỗng")
        if len(set(text_values)) > 1:
            raise ValueError(f"{path}.statement mâu thuẫn với {path}.text")
        value = fact.get("value")
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ValueError(f"{path}.value phải là object")
        if value.get("text") not in (None, text_values[0]):
            raise ValueError(f"{path}.value.text mâu thuẫn với statement/text")
        fact["value"] = {**value, "text": text_values[0]}
        for key in ("statement", "text"):
            if key in fact:
                fact.pop(key)
                _log_compatibility("derived_fact_text_alias", f"{path}.{key}")
        if "kind" not in fact:
            fact["kind"] = "annotation"
            _log_compatibility("derived_fact_kind_default", f"{path}.kind")

    provenance = fact.get("provenance")
    source = fact.get("source")
    normalized_provenance = (
        _compat_value(provenance, _DERIVED_PROVENANCE_ALIASES, path=f"{path}.provenance")
        if provenance is not None
        else None
    )
    normalized_source = (
        _compat_value(source, _DERIVED_PROVENANCE_ALIASES, path=f"{path}.source")
        if source is not None
        else None
    )
    if normalized_provenance is not None and normalized_source is not None and normalized_provenance != normalized_source:
        raise ValueError(f"{path}.provenance mâu thuẫn với {path}.source")
    if source is not None:
        fact.pop("source")
        _log_compatibility("derived_fact_source_alias", f"{path}.source")
    normalized = normalized_provenance or normalized_source
    if normalized is not None:
        if provenance is not None and provenance != normalized:
            _log_compatibility("derived_fact_provenance_alias", f"{path}.provenance")
        fact["provenance"] = normalized


def normalize_scene_v3_json(raw: dict[str, Any], *, problem_text: str, grade: int | None) -> dict[str, Any]:
    """Coerce common LLM omissions into a MathSceneV3-shaped dict."""
    data = dict(raw)
    data["schema_version"] = "3.0"
    data["revision"] = max(1, int(data.get("revision") or 1))
    data["problem_text"] = problem_text
    if grade is not None:
        data["grade"] = grade
    elif data.get("grade") is None:
        data["grade"] = None
    data["scene_id"] = str(data.get("scene_id") or _stable_scene_id(problem_text))
    data.setdefault("topic", "unknown")
    data.setdefault("renderer", "geogebra_2d")
    data.setdefault("objects", [])
    data.setdefault("relations", [])
    data.setdefault("annotations", [])
    data.setdefault("parameters", [])
    data.setdefault("derived_facts", [])
    data.setdefault("construction_steps", [])
    if not isinstance(data.get("view"), dict):
        dim = "3d" if data.get("renderer") == "threejs_3d" else "2d"
        data["view"] = {"dimension": dim, "show_axes": True, "show_grid": True, "show_coordinates": False}
    if not isinstance(data.get("interpretation"), dict):
        data["interpretation"] = {}
    data["interpretation"] = _normalize_interpretation_v3(data["interpretation"])
    audit = data.get("audit") if isinstance(data.get("audit"), dict) else {}
    audit.setdefault("created_by", "ai")
    data["audit"] = audit

    # Ensure ids on list items when LLM omits them.
    for index, obj in enumerate(data.get("objects") or []):
        if isinstance(obj, dict) and not obj.get("id"):
            kind = str(obj.get("type") or "obj")
            label = str(obj.get("label") or index)
            obj["id"] = f"{kind}_{hashlib.sha256(f'{label}:{index}'.encode()).hexdigest()[:10]}"
    for index, rel in enumerate(data.get("relations") or []):
        if isinstance(rel, dict) and not rel.get("id"):
            rel["id"] = f"rel_{index}_{uuid.uuid4().hex[:8]}"
        if isinstance(rel, dict):
            _normalize_relation_contract(rel, index)
            rel.setdefault("source", "ai_inferred")
            rel.setdefault("args", {})
            rel.setdefault("metadata", {})
    for index, fact in enumerate(data.get("derived_facts") or []):
        if isinstance(fact, dict):
            _normalize_derived_fact_contract(fact, index)
    data = _normalize_metric_goal_relations_v3(data)
    for index, ann in enumerate(data.get("annotations") or []):
        if isinstance(ann, dict) and not ann.get("id"):
            ann["id"] = f"ann_{index}_{uuid.uuid4().hex[:8]}"
        if isinstance(ann, dict):
            _normalize_annotation_contract(ann, index)
            metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
            metadata.pop(reserved_annotation_metadata_key(), None)
            ann["metadata"] = metadata
            ann.setdefault("provenance", "render_only")
            # Accept legacy target string → target_ids.
            if "target_ids" not in ann and ann.get("target"):
                target = ann.pop("target")
                ann["target_ids"] = [target] if isinstance(target, str) else list(target)
            # Numeric edge lengths from the problem are given facts, not render-only labels.
            if ann.get("type") == "length" and ann.get("provenance") == "render_only":
                label = str(ann.get("label") or "").strip()
                if re.fullmatch(r"-?\d+(?:\.\d+)?", label):
                    ann["provenance"] = "given"

    data["parameters"] = _normalize_parameters_v3(data.get("parameters") or [])
    data["construction_steps"] = _normalize_construction_steps_v3(data.get("construction_steps") or [])

    return data


def _normalize_interpretation_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """Giữ lại scalar do LLM trả về nhưng đưa về contract values dạng object."""
    interpretation = dict(raw)
    values = interpretation.get("values")
    if not isinstance(values, list):
        values = []
    interpretation["values"] = [item if isinstance(item, dict) else {"value": item} for item in values]
    return interpretation


_METRIC_EXPECTED_ARGS = {
    "distance": "value",
    "angle": "degrees",
    "ratio": "value",
}


def _normalize_metric_goal_relations_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Chuyển đại lượng cần tìm khỏi relation constraint nhưng vẫn giữ intent hiển thị."""
    relations: list[Any] = list(data.get("relations") or [])
    derived_facts: list[Any] = list(data.get("derived_facts") or [])
    used_ids = {
        str(item.get("id"))
        for collection in (data.get("objects") or [], relations, data.get("annotations") or [], derived_facts)
        for item in collection
        if isinstance(item, dict) and item.get("id")
    }
    kept_relations: list[Any] = []
    removed_relation_ids: set[str] = set()

    for index, relation in enumerate(relations):
        if not isinstance(relation, dict):
            kept_relations.append(relation)
            continue
        relation_type = str(relation.get("type") or "").strip().lower()
        expected_arg = _METRIC_EXPECTED_ARGS.get(relation_type)
        if expected_arg is None:
            kept_relations.append(relation)
            continue
        args = relation.get("args") if isinstance(relation.get("args"), dict) else {}
        if relation_type == "angle" and "degrees" not in args and _is_metric_number(args.get("value")):
            args = {**args, "degrees": args["value"]}
            relation["args"] = args
        if _is_metric_number(args.get(expected_arg)):
            kept_relations.append(relation)
            continue
        source = str(relation.get("source") or "ai_inferred").strip().lower()
        if source not in {"ai_inferred", "construction"}:
            kept_relations.append(relation)
            continue

        relation_id = str(relation.get("id") or f"metric_{index}")
        removed_relation_ids.add(relation_id)
        fact_id = _unique_normalized_id(f"goal_{relation_id}", used_ids)
        source_ids = list(dict.fromkeys(
            str(operand.get("ref_id"))
            for operand in relation.get("operands") or []
            if isinstance(operand, dict) and operand.get("ref_id")
        ))
        derived_facts.append({
            "id": fact_id,
            "kind": "measurement",
            "source_ids": source_ids,
            "value": {
                "role": "goal",
                "quantity": relation_type,
                "text": f"Đại lượng {relation_type} cần được tính từ đề bài.",
            },
            "provenance": "render_only",
        })

    data["relations"] = kept_relations
    data["derived_facts"] = derived_facts
    interpretation = data.get("interpretation")
    if removed_relation_ids and isinstance(interpretation, dict):
        interpretation["relation_ids"] = [
            relation_id
            for relation_id in interpretation.get("relation_ids") or []
            if relation_id not in removed_relation_ids
        ]
    _validate_metric_relation_args_v3(kept_relations)
    return data


def _validate_metric_relation_args_v3(relations: list[Any]) -> None:
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = str(relation.get("type") or "").strip().lower()
        expected_arg = _METRIC_EXPECTED_ARGS.get(relation_type)
        if expected_arg is None:
            continue
        args = relation.get("args") if isinstance(relation.get("args"), dict) else {}
        if not _is_metric_number(args.get(expected_arg)):
            relation_id = str(relation.get("id") or relation_type)
            raise ValueError(f"Relation {relation_id} cần args.{expected_arg}")


def _is_metric_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unique_normalized_id(preferred: str, used_ids: set[str]) -> str:
    if preferred not in used_ids:
        used_ids.add(preferred)
        return preferred
    suffix = 2
    while f"{preferred}_{suffix}" in used_ids:
        suffix += 1
    result = f"{preferred}_{suffix}"
    used_ids.add(result)
    return result


def _normalize_parameters_v3(raw: Any) -> list[dict[str, Any]]:
    """Coerce LLM parameter dicts into ParameterV3 fields (min/max/default/step)."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("id") or f"p{index}").strip() or f"p{index}"
        default = item.get("default")
        if default is None:
            default = item.get("value")
        try:
            default_f = float(default) if default is not None else 1.0
        except (TypeError, ValueError):
            default_f = 1.0
        try:
            min_f = float(item["min"]) if item.get("min") is not None else min(0.0, default_f)
            max_f = float(item["max"]) if item.get("max") is not None else max(default_f * 2 if default_f else 10.0, default_f + 1.0)
            step_f = float(item["step"]) if item.get("step") is not None else 0.1
        except (TypeError, ValueError):
            min_f, max_f, step_f = min(0.0, default_f), max(default_f + 1.0, 10.0), 0.1
        if min_f > max_f:
            min_f, max_f = max_f, min_f
        if not min_f <= default_f <= max_f:
            default_f = min(max(default_f, min_f), max_f)
        if step_f <= 0:
            step_f = 0.1
        out.append({
            "id": str(item.get("id") or f"param_{name}"),
            "name": name,
            "label": item.get("label") or name,
            "min": min_f,
            "max": max_f,
            "default": default_f,
            "step": step_f,
        })
    return out


def _normalize_construction_steps_v3(raw: Any) -> list[dict[str, Any]]:
    """Keep only ConstructionStepV3 fields; map action → description when needed."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or item.get("action") or item.get("text") or "").strip()
        if not description:
            continue
        out.append({
            "id": str(item.get("id") or f"construction_{index}"),
            "description": description,
            "object_ids": [str(x) for x in (item.get("object_ids") or []) if x],
            "relation_ids": [str(x) for x in (item.get("relation_ids") or []) if x],
        })
    return out


def parse_math_scene_v3(raw: dict[str, Any], *, problem_text: str, grade: int | None) -> MathSceneV3:
    normalized = normalize_scene_v3_json(raw, problem_text=problem_text, grade=grade)
    repaired = repair_standard_solid_references(normalized, problem_text=problem_text)
    repaired = repair_optional_scene_references(repaired)
    scene = MathSceneV3.model_validate(repaired)
    scene = complete_standard_solid_topology(scene)
    scene = complete_metric_goal_visualizations(scene)
    scene = complete_angle_goal_visualization(scene)
    fidelity_issues = validate_scene_fidelity(scene)
    if fidelity_issues:
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in fidelity_issues)
        raise ValueError(f"Scene fidelity không đạt: {details}")
    return scene


def extract_scene_v3_mock(problem_text: str, grade: int | None = None) -> MathSceneV3:
    """Deterministic native mock for offline/fallback paths."""
    text = problem_text.strip()
    points_3d = [
        {"id": f"pt_{name.lower()}", "type": "point_3d", "label": name, "x": float(x), "y": float(y), "z": float(z)}
        for name, x, y, z in _POINT_3D_RE.findall(text)
    ]
    if points_3d:
        objects: list[dict[str, Any]] = list(points_3d)
        ids = [obj["id"] for obj in points_3d]
        for start, end in zip(ids, ids[1:]):
            objects.append({
                "id": f"seg_{start}_{end}",
                "type": "segment",
                "point_ids": [start, end],
            })
        return parse_math_scene_v3(
            {
                "topic": "coordinate_3d",
                "renderer": "threejs_3d",
                "objects": objects,
                "view": {"dimension": "3d"},
                "audit": {"created_by": "mock"},
            },
            problem_text=text,
            grade=grade,
        )

    points_2d = [
        {"id": f"pt_{name.lower()}", "type": "point_2d", "label": name, "x": float(x), "y": float(y)}
        for name, x, y in _POINT_2D_RE.findall(text)
    ]
    objects = list(points_2d)
    if len(points_2d) >= 2:
        objects.append({
            "id": f"seg_{points_2d[0]['id']}_{points_2d[1]['id']}",
            "type": "segment",
            "label": f"{points_2d[0]['label']}{points_2d[1]['label']}",
            "point_ids": [points_2d[0]["id"], points_2d[1]["id"]],
        })
    return parse_math_scene_v3(
        {
            "topic": "coordinate_2d" if points_2d else "unknown",
            "renderer": "geogebra_2d",
            "objects": objects,
            "view": {"dimension": "2d", "show_coordinates": bool(points_2d)},
            "audit": {"created_by": "mock"},
        },
        problem_text=text,
        grade=grade,
    )


async def extract_scene_v3(
    problem_text: str,
    grade: int | None = None,
    tier: str = "tier1",
    advanced_settings: AdvancedRenderSettings | None = None,
    db: DatabaseClient | None = None,
    preferred_ai_provider: str | None = None,
    preferred_ai_model: str | None = None,
    runtime_settings: RuntimeSettings | None = None,
    nlp_hints: dict[str, Any] | None = None,
) -> ExtractSceneV3Result:
    """Extract MathSceneV3 natively (reason → extract) without v2 bridge."""
    settings = await resolve_effective_settings(db, runtime_settings)
    registry = await load_model_registry(db, settings) if db is not None else registry_from_settings(settings)
    render_settings = advanced_settings or AdvancedRenderSettings()
    warnings: list[str] = []
    attempts: list[RenderAttempt] = []
    use_two_stage = render_settings.reasoning_layer in ("auto", "force")
    started_at = time.monotonic()
    _, reasoning_sys_prompt = await get_system_prompts(db)
    scene_sys_prompt = _secure_v3_prompt()
    # NLP hints go only into the extract/reasoning prompt context — never into warnings
    # (those demote pipeline trust) and never rewrite problem_text.
    extraction_text = problem_text
    if nlp_hints:
        logger.info("NLP hints attached to Scene v3 extract; problem_text left immutable.")

    legacy_override = preferred_ai_provider is not None or preferred_ai_model is not None
    if not legacy_override:
        render_candidates = resolve_render_tier_candidates(registry, tier)
        reasoning_plan: dict | None = None
        if use_two_stage:
            try:
                reasoning_profile = resolve_task_profile(registry, "reasoning")
                reasoning_provider = canonical_provider_id(reasoning_profile.provider_id)
                reasoning_model = reasoning_profile.model_id
            except ValueError as error:
                warnings.append(f"Bỏ qua reasoning layer (profile không hợp lệ): {error}")
                use_two_stage = False
                reasoning_provider = None
                reasoning_model = None
            else:
                if reasoning_provider and reasoning_model:
                    reasoning_plan = await _run_reasoning_stage(
                        settings,
                        extraction_text,
                        grade,
                        reasoning_provider,
                        reasoning_model,
                        warnings,
                        system_prompt=reasoning_sys_prompt,
                        model_supports_thinking=model_supports_thinking(
                            registry, reasoning_provider, reasoning_model
                        ),
                        thinking_enabled=render_settings.thinking_enabled,
                    )
                    if reasoning_plan is not None:
                        logger.info("Scene v3 reasoning layer completed for tier extract.")

        if not render_candidates:
            raise RuntimeError(f"Tier {tier} chưa cấu hình model khả dụng trong ai_task_profiles.")

        for candidate in render_candidates:
            remaining = _render_budget_remaining(started_at)
            if remaining < _RENDER_MIN_ATTEMPT_SECONDS:
                raise RuntimeError(
                    _format_tier_render_failure(f"Tier {tier} đã gần hết thời gian.", attempts)
                )
            attempt_timeout = min(remaining, _RENDER_MAX_ATTEMPT_SECONDS)
            provider_id = canonical_provider_id(candidate.provider_id) or candidate.provider_id
            try:
                scene_json = await asyncio.wait_for(
                    _extract_with_provider(
                        provider_id,
                        settings,
                        extraction_text,
                        grade,
                        render_settings.reasoning_layer,
                        registry,
                        preferred_ai_model=candidate.model_id,
                        reasoning_plan=reasoning_plan,
                        system_prompt=scene_sys_prompt,
                        model_supports_thinking=model_supports_thinking(
                            registry, candidate.provider_id, candidate.model_id
                        ),
                        thinking_enabled=render_settings.thinking_enabled,
                        nlp_hints=nlp_hints,
                        schema_version="3.0",
                    ),
                    timeout=attempt_timeout,
                )
                scene = parse_math_scene_v3(scene_json, problem_text=problem_text, grade=grade)
                if preferred_ai_provider is None:
                    # bind preferred renderer later in route
                    pass
                return ExtractSceneV3Result(
                    scene=scene,
                    warnings=[*warnings, *_render_attempt_warnings(attempts)],
                    provider=provider_id,
                    model=candidate.model_id,
                    attempts=attempts,
                )
            except TimeoutError:
                attempt = RenderAttempt(provider_id, candidate.model_id, f"timeout after {attempt_timeout:.0f}s")
                attempts.append(attempt)
                _log_render_attempt_failure(attempt, stage="timeout")
            except (RuntimeError, ValidationError, ValueError, KeyError, TypeError) as error:
                attempt = RenderAttempt(provider_id, candidate.model_id, str(error))
                attempts.append(attempt)
                _log_render_attempt_failure(attempt, stage="extract_v3")
            except Exception as error:  # noqa: BLE001 — collect provider failures then try next
                attempt = RenderAttempt(provider_id, candidate.model_id, str(error) or error.__class__.__name__)
                attempts.append(attempt)
                _log_render_attempt_failure(attempt, stage="extract_v3")

        warnings.extend(_render_attempt_warnings(attempts))
        # Fail-closed: never ship a mock geometry figure as a successful render
        # unless explicitly enabled (local tests only).
        if settings.allow_render_mock:
            warnings.append("ALLOW_RENDER_MOCK=1: dùng mock native vì mọi provider thất bại.")
            return ExtractSceneV3Result(
                scene=extract_scene_v3_mock(problem_text, grade),
                warnings=warnings,
                degraded=True,
                fallback_source="mock",
                attempts=attempts,
            )
        summary = _format_tier_render_failure(
            "Tất cả AI provider Scene v3 đều thất bại; không dựng hình giả (mock).",
            attempts,
        )
        raise RuntimeError(summary)

    # Explicit provider/model override path (legacy request fields).
    preferred_provider = canonical_provider_id(preferred_ai_provider) or preferred_ai_provider
    if not preferred_provider:
        raise RuntimeError("preferred_ai_provider không hợp lệ.")
    model_id = preferred_ai_model or ""
    try:
        scene_json = await asyncio.wait_for(
            _extract_with_provider(
                preferred_provider,
                settings,
                extraction_text,
                grade,
                render_settings.reasoning_layer,
                registry,
                preferred_ai_model=model_id or None,
                system_prompt=scene_sys_prompt,
                model_supports_thinking=model_supports_thinking(registry, preferred_provider, model_id)
                if model_id
                else None,
                thinking_enabled=render_settings.thinking_enabled,
                nlp_hints=nlp_hints,
                schema_version="3.0",
            ),
            timeout=min(_RENDER_TOTAL_BUDGET_SECONDS, _RENDER_MAX_ATTEMPT_SECONDS),
        )
        scene = parse_math_scene_v3(scene_json, problem_text=problem_text, grade=grade)
        return ExtractSceneV3Result(
            scene=scene,
            warnings=warnings,
            provider=preferred_provider,
            model=model_id or None,
            attempts=attempts,
        )
    except Exception as error:
        raise RuntimeError(f"Extract Scene v3 thất bại ({preferred_provider}): {_short_error(str(error))}") from error


def issues_to_repair_payload(issues: tuple[PipelineIssueV3, ...] | list[PipelineIssueV3]) -> list[dict[str, Any]]:
    return [
        {
            "stage": issue.stage,
            "code": issue.code,
            "message": issue.message,
            "severity": issue.severity,
            "target_id": issue.target_id,
        }
        for issue in issues
        if issue.severity == "error"
    ]


async def repair_scene_v3(
    scene: MathSceneV3,
    issues: tuple[PipelineIssueV3, ...] | list[PipelineIssueV3],
    *,
    problem_text: str,
    grade: int | None,
    tier: str,
    advanced_settings: AdvancedRenderSettings | None,
    db: DatabaseClient | None,
    runtime_settings: RuntimeSettings | None = None,
    reasoning_plan: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
    byok_client: Any | None = None,
) -> MathSceneV3 | None:
    """One LLM repair pass using structured pipeline issues. Returns None if repair fails."""
    error_issues = issues_to_repair_payload(issues)
    if not error_issues:
        return None

    settings = await resolve_effective_settings(db, runtime_settings)
    registry = await load_model_registry(db, settings) if db is not None else registry_from_settings(settings)
    render_settings = advanced_settings or AdvancedRenderSettings()

    user_prompt = build_scene_repair_v3_prompt(
        problem_text,
        scene.model_dump(mode="json"),
        error_issues,
        reasoning_plan=reasoning_plan,
    )

    # Prefer the same BYOK client that produced the broken scene (user's key).
    if byok_client is not None:
        try:
            scene_json = await asyncio.wait_for(
                byok_client.extract_scene_json(
                    problem_text,
                    grade,
                    "off",
                    system_prompt=_secure_repair_prompt(),
                    user_prompt=user_prompt,
                    schema_version="3.0",
                ),
                timeout=_RENDER_MAX_ATTEMPT_SECONDS,
            )
            repaired = parse_math_scene_v3(scene_json, problem_text=problem_text, grade=grade)
            logger.info("Scene v3 repair succeeded via BYOK client")
            return repaired
        except Exception as error:  # noqa: BLE001
            logger.warning("Scene v3 repair failed via BYOK client: %s", error)

    candidates: list[tuple[str, str]] = []
    if provider and model:
        candidates.append((provider, model))
    for candidate in resolve_render_tier_candidates(registry, tier):
        pid = canonical_provider_id(candidate.provider_id) or candidate.provider_id
        pair = (pid, candidate.model_id)
        if pair not in candidates:
            candidates.append(pair)

    for provider_id, model_id in candidates[:3]:
        try:
            # Dedicated repair user_prompt channel — never smuggle into problem_text.
            scene_json = await asyncio.wait_for(
                _extract_with_provider(
                    provider_id,
                    settings,
                    problem_text,
                    grade,
                    "off",
                    registry,
                    preferred_ai_model=model_id,
                    system_prompt=_secure_repair_prompt(),
                    model_supports_thinking=model_supports_thinking(registry, provider_id, model_id),
                    thinking_enabled=render_settings.thinking_enabled,
                    user_prompt=user_prompt,
                    schema_version="3.0",
                ),
                timeout=_RENDER_MAX_ATTEMPT_SECONDS,
            )
            repaired = parse_math_scene_v3(scene_json, problem_text=problem_text, grade=grade)
            logger.info("Scene v3 repair succeeded via %s/%s", provider_id, model_id)
            return repaired
        except Exception as error:  # noqa: BLE001
            logger.warning("Scene v3 repair failed via %s/%s: %s", provider_id, model_id, error)
            continue
    return None
