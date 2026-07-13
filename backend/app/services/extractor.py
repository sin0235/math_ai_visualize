"""Legacy MathScene helpers kept for function-analyzer graphs and expression eval.

Geometry render extraction is Scene v3 only (`extractor_v3`). Shared AI runtime
lives in `ai_provider_runtime`.
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas.scene import MathScene

from app.services.ai_provider_runtime import (
    RenderAttempt,
    RenderFallbackSource,
    _RENDER_MAX_ATTEMPT_SECONDS,
    _RENDER_MIN_ATTEMPT_SECONDS,
    _RENDER_TOTAL_BUDGET_SECONDS,
    _REASONING_TOTAL_TIMEOUT_SECONDS,
    _extract_with_provider,
    _format_tier_render_failure,
    _log_render_attempt_failure,
    _profile_model_candidates,
    _provider_order,
    _render_attempt_warnings,
    _render_budget_remaining,
    _run_reasoning_stage,
    _short_error,
)
from app.services.expression_eval import try_safe_eval, try_safe_eval_exact

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_COLOR_NAMES = {
    "red": "#e63946",
    "blue": "#1d3557",
    "green": "#2a9d8f",
    "orange": "#f97316",
    "purple": "#7c3aed",
    "gray": "#8b95a7",
    "grey": "#8b95a7",
    "yellow": "#ffd166",
}
_DEFAULT_COLORS = {
    "segment": "#1d3557",
    "face": "#5da9ff",
    "sphere": "#5da9ff",
    "plane": "#4f8cff",
    "line_3d": "#1d3557",
    "vector_3d": "#7c3aed",
    "angle": "#b45309",
    "length": "#7c3aed",
    "equal_marks": "#e63946",
    "right_angle": "#e63946",
}

def normalize_scene_json(scene_json: dict) -> dict:
    data = dict(scene_json)
    data["objects"] = [_normalize_object(dict(obj)) for obj in data.get("objects", []) if isinstance(obj, dict)]
    data["annotations"] = [_normalize_annotation(dict(ann)) for ann in data.get("annotations", []) if isinstance(ann, dict)]
    if isinstance(data.get("parameters"), list):
        data["parameters"] = [_normalize_parameter(dict(p)) for p in data["parameters"] if isinstance(p, dict)]
        data["parameters"] = [p for p in data["parameters"] if p is not None]
    apply_parameters_to_scene(data)
    _enrich_scene_semantic_hints(data)
    return data


def _enrich_scene_semantic_hints(data: dict[str, Any]) -> None:
    objects = data.get("objects")
    relations = data.get("relations")
    if not isinstance(objects, list) or not isinstance(relations, list):
        return

    problem_text = str(data.get("problem_text") or "")
    solid_type = _solid_type_hint(problem_text)
    pyramid = _pyramid_signature(problem_text)
    if pyramid:
        apex, base = pyramid
        _mark_point_role(objects, apex, "apex")
        for point in base:
            _mark_point_role(objects, point, "base_vertex")
        _mark_base_object(objects, base, solid_type or "pyramid")
        _append_interpretation_hint(data, "objects", {"role": "apex", "point": apex, "solid_type": solid_type or "pyramid"})
        _append_interpretation_hint(data, "objects", {"role": "base", "points": list(base), "solid_type": solid_type or "pyramid"})

    for relation in relations:
        if not isinstance(relation, dict) or str(relation.get("type") or "").lower() != "perpendicular":
            continue
        segment, plane = _perpendicular_segment_plane_hint(relation)
        if not segment or not plane:
            continue
        apex, foot = _height_endpoints(segment, plane)
        if not apex or not foot:
            continue
        metadata = relation.get("metadata") if isinstance(relation.get("metadata"), dict) else {}
        relation["metadata"] = metadata
        metadata.setdefault("role", "height")
        metadata.setdefault("apex", apex)
        metadata.setdefault("projection_foot", foot)
        metadata.setdefault("base", list(plane))
        if solid_type:
            metadata.setdefault("solid_type", solid_type)
        _mark_point_role(objects, apex, "apex")
        _mark_point_role(objects, foot, "projection_foot")
        for point in plane:
            _mark_point_role(objects, point, "base_vertex")
        _mark_base_object(objects, plane, solid_type)
        _append_interpretation_hint(data, "relations", {
            "role": "height",
            "line": "".join(segment),
            "apex": apex,
            "projection_foot": foot,
            "base": list(plane),
            "solid_type": solid_type,
            "source_relation": relation.get("id") or relation.get("type"),
        })


def _solid_type_hint(text: str) -> str | None:
    lowered = text.lower()
    if "tứ diện" in lowered or "tu dien" in lowered:
        return "tetrahedron"
    if "hình chóp" in lowered or "hinh chop" in lowered:
        return "pyramid"
    if "lăng trụ" in lowered or "lang tru" in lowered:
        return "prism"
    if "hình hộp" in lowered or "hinh hop" in lowered or "hộp chữ nhật" in lowered:
        return "box"
    return None


def _pyramid_signature(text: str) -> tuple[str, tuple[str, ...]] | None:
    match = re.search(r"(?:hình\s*chóp|hinh\s*chop)\s+([A-Z])\.([A-Z]{3,6})", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper(), tuple(match.group(2).upper())


def _perpendicular_segment_plane_hint(relation: dict[str, Any]) -> tuple[tuple[str, str] | None, tuple[str, ...] | None]:
    first = _parse_segment_hint(relation.get("object_1"))
    second = _parse_plane_hint(relation.get("object_2"))
    if first and second:
        return first, second
    first = _parse_segment_hint(relation.get("object_2"))
    second = _parse_plane_hint(relation.get("object_1"))
    return first, second


def _parse_segment_hint(value: Any) -> tuple[str, str] | None:
    compact = re.sub(r"\s+", "", str(value or ""))
    compact = re.sub(r"^(segment|line)\((.*)\)$", r"\2", compact, flags=re.IGNORECASE)
    if "-" in compact:
        parts = [part.upper() for part in compact.split("-") if part]
        return (parts[0], parts[1]) if len(parts) == 2 else None
    return (compact[0].upper(), compact[1].upper()) if len(compact) == 2 and compact.isalpha() else None


def _parse_plane_hint(value: Any) -> tuple[str, ...] | None:
    text = str(value or "").strip()
    if text.lower().startswith("plane(") and text.endswith(")"):
        text = text[6:-1]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    points = tuple(match.group(0).upper() for match in re.finditer(r"[A-Za-z](?:[0-9]+|')?", text))
    return points if len(points) >= 3 else None


def _height_endpoints(segment: tuple[str, str], plane: tuple[str, ...]) -> tuple[str | None, str | None]:
    first, second = segment
    plane_points = set(plane)
    if first not in plane_points and second in plane_points:
        return first, second
    if second not in plane_points and first in plane_points:
        return second, first
    return None, None


def _mark_point_role(objects: list[Any], point: str, role: str) -> None:
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") not in {"point_2d", "point_3d"} or obj.get("name") != point:
            continue
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        obj["metadata"] = metadata
        roles = metadata.get("semantic_roles") if isinstance(metadata.get("semantic_roles"), list) else []
        if role not in roles:
            roles.append(role)
        metadata["semantic_roles"] = roles
        return


def _mark_base_object(objects: list[Any], base: tuple[str, ...], solid_type: str | None) -> None:
    base_set = set(base)
    for obj in objects:
        if not isinstance(obj, dict) or obj.get("type") not in {"face", "plane"}:
            continue
        points = obj.get("points")
        if not isinstance(points, list) or not base_set.issubset({str(point).upper() for point in points}):
            continue
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        obj["metadata"] = metadata
        metadata.setdefault("role", "base")
        if solid_type:
            metadata.setdefault("solid_type", solid_type)


def _append_interpretation_hint(data: dict[str, Any], key: str, item: dict[str, Any]) -> None:
    interpretation = data.get("interpretation") if isinstance(data.get("interpretation"), dict) else {}
    data["interpretation"] = interpretation
    items = interpretation.get(key) if isinstance(interpretation.get(key), list) else []
    if item not in items:
        items.append(item)
    interpretation[key] = items




def _normalize_parameter(param: dict[str, Any]) -> dict[str, Any] | None:
    """Chuẩn hoá Parameter; trả None nếu thiếu trường bắt buộc."""
    name = param.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        default = float(param.get("default"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    try:
        lo = float(param.get("min", default - 5))
        hi = float(param.get("max", default + 5))
    except (TypeError, ValueError):
        lo, hi = default - 5, default + 5
    if hi <= lo:
        hi = lo + 1.0
    if not (lo <= default <= hi):
        default = max(lo, min(hi, default))
    try:
        step = float(param.get("step", 0.1))
    except (TypeError, ValueError):
        step = 0.1
    if step <= 0:
        step = 0.1
    return {
        "name": name.strip(),
        "label": param.get("label") if isinstance(param.get("label"), str) else None,
        "min": lo,
        "max": hi,
        "default": default,
        "step": step,
    }


def apply_parameters_to_scene(data: dict[str, Any]) -> None:
    """Eval các *_expr với giá trị default của parameter rồi gán vào x/y/z/radius.

    Mục đích: scene khi render lần đầu phải có toạ độ float hợp lệ. LLM có thể
    chỉ trả expression mà quên tính raw float, hoặc raw float không khớp với
    expression — pass này đảm bảo nhất quán ở giá trị default.
    Frontend sẽ tự eval lại khi user kéo slider.
    """
    parameters = data.get("parameters") or []
    if not isinstance(parameters, list) or not parameters:
        return
    defaults: dict[str, float] = {}
    for p in parameters:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        try:
            default = float(p.get("default"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if isinstance(name, str) and name.strip():
            defaults[name.strip()] = default
    if not defaults:
        return

    objects = data.get("objects")
    if not isinstance(objects, list):
        return
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        for axis in ("x", "y", "z", "radius"):
            expr = obj.get(f"{axis}_expr")
            if not isinstance(expr, str) or not expr.strip():
                continue
            exact = try_safe_eval_exact(expr, defaults)
            value = exact[1] if exact is not None else try_safe_eval(expr, defaults)
            if value is not None:
                obj[axis] = value


def _normalize_object(obj: dict[str, Any]) -> dict[str, Any]:
    obj_type = obj.get("type")
    if obj_type == "segment":
        obj.setdefault("hidden", False)
        obj["color"] = _normalize_color(obj.get("color"), _DEFAULT_COLORS["segment"])
        if obj.get("style") not in {"solid", "dashed", "dotted", None}:
            obj["style"] = "solid"
    elif obj_type in {"face", "sphere", "plane", "line_3d", "vector_3d"}:
        obj["color"] = _normalize_color(obj.get("color"), _DEFAULT_COLORS[obj_type])
    return obj


def _normalize_annotation(ann: dict[str, Any]) -> dict[str, Any]:
    ann_type = ann.get("type")
    metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
    ann["metadata"] = metadata
    if ann_type in _DEFAULT_COLORS:
        ann["color"] = _normalize_color(ann.get("color"), _DEFAULT_COLORS[ann_type])
    if ann_type == "angle":
        target = ann.get("target")
        if isinstance(target, str) and len(target) == 3 and not metadata.get("arms"):
            ann["target"] = target[1]
            metadata["arms"] = [target[0], target[2]]
        elif "arms" in metadata:
            metadata["arms"] = _normalize_arms(metadata["arms"])
    if ann_type in {"length", "equal_marks"} and isinstance(ann.get("target"), str):
        ann["target"] = _normalize_segment_target(ann["target"])
    return ann


def _normalize_arms(value: Any) -> Any:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,;\-\s]+", value) if part.strip()]
        if len(parts) >= 2:
            return parts[:2]
    return value


def _normalize_segment_target(target: str) -> str:
    compact = re.sub(r"\s+", "", target)
    if "-" in compact:
        parts = [part for part in compact.split("-") if part]
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
    if len(compact) == 2:
        return f"{compact[0]}-{compact[1]}"
    return target


def _normalize_color(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if _HEX_COLOR_RE.match(text):
            return text.lower()
        named = _COLOR_NAMES.get(text.lower())
        if named:
            return named
    return fallback


async def extract_scene(*_args, **_kwargs):
    raise RuntimeError(
        "extract_scene (MathScene v2) đã bị gỡ. Dùng extract_scene_v3 / POST /api/render/v3."
    )


def build_scene_with_cas_fix(*_args, **_kwargs):
    raise RuntimeError(
        "build_scene_with_cas_fix đã bị gỡ cùng CAS pipeline v2. Scene v3 dùng geometry kernel."
    )


def extract_scene_mock(*_args, **_kwargs):
    raise RuntimeError("extract_scene_mock đã bị gỡ. Production path không dùng mock MathScene.")


__all__ = [
    "RenderAttempt",
    "RenderFallbackSource",
    "apply_parameters_to_scene",
    "build_scene_with_cas_fix",
    "extract_scene",
    "extract_scene_mock",
    "normalize_scene_json",
    "_provider_order",
    "_profile_model_candidates",
]
