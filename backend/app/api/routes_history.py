import json

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_trusted_origin
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.activity import try_log_user_activity
from app.repositories.history import RenderHistoryRepository
from app.repositories.scene_workspaces import SceneWorkspaceRepository
from app.schemas.auth import (
    RenderHistoryDetail,
    RenderHistoryDetailV3,
    RenderHistoryItem,
    RenderHistoryPatchRequest,
    RestoreHistoryV3Request,
    SceneRevisionResponse,
)
from app.schemas.scene_v3 import CommittedSceneRefV3, SceneWorkspaceResponseV3

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[RenderHistoryItem])
async def list_history(
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    limit: int = Query(default=30, ge=1, le=100),
    q: str | None = Query(default=None, max_length=256),
    renderer: str | None = Query(default=None, max_length=64),
    topic: str | None = Query(default=None, max_length=64),
    favorite: bool | None = Query(default=None),
    archived: bool | None = Query(default=False),
) -> list[RenderHistoryItem]:
    repo = RenderHistoryRepository(db)
    jobs = await repo.list_for_user(user.id, limit, q=q, renderer=renderer, topic=topic, favorite=favorite, archived=archived)
    return [await render_history_item(repo, job) for job in jobs]


@router.get("/{job_id}", response_model=RenderHistoryDetail)
async def get_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> RenderHistoryDetail:
    repo = RenderHistoryRepository(db)
    job = await repo.find_for_user(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử dựng hình.")
    item = await render_history_item(repo, job)
    if job.schema_version != "3.0":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Lịch sử Scene v2 đã bị gỡ. Hãy dựng lại hình bằng pipeline Scene v3.",
        )
    snapshot = await repo.find_v3_snapshot_for_user(user.id, job_id)
    if snapshot is None or snapshot.response_json is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Lịch sử v3 không có snapshot hợp lệ.")
    try:
        workspace = SceneWorkspaceResponseV3.model_validate_json(snapshot.response_json)
        command_log = json.loads(snapshot.command_log_json or "[]")
        if not isinstance(command_log, list):
            command_log = []
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Snapshot lịch sử v3 không hợp lệ.") from error
    return RenderHistoryDetailV3(
        **item.model_dump(),
        workspace=workspace,
        snapshot_revision=snapshot.snapshot_revision or workspace.scene.revision,
        command_log=command_log,
        render_request=parse_json_object(job.render_request_json),
        runtime_settings=parse_json_object(job.runtime_settings_json),
    )


@router.patch("/{job_id}", response_model=RenderHistoryItem, dependencies=[Depends(require_trusted_origin)])
async def patch_history(
    job_id: str,
    request: RenderHistoryPatchRequest,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> RenderHistoryItem:
    repo = RenderHistoryRepository(db)
    patch = request.model_dump(exclude_unset=True)
    job = await repo.patch_item(user.id, job_id, patch)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử dựng hình.")
    await try_log_user_activity(
        db,
        user.id,
        "history_item.updated",
        target_type="render_job",
        target_id=job_id,
        metadata={"changed_fields": sorted(patch.keys())},
    )
    return await render_history_item(repo, job)


@router.get("/{job_id}/revisions", response_model=list[SceneRevisionResponse])
async def list_history_revisions(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> list[SceneRevisionResponse]:
    revisions = await RenderHistoryRepository(db).list_revisions_for_user(user.id, job_id)
    return [
        SceneRevisionResponse(
            id=item.id,
            history_item_id=item.history_item_id,
            render_job_id=item.render_job_id,
            revision_no=item.revision_no,
            change_source=item.change_source,
            change_summary=item.change_summary,
            created_at=item.created_at,
            schema_version=item.schema_version,
            scene_id=item.scene_id,
            snapshot_revision=item.snapshot_revision,
        )
        for item in revisions
    ]


@router.post(
    "/{job_id}/restore",
    response_model=SceneWorkspaceResponseV3,
    dependencies=[Depends(require_trusted_origin)],
)
async def restore_history_v3(
    job_id: str,
    request: RestoreHistoryV3Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> SceneWorkspaceResponseV3:
    repo = RenderHistoryRepository(db)
    snapshot = await repo.find_v3_snapshot_for_user(user.id, job_id, request.snapshot_revision)
    if snapshot is None or snapshot.response_json is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy snapshot lịch sử v3.")
    try:
        workspace = SceneWorkspaceResponseV3.model_validate_json(snapshot.response_json)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Snapshot lịch sử v3 không hợp lệ.") from error
    await SceneWorkspaceRepository(db).restore_snapshot(user.id, snapshot.history_item_id, workspace)
    from app.api.routes_render import workspace_response_v3
    from app.services.committed_scene_v3 import load_committed_scene_v3

    committed = await load_committed_scene_v3(
        db,
        user.id,
        CommittedSceneRefV3(scene_id=workspace.scene.scene_id, revision=workspace.scene.revision),
        require_trusted=False,
    )
    response = workspace_response_v3(
        committed.result,
        confirmed_revision=committed.workspace.confirmed_revision,
        trusted_for_downstream=committed.trusted_for_downstream,
    )
    await try_log_user_activity(
        db,
        user.id,
        "history_item.restored",
        target_type="render_job",
        target_id=job_id,
        metadata={"scene_id": workspace.scene.scene_id, "revision": workspace.scene.revision},
    )
    return response


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def delete_history(job_id: str, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> None:
    await RenderHistoryRepository(db).delete_for_user(user.id, job_id)
    await try_log_user_activity(db, user.id, "history_item.deleted", target_type="render_job", target_id=job_id)


async def render_history_item(repo: RenderHistoryRepository, job) -> RenderHistoryItem:
    return RenderHistoryItem(
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
        title=job.title,
        problem_preview=job.problem_preview or job.problem_text[:240],
        topic=job.topic,
        grade=job.grade,
        tier=job.tier,
        is_favorite=job.is_favorite,
        archived_at=job.archived_at,
        last_opened_at=job.last_opened_at,
        updated_at=job.history_updated_at,
        tags=await repo.tags_for_item(job.history_item_id),
    )


def parse_json_object(value: str | None) -> dict | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None
