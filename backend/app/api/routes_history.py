import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.history import RenderHistoryRepository
from app.schemas.auth import RenderHistoryDetail, RenderHistoryItem
from app.schemas.scene import MathScene, RenderPayload, RenderResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[RenderHistoryItem])
async def list_history(user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> list[RenderHistoryItem]:
    jobs = await RenderHistoryRepository(db).list_for_user(user.id)
    return [
        RenderHistoryItem(
            id=job.id,
            problem_text=job.problem_text,
            provider=job.provider,
            model=job.model,
            created_at=job.created_at,
            source_type=job.source_type,
            renderer=job.renderer,
            degraded=job.degraded,
            fallback_source=job.fallback_source,  # type: ignore[arg-type]
            ai_source=job.ai_source,  # type: ignore[arg-type]
            schema_version=job.schema_version,
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=RenderHistoryDetail)
async def get_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> RenderHistoryDetail:
    job = await RenderHistoryRepository(db).find_for_user(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử dựng hình.")
    try:
        response = RenderResponse.model_validate_json(job.response_json) if job.response_json else None
        scene = response.scene if response else MathScene.model_validate_json(job.scene_json)
        payload = response.payload if response else RenderPayload.model_validate_json(job.payload_json)
        warnings = response.warnings if response else json.loads(job.warnings_json)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Lịch sử này dùng định dạng cũ hoặc không còn tương thích với render v2.") from error
    return RenderHistoryDetail(
        id=job.id,
        problem_text=job.problem_text,
        provider=job.provider,
        model=job.model,
        created_at=job.created_at,
        source_type=job.source_type,
        renderer=job.renderer,
        degraded=job.degraded,
        fallback_source=job.fallback_source,  # type: ignore[arg-type]
        ai_source=job.ai_source,  # type: ignore[arg-type]
        schema_version=job.schema_version,
        scene=scene,
        payload=payload,
        warnings=warnings,
        response=response,
        render_request=parse_json_object(job.render_request_json),
        advanced_settings=parse_json_object(job.advanced_settings_json),
        runtime_settings=parse_json_object(job.runtime_settings_json),
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def delete_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> None:
    await RenderHistoryRepository(db).delete_for_user(user.id, job_id)


def parse_json_object(value: str | None) -> dict | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None
