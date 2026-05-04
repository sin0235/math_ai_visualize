import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.deps import get_optional_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.history import RenderHistoryRepository
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import RenderRequest, RenderResponse, SceneRenderRequest
from app.services.system_settings import load_feature_flags, load_plan_settings
from app.services.extractor import extract_scene
from app.services.geometry_engine import normalize_scene
from app.services.renderer_router import build_render_payload

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/render", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_problem(
    request: RenderRequest,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    await enforce_render_access(db, user)
    try:
        scene, warnings = await extract_scene(
            request.problem_text,
            request.grade,
            request.preferred_ai_provider,
            request.preferred_ai_model,
            request.advanced_settings,
            request.runtime_settings,
            db=db,
        )
    except (RuntimeError, ValidationError, ValueError, KeyError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if request.preferred_renderer is not None:
        scene.renderer = request.preferred_renderer
    scene_data = scene.model_dump()
    if request.advanced_settings.show_coordinates is not None:
        scene_data["view"]["show_coordinates"] = request.advanced_settings.show_coordinates
    if request.advanced_settings.show_axes is not None:
        scene_data["view"]["show_axes"] = request.advanced_settings.show_axes
    if request.advanced_settings.show_grid is not None:
        scene_data["view"]["show_grid"] = request.advanced_settings.show_grid
    scene = scene.model_validate(scene_data)
    scene = normalize_scene(scene, request.advanced_settings)
    payload = build_render_payload(scene, request.advanced_settings)
    if scene.topic == "unknown":
        warnings.append("Chưa nhận diện được dạng toán, hãy thử đề cụ thể hơn.")
    response = RenderResponse(scene=scene, payload=payload, warnings=warnings)
    if user is not None:
        await RenderHistoryRepository(db).create(
            user.id,
            request.problem_text,
            request.preferred_ai_provider,
            request.preferred_ai_model,
            response,
            render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
            advanced_settings_json=request.advanced_settings.model_dump_json(),
            runtime_settings_json=json.dumps(sanitize_runtime_settings(request.runtime_settings), ensure_ascii=False),
            source_type="problem",
            renderer=scene.renderer,
        )
    return response


@router.post("/render/scene", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_scene(
    request: SceneRenderRequest,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    await enforce_render_access(db, user)
    scene = normalize_scene(request.scene, request.advanced_settings)
    payload = build_render_payload(scene, request.advanced_settings)
    warnings = []
    computed = (payload.three_scene or {}).get("computed") if payload.three_scene else None
    if isinstance(computed, dict):
        warnings = [warning for warning in computed.get("warnings", []) if isinstance(warning, str)]
    response = RenderResponse(scene=scene, payload=payload, warnings=warnings)
    if user is not None:
        await RenderHistoryRepository(db).create(
            user.id,
            scene.problem_text,
            None,
            None,
            response,
            render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
            advanced_settings_json=request.advanced_settings.model_dump_json(),
            runtime_settings_json=None,
            source_type="scene_edit",
            renderer=scene.renderer,
        )
    return response


async def enforce_render_access(db: DatabaseClient, user: UserRecord | None) -> None:
    flags = await load_feature_flags(db)
    enforce_enabled(flags)
    if user is None:
        return
    plan_settings = await load_plan_settings(db)
    quota = plan_settings.plans.get(user.plan) or plan_settings.plans.get("free")
    if quota is None or quota.daily_render_limit is None:
        return
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    used = await AdminRepository(db).count_user_render_jobs_since(user.id, since)
    if used >= quota.daily_render_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Bạn đã dùng hết hạn mức render hôm nay.")


def enforce_enabled(flags: SystemFeatureFlags) -> None:
    if flags.maintenance_mode:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=flags.maintenance_message)
    if not flags.render_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tính năng render đang tạm tắt.")


def sanitize_request_dump(request: RenderRequest | SceneRenderRequest) -> dict:
    data = request.model_dump(mode="json")
    runtime_settings = data.get("runtime_settings")
    if isinstance(runtime_settings, dict):
        data["runtime_settings"] = sanitize_runtime_settings(request.runtime_settings if isinstance(request, RenderRequest) else None)
    return data


def sanitize_runtime_settings(runtime_settings: object) -> dict | None:
    if runtime_settings is None or not hasattr(runtime_settings, "model_dump"):
        return None
    sanitized = sanitize_public_runtime_settings(runtime_settings)
    return sanitized.model_dump(mode="json", exclude_none=True) if sanitized is not None else None


def sanitize_public_runtime_settings(runtime_settings: object):
    if runtime_settings is None or not hasattr(runtime_settings, "model_dump"):
        return None
    data = runtime_settings.model_dump(mode="json")
    return type(runtime_settings).model_validate(
        {
            "default_provider": data.get("default_provider"),
            "openrouter": {"model": (data.get("openrouter") or {}).get("model")},
            "nvidia": {"model": (data.get("nvidia") or {}).get("model")},
            "ollama": {"model": (data.get("ollama") or {}).get("model")},
            "router9": {"model": (data.get("router9") or {}).get("model")},
        }
    )
