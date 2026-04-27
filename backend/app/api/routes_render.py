from fastapi import APIRouter

from app.schemas.scene import RenderRequest, RenderResponse
from app.services.extractor import extract_scene
from app.services.geometry_engine import normalize_scene
from app.services.renderer_router import build_render_payload

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/render", response_model=RenderResponse)
async def render_problem(request: RenderRequest) -> RenderResponse:
    scene, warnings = await extract_scene(request.problem_text, request.grade, request.preferred_ai_provider)
    if request.preferred_renderer is not None:
        scene.renderer = request.preferred_renderer
    scene = normalize_scene(scene)
    payload = build_render_payload(scene)
    if scene.topic == "unknown":
        warnings.append("Chưa nhận diện được dạng toán, hãy thử đề cụ thể hơn.")
    return RenderResponse(scene=scene, payload=payload, warnings=warnings)
