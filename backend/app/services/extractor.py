import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.scene import AdvancedRenderSettings, MathScene, RuntimeSettings, SceneView
from app.db.session import DatabaseClient
from app.services.ai_fallback import explicit_model_for_provider, provider_configured, text_model_candidates
from app.services.ai_prompt import get_system_prompts
from app.services.expression_eval import try_safe_eval, try_safe_eval_exact
from app.services.nvidia_client import NvidiaClient
from app.services.ollama_client import OllamaClient
from app.services.openai_compat_client import OpenAICompatClient
from app.services.openrouter_client import OpenRouterClient
from app.services.router9_bootstrap import select_router9_render_model_ids_from_ids
from app.services.router9_client import Router9Client
from app.services.provider_logging import redact_sensitive
from app.services.model_registry import load_model_registry, resolve_effective_settings, resolve_task_profile
from app.services.solid_presets import equilateral_triangle, rectangular_box, square_pyramid, triangular_prism, triangular_pyramid

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

_POINT_2D_RE = re.compile(r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_POINT_3D_RE = re.compile(r"([A-Z])\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)")
_FUNCTION_RE = re.compile(r"y\s*=\s*([^.,;\n]+)", re.IGNORECASE)
_CIRCLE_RADIUS_RE = re.compile(r"(?:tâm|tam)\s+([A-Z]).*?(?:bán kính|ban kinh|r)\s*[=:]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_RENDER_TOTAL_BUDGET_SECONDS = 300.0
_RENDER_MIN_ATTEMPT_SECONDS = 10.0
_RENDER_MAX_ATTEMPT_SECONDS = 285.0


@dataclass(frozen=True)
class RenderAttempt:
    provider: str
    model: str
    message: str

    def warning(self) -> str:
        return f"{self.provider}/{self.model}: {_short_error(self.message)}"


async def _build_render_settings(db: DatabaseClient | None, runtime_settings: RuntimeSettings | None) -> Settings:
    return await resolve_effective_settings(db, runtime_settings)

async def extract_scene(
    problem_text: str,
    grade: int | None = None,
    preferred_ai_provider: str | None = None,
    preferred_ai_model: str | None = None,
    advanced_settings: AdvancedRenderSettings | None = None,
    runtime_settings: RuntimeSettings | None = None,
    db: DatabaseClient | None = None,
) -> tuple[MathScene, list[str]]:
    settings = await _build_render_settings(db, runtime_settings)
    registry = await load_model_registry(db, settings) if db is not None else None
    render_profile = resolve_task_profile(registry, "render", preferred_ai_provider, preferred_ai_model) if registry else None
    reasoning_profile = resolve_task_profile(registry, "reasoning", preferred_ai_provider, preferred_ai_model) if registry else None
    render_provider = render_profile.provider_id if render_profile else preferred_ai_provider
    render_model = render_profile.model_id if render_profile else preferred_ai_model
    reasoning_provider = reasoning_profile.provider_id if reasoning_profile else preferred_ai_provider
    reasoning_model = reasoning_profile.model_id if reasoning_profile else preferred_ai_model
    render_settings = advanced_settings or AdvancedRenderSettings()
    warnings: list[str] = []
    attempts: list[RenderAttempt] = []
    use_two_stage = render_settings.reasoning_layer in ("auto", "force")
    started_at = time.monotonic()

    # --- TẢI SYSTEM PROMPTS ---
    scene_sys_prompt, reasoning_sys_prompt = await get_system_prompts(db)

    # --- TẦNG 1: Suy luận (nếu bật) ---
    reasoning_plan: dict | None = None
    if use_two_stage:
        reasoning_plan = await _run_reasoning_stage(
            settings, problem_text, grade,
            reasoning_provider, reasoning_model,
            warnings, system_prompt=reasoning_sys_prompt,
        )
        if reasoning_plan is not None:
            warnings.append("Đã hoàn thành tầng suy luận (reasoning layer).")

    # --- TẦNG 2: Trích xuất scene ---
    requested_provider = render_provider or settings.ai_provider
    for provider in _fast_provider_order(settings, render_provider):
        explicit_model = render_model if provider == requested_provider else None
        models = _profile_model_candidates(render_profile, provider, settings, explicit_model)
        for model in models:
            remaining = _render_budget_remaining(started_at)
            if remaining < _RENDER_MIN_ATTEMPT_SECONDS:
                warnings.extend(_render_attempt_warnings(attempts))
                warnings.append(_render_budget_warning(attempts, remaining))
                if settings.router9_only:
                    raise RuntimeError(_format_render_failure("9router-only đang bật và render đã gần hết thời gian.", attempts, True))
                return extract_scene_mock(problem_text, grade), warnings
            attempt_timeout = min(remaining, _RENDER_MAX_ATTEMPT_SECONDS)
            try:
                try:
                    scene_json = await asyncio.wait_for(
                        _extract_with_provider(
                            provider, settings, problem_text, grade,
                            render_settings.reasoning_layer,
                            preferred_ai_model=model,
                            reasoning_plan=reasoning_plan,
                            system_prompt=scene_sys_prompt,
                        ),
                        timeout=attempt_timeout,
                    )
                except TypeError as error:
                    if "unexpected keyword argument" not in str(error):
                        raise
                    scene_json = await asyncio.wait_for(
                        _extract_with_provider(
                            provider, settings, problem_text, grade,
                            render_settings.reasoning_layer,
                            preferred_ai_model=model,
                        ),
                        timeout=attempt_timeout,
                    )
                warnings.extend(_render_attempt_warnings(attempts))
                scene, cas_warnings = build_scene_with_cas_fix(scene_json)
                warnings.extend(cas_warnings)
                return scene, warnings
            except TimeoutError as error:
                attempts.append(RenderAttempt(provider, model or _provider_model(provider, settings), f"provider timeout after {attempt_timeout:.0f}s"))
                if settings.router9_only:
                    raise RuntimeError(_format_render_failure("9router-only đang bật nên không fallback sang provider khác.", attempts, True)) from error
            except (RuntimeError, ValidationError, ValueError, KeyError) as error:
                attempts.append(RenderAttempt(provider, model or _provider_model(provider, settings), str(error)))
                if settings.router9_only:
                    raise RuntimeError(_format_render_failure("9router-only đang bật nên không fallback sang provider khác.", attempts, True)) from error
            except Exception as error:
                message = str(error) or error.__class__.__name__
                attempts.append(RenderAttempt(provider, model or _provider_model(provider, settings), message))
                if settings.router9_only:
                    raise RuntimeError(_format_render_failure("9router-only đang bật nên không fallback sang provider khác.", attempts, True)) from error

    warnings.extend(_render_attempt_warnings(attempts))
    if attempts:
        warnings.append("Tất cả AI provider đều lỗi; đang dùng mock extractor.")
    else:
        warnings.append("Đang dùng mock extractor vì AI provider chưa sẵn sàng.")
    return extract_scene_mock(problem_text, grade), warnings


async def _run_reasoning_stage(
    settings: Settings,
    problem_text: str,
    grade: int | None,
    preferred_ai_provider: str | None,
    preferred_ai_model: str | None,
    warnings: list[str],
    system_prompt: str | None = None,
) -> dict | None:
    """Run the reasoning layer (Task 1) and return the reasoning plan.

    Returns None if reasoning fails (the pipeline will fall back to
    single-stage extraction).
    Giới hạn tối đa 1 lần thử và 25s tổng để không kéo dài pipeline.
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    _MAX_REASONING_ATTEMPTS = 1
    _REASONING_TOTAL_TIMEOUT = 25

    async def _try_reasoning() -> dict | None:
        attempts = 0
        requested_provider = preferred_ai_provider or settings.ai_provider
        for provider in _provider_order(settings, preferred_ai_provider):
            explicit_model = preferred_ai_model if provider == requested_provider else None
            for model in _provider_model_candidates(provider, settings, explicit_model):
                if attempts >= _MAX_REASONING_ATTEMPTS:
                    return None
                attempts += 1
                try:
                    plan = await _reason_with_provider(provider, settings, problem_text, grade, model, system_prompt=system_prompt)
                    if isinstance(plan, dict):
                        logger.info("Reasoning stage succeeded via %s/%s", provider, model)
                        return plan
                except Exception as error:
                    logger.warning("Reasoning stage failed via %s/%s: %s", provider, model, error)
                    warnings.append(f"Tầng suy luận lỗi ({provider}/{model}): {_short_error(str(error))}")
                    continue
        return None

    try:
        result = await asyncio.wait_for(_try_reasoning(), timeout=_REASONING_TOTAL_TIMEOUT)
        if result is None:
            warnings.append("Tầng suy luận không thành công; sẽ dùng single-stage extraction.")
        return result
    except asyncio.TimeoutError:
        warnings.append("Tầng suy luận quá thời gian (25s); sẽ dùng single-stage extraction.")
        return None


def normalize_scene_json(scene_json: dict) -> dict:
    data = dict(scene_json)
    data["objects"] = [_normalize_object(dict(obj)) for obj in data.get("objects", []) if isinstance(obj, dict)]
    data["annotations"] = [_normalize_annotation(dict(ann)) for ann in data.get("annotations", []) if isinstance(ann, dict)]
    if isinstance(data.get("parameters"), list):
        data["parameters"] = [_normalize_parameter(dict(p)) for p in data["parameters"] if isinstance(p, dict)]
        data["parameters"] = [p for p in data["parameters"] if p is not None]
    apply_parameters_to_scene(data)
    return data


def build_scene_with_cas_fix(
    scene_json: dict,
    *,
    repair_llm: Callable[[str], str] | None = None,
    repair_max_iterations: int = 2,
    repair_min_severity: str = "warning",
) -> tuple[MathScene, list[str]]:
    """Validate scene từ JSON LLM rồi chạy validator + CAS verify + auto-fix.

    Pipeline:
      1. Pre-validate raw dict: drop object/relation/annotation có type không hợp lệ.
      2. normalize_scene_json: chuẩn hoá colors, parameter defaults, eval *_expr.
      3. Pydantic validate (MathScene.model_validate): bắt lỗi schema cứng.
      4. scene_validator.validate_and_repair: ngữ nghĩa (reference integrity,
         naming uniqueness, dimension consistency, geometry sanity, parameters,
         annotation shape).
      5. cas_verifier.auto_fix_scene: kiểm tra số học các quan hệ (midpoint,
         on_line, on_plane, perpendicular, parallel, ...) và auto-fix khi
         deterministic.
      6. (Optional) cas_repair.repair_scene_iteratively: nếu ``repair_llm``
         được cung cấp và còn issues sau bước 5, gọi LLM tối đa
         ``repair_max_iterations`` lần để sửa các quan hệ phức tạp.

    Trả về (scene, warnings). Warnings là chuỗi human-readable gộp tất cả
    bất thường phát hiện ở mọi bước.
    """
    from app.services.cas_verifier import auto_fix_scene, infer_point_coordinates  # local import tránh circular
    from app.services.scene_validator import pre_validate_raw, validate_and_repair

    cleaned, pre_warnings = pre_validate_raw(scene_json)
    normalized = normalize_scene_json(cleaned)
    scene = MathScene.model_validate(normalized)

    report = validate_and_repair(scene)
    scene = report.scene

    scene, inference_issues = infer_point_coordinates(scene)
    fixed_scene, issues = auto_fix_scene(scene)

    warnings: list[str] = []
    for msg in pre_warnings:
        warnings.append(f"[Validator] Pre-check: {msg}")
    warnings.extend(report.all_warnings)
    for issue in [*inference_issues, *issues]:
        prefix = "Đã tự sửa" if issue.auto_fixed else "Cảnh báo CAS"
        warnings.append(f"[CAS] {prefix} ({issue.relation_type}): {issue.description}")

    if repair_llm is not None:
        from app.services.cas_repair import repair_scene_iteratively

        unresolved = [i for i in issues if not i.auto_fixed]
        if unresolved:
            outcome = repair_scene_iteratively(
                fixed_scene,
                unresolved,
                repair_llm,
                max_iterations=repair_max_iterations,
                min_severity=repair_min_severity,
            )
            fixed_scene = outcome.scene
            for attempt in outcome.attempts:
                if attempt.accepted:
                    warnings.append(
                        f"[CAS Repair] iteration {attempt.iteration}: "
                        f"{len(attempt.issues_before)} → {len(attempt.issues_after)} issues."
                    )
            warnings.extend(outcome.warnings)

    return fixed_scene, warnings


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


def extract_scene_mock(problem_text: str, grade: int | None = None) -> MathScene:
    text = problem_text.strip()
    lowered = text.lower()

    if "tam giác đều" in lowered or "tam giac deu" in lowered:
        return equilateral_triangle(text, grade)
    if "lăng trụ" in lowered or "lang tru" in lowered:
        return triangular_prism(text, grade)
    if "hình hộp" in lowered or "hinh hop" in lowered or "hộp chữ nhật" in lowered:
        return rectangular_box(text, grade)
    if "tứ diện" in lowered or "tu dien" in lowered or "s.abc" in lowered:
        return triangular_pyramid(text, grade)
    if "hình chóp" in lowered or "s.abcd" in lowered:
        return square_pyramid(text, grade)

    points_3d = _extract_points_3d(text)
    if points_3d:
        return _coordinate_3d_scene(text, grade, points_3d)

    function_match = _FUNCTION_RE.search(text)
    if "đồ thị" in lowered or "do thi" in lowered or function_match:
        expression = function_match.group(1).strip() if function_match else "x^2"
        return MathScene(
            problem_text=text,
            grade=grade,
            topic="function_graph",
            renderer="geogebra_2d",
            objects=[{"type": "function_graph", "name": "f", "expression": expression}],
            view=SceneView(dimension="2d"),
        )

    points = _extract_points_2d(text)
    if "đường tròn" in lowered or "duong tron" in lowered:
        return _circle_scene(text, grade, points)
    if "vector" in lowered or "vectơ" in lowered or "vec" in lowered:
        return _vector_scene(text, grade, points)
    if points:
        return _coordinate_2d_scene(text, grade, points)

    return MathScene(
        problem_text=text,
        grade=grade,
        topic="unknown",
        renderer="geogebra_2d",
        objects=[],
        view=SceneView(dimension="2d"),
    )


def _extract_points_2d(text: str) -> list[dict[str, Any]]:
    return [
        {"type": "point_2d", "name": name, "x": float(x), "y": float(y)}
        for name, x, y in _POINT_2D_RE.findall(text)
    ]


def _extract_points_3d(text: str) -> list[dict[str, Any]]:
    return [
        {"type": "point_3d", "name": name, "x": float(x), "y": float(y), "z": float(z)}
        for name, x, y, z in _POINT_3D_RE.findall(text)
    ]


def _coordinate_2d_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    names = [point["name"] for point in points]
    if len(names) >= 2:
        objects.append({"type": "line_2d", "name": f"{names[0]}{names[1]}", "through": names[:2]})
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_2d",
        renderer="geogebra_2d",
        objects=objects,
        view=SceneView(dimension="2d"),
    )


def _coordinate_3d_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    names = [point["name"] for point in points]
    for start, end in zip(names, names[1:]):
        objects.append({"type": "segment", "points": [start, end]})
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_3d",
        renderer="threejs_3d",
        objects=objects,
        view=SceneView(dimension="3d", show_axes=True, show_grid=True),
    )


def _vector_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    if len(points) < 2:
        points = [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 3, "y": 2},
        ]
    names = [point["name"] for point in points]
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="vector_2d",
        renderer="geogebra_2d",
        objects=[*points, {"type": "vector_2d", "name": f"u", "from_point": names[0], "to_point": names[1]}],
        view=SceneView(dimension="2d"),
    )


def _circle_scene(text: str, grade: int | None, points: list[dict[str, Any]]) -> MathScene:
    objects: list[dict[str, Any]] = [*points]
    radius_match = _CIRCLE_RADIUS_RE.search(text)
    if radius_match:
        center, radius = radius_match.groups()
        if not any(point["name"] == center for point in points):
            objects.append({"type": "point_2d", "name": center, "x": 0, "y": 0})
        objects.append({"type": "circle_2d", "name": "c", "center": center, "radius": float(radius)})
    elif len(points) >= 2:
        objects.append({"type": "circle_2d", "name": "c", "center": points[0]["name"], "through": points[1]["name"]})
    else:
        objects.extend([
            {"type": "point_2d", "name": "O", "x": 0, "y": 0},
            {"type": "point_2d", "name": "A", "x": 2, "y": 0},
            {"type": "circle_2d", "name": "c", "center": "O", "through": "A"},
        ])
    return MathScene(
        problem_text=text,
        grade=grade,
        topic="coordinate_2d",
        renderer="geogebra_2d",
        objects=objects,
        view=SceneView(dimension="2d"),
    )


def _fast_provider_order(settings: Settings, preferred_ai_provider: str | None = None) -> list[str]:
    return _provider_order(settings, preferred_ai_provider)


def _provider_order(settings: Settings, preferred_ai_provider: str | None = None) -> list[str]:
    provider = preferred_ai_provider or settings.ai_provider
    router9_providers = ["router9"] if provider_configured(settings.router9_api_key) else []
    nvidia_providers = ["nvidia"] if provider_configured(settings.nvidia_api_key) else []
    custom_providers = ["openai_compat"] if provider_configured(settings.openai_compat_api_key) and settings.openai_compat_text_model else []
    openrouter_providers = ["openrouter"] if provider_configured(settings.openrouter_api_key) else []
    local_providers = ["ollama_gpt_oss"]
    if settings.router9_only:
        if provider not in {"auto", "router9"}:
            raise RuntimeError("9router-only đang bật nên chỉ được dùng model 9router.")
        return router9_providers or ["router9"]
    if provider == "mock":
        return []
    if provider == "router9":
        return _dedupe([*router9_providers, *openrouter_providers, *nvidia_providers, *custom_providers, *local_providers])
    if provider == "openai_compat":
        return _dedupe([*custom_providers, *router9_providers, *nvidia_providers, *openrouter_providers, *local_providers])
    if provider == "nvidia":
        return _dedupe([*nvidia_providers, *router9_providers, *openrouter_providers, *custom_providers, *local_providers])
    if provider in {"openrouter", "opencode_nemotron", "openrouter_gpt_oss"}:
        requested = [provider] if provider_configured(settings.openrouter_api_key) else []
        return _dedupe([*requested, *openrouter_providers, *router9_providers, *nvidia_providers, *custom_providers, *local_providers])
    if provider == "ollama_gpt_oss":
        return _dedupe([*local_providers, *router9_providers, *openrouter_providers, *nvidia_providers, *custom_providers])
    return _dedupe([*router9_providers, *nvidia_providers, *openrouter_providers, *custom_providers, *local_providers])


def _provider_model(provider: str, settings: Settings, preferred_ai_model: str | None = None) -> str:
    if provider == "router9":
        return preferred_ai_model or settings.router9_text_model or "<none>"
    if provider == "openrouter":
        return preferred_ai_model or settings.openrouter_text_model
    if provider == "opencode_nemotron":
        return settings.opencode_nemotron_model
    if provider == "openrouter_gpt_oss":
        return "openai/gpt-oss-120b:free"
    if provider == "ollama_gpt_oss":
        return preferred_ai_model or settings.ollama_text_model
    if provider == "nvidia":
        return preferred_ai_model or settings.nvidia_text_model
    if provider == "openai_compat":
        return preferred_ai_model or settings.openai_compat_text_model or "<none>"
    return "<unknown>"


def _provider_model_candidates(provider: str, settings: Settings, preferred_ai_model: str | None = None) -> list[str | None]:
    if provider == "router9":
        return _router9_model_candidates(settings, preferred_ai_model)
    if provider in {"openrouter", "nvidia", "ollama_gpt_oss", "openai_compat"}:
        return text_model_candidates(provider, settings, preferred_ai_model)
    return [None]


def _profile_model_candidates(profile: Any, provider: str, settings: Settings, preferred_ai_model: str | None = None) -> list[str | None]:
    candidates = _provider_model_candidates(provider, settings, preferred_ai_model)
    if profile is None or provider != profile.provider_id:
        return candidates
    return _dedupe([*(model or "" for model in candidates), *profile.fallbacks])


def _render_attempt_warnings(attempts: list[RenderAttempt]) -> list[str]:
    return [f"AI fallback: {attempt.warning()}" for attempt in attempts]


def _render_budget_remaining(started_at: float) -> float:
    return max(0.0, _RENDER_TOTAL_BUDGET_SECONDS - (time.monotonic() - started_at))


def _render_budget_warning(attempts: list[RenderAttempt], remaining_seconds: float) -> str:
    tried = len(attempts)
    suffix = f" sau {tried} lần thử" if tried else ""
    return f"Dừng fallback AI{suffix} vì chỉ còn {remaining_seconds:.1f}s trước timeout; đang dùng mock extractor."


def _format_render_failure(message: str, attempts: list[RenderAttempt], router9_only: bool) -> str:
    details = " | ".join(attempt.warning() for attempt in attempts) or "chưa có provider/model nào được thử"
    suggestions = "Hãy kiểm tra API key/gateway, chọn model khác hoặc quét lại model 9router."
    if router9_only:
        suggestions += " Nếu muốn fallback sang provider khác, hãy tắt 9router-only."
    return f"{message} Đã thử: {details}. {suggestions}"


def _short_error(message: str) -> str:
    clean = re.sub(r"\s+", " ", redact_sensitive(message)).strip()
    return clean[:300] + ("..." if len(clean) > 300 else "")


def _dedupe(providers: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for provider in providers:
        if provider in seen:
            continue
        seen.add(provider)
        ordered.append(provider)
    return ordered


def _router9_model(settings: Settings, preferred_ai_model: str | None) -> str:
    model = explicit_model_for_provider("router9", preferred_ai_model) or settings.router9_text_model
    if not model:
        raise RuntimeError("Chưa chọn model 9router.")
    if settings.router9_allowed_models and model not in settings.router9_allowed_models:
        raise RuntimeError(f"Model 9router không nằm trong danh sách được phép: {model}")
    return model


def _router9_model_candidates(settings: Settings, preferred_ai_model: str | None) -> list[str]:
    explicit_model = explicit_model_for_provider("router9", preferred_ai_model)
    if explicit_model is not None:
        return [_router9_model(settings, explicit_model)]

    if settings.router9_allowed_models:
        if settings.router9_text_model and settings.router9_text_model in settings.router9_allowed_models:
            candidates = [settings.router9_text_model]
        else:
            selected = select_router9_render_model_ids_from_ids(settings.router9_allowed_models)
            candidates = [selected[0] if selected else settings.router9_allowed_models[0]]
    else:
        candidates = [settings.router9_text_model or settings.router9_text_fallback_models[0]]

    if not candidates:
        raise RuntimeError("Chưa chọn model 9router phù hợp cho render.")
    return candidates


async def _extract_with_provider(provider: str, settings: Settings, problem_text: str, grade: int | None, reasoning_layer: str, preferred_ai_model: str | None = None, reasoning_plan: dict | None = None, system_prompt: str | None = None) -> dict:
    if provider == "nvidia":
        return await NvidiaClient(settings, model=preferred_ai_model).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "router9":
        model = _router9_model(settings, preferred_ai_model)
        return await Router9Client(settings, model=model).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "openrouter":
        return await OpenRouterClient(settings, model=preferred_ai_model).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "openai_compat":
        return await OpenAICompatClient(settings, model=preferred_ai_model).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "opencode_nemotron":
        return await OpenRouterClient(settings, model=settings.opencode_nemotron_model, reasoning_enabled=False).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "ollama_gpt_oss":
        return await OllamaClient(settings, model=preferred_ai_model).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    if provider == "openrouter_gpt_oss":
        return await OpenRouterClient(settings, model="openai/gpt-oss-120b:free", reasoning_enabled=True).extract_scene_json(problem_text, grade, reasoning_layer, reasoning_plan=reasoning_plan, system_prompt=system_prompt)
    raise RuntimeError(f"Provider không hỗ trợ: {provider}")


async def _reason_with_provider(provider: str, settings: Settings, problem_text: str, grade: int | None, preferred_ai_model: str | None = None, system_prompt: str | None = None) -> dict:
    """Run reasoning task (Task 1) with the given provider."""
    if provider == "nvidia":
        return await NvidiaClient(settings, model=preferred_ai_model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "router9":
        model = _router9_model(settings, preferred_ai_model)
        return await Router9Client(settings, model=model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "openrouter":
        return await OpenRouterClient(settings, model=preferred_ai_model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "openai_compat":
        return await OpenAICompatClient(settings, model=preferred_ai_model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "opencode_nemotron":
        return await OpenRouterClient(settings, model=settings.opencode_nemotron_model, reasoning_enabled=False).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "ollama_gpt_oss":
        return await OllamaClient(settings, model=preferred_ai_model).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    if provider == "openrouter_gpt_oss":
        return await OpenRouterClient(settings, model="openai/gpt-oss-120b:free", reasoning_enabled=True).reason_about_problem(problem_text, grade, system_prompt=system_prompt)
    raise RuntimeError(f"Provider không hỗ trợ reasoning: {provider}")
