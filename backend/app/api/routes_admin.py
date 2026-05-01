import json

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_admin_user, require_trusted_origin
from app.api.routes_history import parse_json_object
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.auth import (
    AdminRenderHistoryDetail,
    AdminRenderHistoryItem,
    AdminSummaryResponse,
    AdminUserUpdateRequest,
    AuditLogResponse,
    SystemSettingRequest,
    SystemSettingResponse,
    UserResponse,
)
from app.schemas.scene import MathScene, RenderPayload

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/summary", response_model=AdminSummaryResponse)
async def admin_summary(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> AdminSummaryResponse:
    return AdminSummaryResponse(**await AdminRepository(db).summary())


@router.get("/users", response_model=list[UserResponse])
async def admin_users(
    q: str | None = Query(default=None, max_length=256),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[UserResponse]:
    users = await AdminRepository(db).list_users(q)
    return [user_response(user) for user in users]


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_update_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> UserResponse:
    repo = AdminRepository(db)
    updated = await repo.update_user(user_id, role=request.role, status=request.status, display_name=request.display_name, plan=request.plan)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
    await repo.audit(admin.id, "admin.user.update", "user", user_id, request.model_dump(exclude_none=True))
    return user_response(updated)


@router.get("/render-jobs", response_model=list[AdminRenderHistoryItem])
async def admin_render_jobs(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[AdminRenderHistoryItem]:
    jobs = await AdminRepository(db).list_render_jobs()
    return [
        AdminRenderHistoryItem(
            id=job.id,
            user_id=job.user_id,
            problem_text=job.problem_text,
            provider=job.provider,
            model=job.model,
            created_at=job.created_at,
            source_type=job.source_type,
            renderer=job.renderer,
        )
        for job in jobs
    ]


@router.get("/render-jobs/{job_id}", response_model=AdminRenderHistoryDetail)
async def admin_render_job(job_id: str, _: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> AdminRenderHistoryDetail:
    job = await AdminRepository(db).find_render_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử dựng hình.")
    return AdminRenderHistoryDetail(
        id=job.id,
        user_id=job.user_id,
        problem_text=job.problem_text,
        provider=job.provider,
        model=job.model,
        created_at=job.created_at,
        source_type=job.source_type,
        renderer=job.renderer,
        scene=MathScene.model_validate_json(job.scene_json),
        payload=RenderPayload.model_validate_json(job.payload_json),
        warnings=json.loads(job.warnings_json),
        render_request=parse_json_object(job.render_request_json),
        advanced_settings=parse_json_object(job.advanced_settings_json),
        runtime_settings=parse_json_object(job.runtime_settings_json),
    )


@router.delete("/render-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_delete_render_job(job_id: str, admin: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> None:
    repo = AdminRepository(db)
    await repo.delete_render_job(job_id)
    await repo.audit(admin.id, "admin.render_job.delete", "render_job", job_id)


@router.get("/system-settings", response_model=list[SystemSettingResponse])
async def admin_system_settings(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[SystemSettingResponse]:
    settings = await AdminRepository(db).list_system_settings()
    return [SystemSettingResponse(key=item.key, value=parse_setting_value(item.value_json), updated_by=item.updated_by, updated_at=item.updated_at) for item in settings]


@router.put("/system-settings", response_model=SystemSettingResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_save_system_setting(
    request: SystemSettingRequest,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> SystemSettingResponse:
    repo = AdminRepository(db)
    setting = await repo.upsert_system_setting(request.key, request.value, admin.id)
    await repo.audit(admin.id, "admin.system_settings.update", "system_setting", request.key, {"key": request.key})
    return SystemSettingResponse(key=setting.key, value=parse_setting_value(setting.value_json), updated_by=setting.updated_by, updated_at=setting.updated_at)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def admin_audit_logs(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[AuditLogResponse]:
    logs = await AdminRepository(db).list_audit_logs()
    return [
        AuditLogResponse(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            metadata=parse_setting_value(log.metadata_json),
            created_at=log.created_at,
        )
        for log in logs
    ]


def parse_setting_value(value: str) -> dict:
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def user_response(user: UserRecord) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        role=user.role,
        status=user.status,
        display_name=user.display_name,
        last_login_at=user.last_login_at,
        plan=user.plan,
    )
