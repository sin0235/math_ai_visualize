import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.api.deps import get_optional_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.history import RenderHistoryRepository
from app.schemas.scene import RenderRequest, RenderResponse, SceneRenderRequest
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
    try:
        scene, warnings = await extract_scene(
            request.problem_text,
            request.grade,
            request.preferred_ai_provider,
            request.preferred_ai_model,
            request.advanced_settings,
            sanitize_public_runtime_settings(request.runtime_settings),
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
