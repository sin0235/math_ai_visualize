import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.history import RenderHistoryRepository
from app.schemas.auth import RenderHistoryDetail, RenderHistoryItem
from app.schemas.scene import MathScene, RenderPayload

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[RenderHistoryItem])
async def list_history(user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> list[RenderHistoryItem]:
    jobs = await RenderHistoryRepository(db).list_for_user(user.id)
    return [
        RenderHistoryItem(id=job.id, problem_text=job.problem_text, provider=job.provider, model=job.model, created_at=job.created_at)
        for job in jobs
    ]


@router.get("/{job_id}", response_model=RenderHistoryDetail)
async def get_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> RenderHistoryDetail:
    job = await RenderHistoryRepository(db).find_for_user(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử dựng hình.")
    return RenderHistoryDetail(
        id=job.id,
        problem_text=job.problem_text,
        provider=job.provider,
        model=job.model,
        created_at=job.created_at,
        scene=MathScene.model_validate_json(job.scene_json),
        payload=RenderPayload.model_validate_json(job.payload_json),
        warnings=json.loads(job.warnings_json),
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> None:
    await RenderHistoryRepository(db).delete_for_user(user.id, job_id)
