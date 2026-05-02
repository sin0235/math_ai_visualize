import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.api.deps import require_admin_user, require_trusted_origin
from app.api.routes_history import parse_json_object
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.schemas.auth import (
    AdminRenderHistoryDetail,
    AdminRenderHistoryItem,
    AdminSessionResponse,
    AdminSummaryResponse,
    AdminUserUpdateRequest,
    AuditLogResponse,
    SystemAiProfiles,
    SystemAiPrompts,
    SystemAiSettings,
    SystemFeatureFlags,
    SystemPlanSettings,
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
    role: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, max_length=32),
    plan: str | None = Query(default=None, max_length=64),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[UserResponse]:
    users = await AdminRepository(db).list_users(q, role, status, plan)
    return [user_response(user) for user in users]


@router.get("/users/{user_id}/sessions", response_model=list[AdminSessionResponse])
async def admin_user_sessions(user_id: str, _: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[AdminSessionResponse]:
    sessions = await AdminRepository(db).list_user_sessions(user_id)
    return [AdminSessionResponse(id=item.id, created_at=item.created_at, expires_at=item.expires_at, last_seen_at=item.last_seen_at, ip_address=item.ip_address, user_agent=item.user_agent) for item in sessions]


@router.delete("/users/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_revoke_user_session(user_id: str, session_id: str, admin: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> None:
    repo = AdminRepository(db)
    revoked = await repo.revoke_user_session(user_id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên đăng nhập.")
    await repo.audit(admin.id, "admin.session.revoke", "session", session_id, {"user_id": user_id})


@router.post("/users/{user_id}/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_revoke_user_sessions(user_id: str, admin: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> None:
    repo = AdminRepository(db)
    count = await repo.revoke_user_sessions(user_id)
    await repo.audit(admin.id, "admin.sessions.revoke_all", "user", user_id, {"count": count})


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
async def admin_render_jobs(
    provider: str | None = Query(default=None, max_length=64),
    model: str | None = Query(default=None, max_length=256),
    renderer: str | None = Query(default=None, max_length=64),
    source_type: str | None = Query(default=None, max_length=64),
    user_id: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=256),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[AdminRenderHistoryItem]:
    jobs = await AdminRepository(db).list_render_jobs(provider, model, renderer, source_type, user_id, q)
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
    value = validate_system_setting(request.key, request.value)
    setting = await repo.upsert_system_setting(request.key, value, admin.id)
    await repo.audit(admin.id, "admin.system_settings.update", "system_setting", request.key, {"key": request.key})
    return SystemSettingResponse(key=setting.key, value=parse_setting_value(setting.value_json), updated_by=setting.updated_by, updated_at=setting.updated_at)


@router.post("/providers/{provider}/check")
async def admin_check_provider(
    provider: str,
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> dict:
    from app.services.extractor import _extract_with_provider
    from app.core.config import get_settings

    settings = get_settings()
    # Use a very simple problem for checking connection
    test_problem = "Vẽ điểm A(0,0)."
    try:
        # Note: this uses the system configured API keys and settings
        await _extract_with_provider(provider, settings, test_problem, grade=None, reasoning_layer="off")
        return {"status": "ok", "message": f"Kết nối tới {provider} thành công."}
    except Exception as error:
        return {"status": "error", "message": str(error)}


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def admin_audit_logs(
    action: str | None = Query(default=None, max_length=128),
    actor_user_id: str | None = Query(default=None, max_length=128),
    target_type: str | None = Query(default=None, max_length=128),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[AuditLogResponse]:
    logs = await AdminRepository(db).list_audit_logs(action, actor_user_id, target_type)
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


def validate_system_setting(key: str, value: dict) -> dict:
    schemas = {
        "ai_settings": SystemAiSettings,
        "plan_settings": SystemPlanSettings,
        "feature_flags": SystemFeatureFlags,
        "ai_profiles": SystemAiProfiles,
        "ai_prompts": SystemAiPrompts,
    }
    schema = schemas.get(key)
    if schema is None:
        return value
    try:
        return schema.model_validate(value).model_dump(mode="json")
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.errors()) from error


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
