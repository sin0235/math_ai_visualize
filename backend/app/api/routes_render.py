from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas.scene import RenderRequest, RenderResponse, SceneRenderRequest
from app.services.extractor import extract_scene
from app.services.geometry_engine import normalize_scene
from app.services.renderer_router import build_render_payload

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/render", response_model=RenderResponse)
async def render_problem(request: RenderRequest) -> RenderResponse:
    try:
        scene, warnings = await extract_scene(
            request.problem_text,
            request.grade,
            request.preferred_ai_provider,
            request.preferred_ai_model,
            request.advanced_settings,
            request.runtime_settings,
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
    return RenderResponse(scene=scene, payload=payload, warnings=warnings)


@router.post("/render/scene", response_model=RenderResponse)
async def render_scene(request: SceneRenderRequest) -> RenderResponse:
    scene = normalize_scene(request.scene, request.advanced_settings)
    payload = build_render_payload(scene, request.advanced_settings)
    warnings = []
    computed = (payload.three_scene or {}).get("computed") if payload.three_scene else None
    if isinstance(computed, dict):
        warnings = [warning for warning in computed.get("warnings", []) if isinstance(warning, str)]
    return RenderResponse(scene=scene, payload=payload, warnings=warnings)
