import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.api.deps import enforce_rate_limit, require_active_user, require_trusted_origin
from app.db.models import UserRecord
from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient, create_database_client, get_database
from app.repositories.admin import AdminRepository
from app.repositories.history import RenderHistoryRepository
from app.schemas.auth import SystemFeatureFlags
from app.schemas.scene import MathScene, RenderJobCreateResponse, RenderJobStatusResponse, RenderPayload, RenderRequest, RenderResponse, SceneRenderRequest
from app.services.api_errors import api_error
from app.services.system_settings import load_feature_flags
from app.services.extractor import extract_scene
from app.services.geometry_engine import normalize_scene
from app.services.renderer_router import build_render_payload

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/render", response_model=RenderJobCreateResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_trusted_origin)])
async def render_problem(
    request: RenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> RenderJobCreateResponse:
    await enforce_rate_limit(db, http_request, user, "render", 20 if user else 8, 60)
    await enforce_render_access(db, user)
    repo = RenderHistoryRepository(db)
    job = await repo.create_pending(
        user.id,
        request.problem_text,
        request.preferred_ai_provider,
        request.preferred_ai_model,
        render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
        advanced_settings_json=request.advanced_settings.model_dump_json(),
        runtime_settings_json=json.dumps(sanitize_runtime_settings(request.runtime_settings), ensure_ascii=False),
        source_type="problem",
        renderer=request.preferred_renderer,
    )
    asyncio.create_task(process_render_job(job.id, request, settings))
    return RenderJobCreateResponse(job_id=job.id, status="queued")


@router.get("/render/jobs/{job_id}", response_model=RenderJobStatusResponse)
async def get_render_job(
    job_id: str,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderJobStatusResponse:
    job = await RenderHistoryRepository(db).find_for_user(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy render job.")
    if job.status == "completed":
        return RenderJobStatusResponse(
            job_id=job.id,
            status="completed",
            response=RenderResponse(
                scene=MathScene.model_validate_json(job.scene_json),
                payload=RenderPayload.model_validate_json(job.payload_json),
                warnings=json.loads(job.warnings_json),
            ),
        )
    if job.status == "failed":
        return RenderJobStatusResponse(job_id=job.id, status="failed", error=parse_json_object(job.error_json) or {})
    return RenderJobStatusResponse(job_id=job.id, status=job.status)  # type: ignore[arg-type]


async def process_render_job(job_id: str, request: RenderRequest, settings: Settings) -> None:
    db = create_database_client(settings)
    repo = RenderHistoryRepository(db)
    await repo.mark_running(job_id)
    try:
        response = await build_problem_render_response(request, db)
        await repo.mark_completed(job_id, response, response.scene.renderer)
    except (RuntimeError, ValidationError, ValueError, KeyError) as error:
        await repo.mark_failed(job_id, render_error_payload(error))
    except Exception as error:
        await repo.mark_failed(job_id, render_error_payload(error))


async def build_problem_render_response(request: RenderRequest, db: DatabaseClient) -> RenderResponse:
    scene, warnings = await extract_scene(
        request.problem_text,
        request.grade,
        request.preferred_ai_provider,
        request.preferred_ai_model,
        request.advanced_settings,
        request.runtime_settings,
        db=db,
    )
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


@router.post("/render/scene", response_model=RenderResponse, dependencies=[Depends(require_trusted_origin)])
async def render_scene(
    request: SceneRenderRequest,
    http_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderResponse:
    await enforce_rate_limit(db, http_request, user, "render_scene", 40 if user else 12, 60)
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
    repo = AdminRepository(db)
    plan = await repo.find_plan(user.plan) or await repo.find_plan("free")
    if plan is None or plan.daily_render_limit is None:
        return
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    used = await AdminRepository(db).count_user_render_jobs_since(user.id, since)
    if used >= plan.daily_render_limit:
        raise api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Bạn đã dùng hết hạn mức render hôm nay của gói hiện tại.",
            "PLAN_QUOTA_EXCEEDED",
            suggestions=["Chờ sang ngày mới để hạn mức được đặt lại.", "Nâng cấp gói hoặc liên hệ admin nếu cần thêm lượt render."],
        )


def enforce_enabled(flags: SystemFeatureFlags) -> None:
    if flags.maintenance_mode:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, flags.maintenance_message, "MAINTENANCE_MODE")
    if not flags.render_enabled:
        raise api_error(status.HTTP_403_FORBIDDEN, "Tính năng render đang tạm tắt.", "RENDER_DISABLED")


def render_error_payload(error: Exception) -> dict:
    message = str(error) or error.__class__.__name__
    return {
        "code": "RENDER_FAILED",
        "message": "Không thể dựng hình từ đề bài này.",
        "debug_message": message,
        "suggestions": ["Kiểm tra đề bài và model dựng hình đã chọn.", "Thử provider/model khác hoặc viết đề bài rõ hơn."],
    }


def parse_json_object(value: str | None) -> dict | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None


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
