import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.api.deps import enforce_rate_limit, require_admin_user, require_trusted_origin
from app.api.routes_history import parse_json_object
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.feedback import FeedbackRepository
from app.schemas.auth import (
    ADMIN_DEFAULT_PROVIDERS,
    ADMIN_OCR_PROVIDERS,
    AdminPlanResponse,
    AdminPlanUpdateRequest,
    AdminRenderHistoryDetail,
    AdminRenderHistoryItem,
    AdminSessionResponse,
    AdminSummaryResponse,
    AdminUserUpdateRequest,
    AuditLogResponse,
    SystemAiProfiles,
    SystemAiTierProfiles,
    SystemAiPrompts,
    SystemAiSettings,
    SystemFeatureFlags,
    SystemPlanSettings,
    SystemSettingRequest,
    SystemSettingResponse,
    UserResponse,
)
from app.schemas.feedback import AdminFeedbackResponse, AdminFeedbackUpdateRequest
from app.schemas.scene import MathScene, ModelScanRequest, RenderPayload
from app.services.admin_settings import build_database_diagnostics, normalize_provider_defaults, sync_ai_profiles_to_registry, sync_ai_settings_to_registry, sync_ai_tier_profiles_to_registry
from app.services.database_cleanup import cleanup_database, reset_dev_data
from app.services.model_provider import canonicalize_fallback_models, canonicalize_model_ref, explicit_provider_from_model
from app.services.model_registry import resolve_effective_settings, save_provider_check
from app.services.provider_ping import ADMIN_PING_PROVIDERS, ping_provider
from app.services.storage_diagnostics import check_upload_storage

router = APIRouter(prefix="/api/admin", tags=["admin"])


class DatabaseCleanupRequest(BaseModel):
    dry_run: bool = True
    limit_per_table: int = Field(default=100, ge=1, le=5000)
    tables: list[str] | None = None
    min_age_hours: int = Field(default=24, ge=1, le=24 * 365)
    verify_remote: bool = True
    providers: list[Literal["appwrite", "r2"]] | None = None
    confirm: str | None = Field(default=None, max_length=128)
    delete_remote: bool = False
    delete_db_record: bool = False


class DevDataResetRequest(BaseModel):
    dry_run: bool = True
    confirm: str | None = Field(default=None, max_length=128)
    delete_upload_remotes: bool = False


class StorageCheckRequest(BaseModel):
    provider: Literal["auto", "appwrite", "r2"] = "auto"
    write: bool = False
    read_back: bool = True
    delete_after: bool = True


@router.get("/summary", response_model=AdminSummaryResponse)
async def admin_summary(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> AdminSummaryResponse:
    return AdminSummaryResponse(**await AdminRepository(db).summary())


@router.get("/plans", response_model=list[AdminPlanResponse])
async def admin_plans(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[AdminPlanResponse]:
    return [plan_response(plan) for plan in await AdminRepository(db).list_plans()]


@router.patch("/plans/{plan_id}", response_model=AdminPlanResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_update_plan(
    plan_id: str,
    request: AdminPlanUpdateRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> AdminPlanResponse:
    await enforce_rate_limit(db, http_request, admin, "admin_plan_update", 20, 60)
    repo = AdminRepository(db)
    patch = request.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có thay đổi để cập nhật.")
    current = await repo.find_plan(plan_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy gói người dùng.")
    no_op_fields = [field for field, value in patch.items() if getattr(current, field) == value]
    if len(no_op_fields) == len(patch):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có thay đổi để cập nhật.")
    updated = await repo.update_plan(plan_id, patch)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy gói người dùng.")
    await repo.audit(admin.id, "admin.plan.update", "plan", plan_id, {"fields": sorted(patch)})
    return plan_response(updated)


@router.get("/users", response_model=list[UserResponse])
async def admin_users(
    q: str | None = Query(default=None, max_length=256),
    role: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, max_length=32),
    plan: str | None = Query(default=None, max_length=64),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[UserResponse]:
    repo = AdminRepository(db)
    if plan:
        await validate_known_plan(repo, plan)
    users = await repo.list_users(q, role, status, plan)
    return [user_response(user) for user in users]


@router.get("/users/{user_id}/sessions", response_model=list[AdminSessionResponse])
async def admin_user_sessions(user_id: str, _: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[AdminSessionResponse]:
    sessions = await AdminRepository(db).list_user_sessions(user_id)
    return [AdminSessionResponse(id=item.id, created_at=item.created_at, expires_at=item.expires_at, last_seen_at=item.last_seen_at, ip_address=item.ip_address, user_agent=item.user_agent) for item in sessions]


@router.delete("/users/{user_id}/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_revoke_user_session(
    user_id: str,
    session_id: str,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> None:
    await enforce_rate_limit(db, http_request, admin, "admin_session_revoke", 30, 60)
    repo = AdminRepository(db)
    revoked = await repo.revoke_user_session(user_id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên đăng nhập.")
    await repo.audit(admin.id, "admin.session.revoke", "session", session_id, {"user_id": user_id})


@router.post("/users/{user_id}/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_revoke_user_sessions(
    user_id: str,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> None:
    await enforce_rate_limit(db, http_request, admin, "admin_sessions_revoke_all", 30, 60)
    repo = AdminRepository(db)
    count = await repo.revoke_user_sessions(user_id)
    await repo.audit(admin.id, "admin.sessions.revoke_all", "user", user_id, {"count": count})


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_update_user(
    user_id: str,
    request: AdminUserUpdateRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> UserResponse:
    await enforce_rate_limit(db, http_request, admin, "admin_user_update", 20, 60)
    repo = AdminRepository(db)
    patch = request.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có thay đổi để cập nhật.")
    if user_id == admin.id and ("role" in patch or "status" in patch):
        await repo.audit(admin.id, "admin.user.update.blocked", "user", user_id, {"reason": "self_role_status_change", "fields": sorted(patch)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể tự thay đổi role hoặc trạng thái của chính mình.")
    current = await repo.find_user(user_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
    if "plan" in patch:
        patch["plan"] = await validate_known_plan(repo, str(patch["plan"]))
    effective_role = patch.get("role", current.role)
    effective_status = patch.get("status", current.status)
    removing_active_admin = current.role == "admin" and current.status == "active" and (effective_role != "admin" or effective_status != "active")
    if removing_active_admin and await repo.count_active_admins() <= 1:
        await repo.audit(admin.id, "admin.user.update.blocked", "user", user_id, {"reason": "last_active_admin", "fields": sorted(patch)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể xoá hoặc vô hiệu hoá admin hoạt động cuối cùng.")
    no_op_fields = [field for field, value in patch.items() if getattr(current, field) == value]
    if len(no_op_fields) == len(patch):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không có thay đổi để cập nhật.")
    audit_metadata = build_user_update_audit_metadata(current, patch)
    updated = await repo.update_user(user_id, patch)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
    if patch.get("status") == "disabled":
        revoked_count = await repo.revoke_user_sessions(user_id)
        audit_metadata["revoked_sessions"] = revoked_count
    await repo.audit(admin.id, "admin.user.update", "user", user_id, audit_metadata)
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
            degraded=job.degraded,
            fallback_source=job.fallback_source,  # type: ignore[arg-type]
            ai_source=job.ai_source,  # type: ignore[arg-type]
            schema_version=job.schema_version,
            title=job.title,
            problem_preview=job.problem_preview,
            topic=job.topic,
            grade=job.grade,
            tier=job.tier,
            is_favorite=job.is_favorite,
            archived_at=job.archived_at,
            last_opened_at=job.last_opened_at,
            updated_at=job.history_updated_at,
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
        degraded=job.degraded,
        fallback_source=job.fallback_source,  # type: ignore[arg-type]
        ai_source=job.ai_source,  # type: ignore[arg-type]
        schema_version=job.schema_version,
        title=job.title,
        problem_preview=job.problem_preview,
        topic=job.topic,
        grade=job.grade,
        tier=job.tier,
        is_favorite=job.is_favorite,
        archived_at=job.archived_at,
        last_opened_at=job.last_opened_at,
        updated_at=job.history_updated_at,
        scene=MathScene.model_validate_json(job.scene_json),
        payload=RenderPayload.model_validate_json(job.payload_json),
        warnings=json.loads(job.warnings_json),
        render_request=parse_json_object(job.render_request_json),
        advanced_settings=parse_json_object(job.advanced_settings_json),
        runtime_settings=parse_json_object(job.runtime_settings_json),
    )


@router.delete("/render-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def admin_delete_render_job(
    job_id: str,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> None:
    await enforce_rate_limit(db, http_request, admin, "admin_render_delete", 30, 60)
    repo = AdminRepository(db)
    await repo.delete_render_job(job_id)
    await repo.audit(admin.id, "admin.render_job.delete", "render_job", job_id)


@router.get("/feedback", response_model=list[AdminFeedbackResponse])
async def admin_feedback(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    user_id: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=256),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[AdminFeedbackResponse]:
    if status_filter and status_filter not in {"pending", "received", "accepted"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Trạng thái góp ý không hợp lệ.")
    items = await FeedbackRepository(db).list_admin(status_filter, user_id, q)
    return [
        AdminFeedbackResponse(
            id=item.id,
            user_id=item.user_id,
            user_email=user_email,
            subject=item.subject,
            message=item.message,
            status=item.status,  # type: ignore[arg-type]
            admin_note=item.admin_note,
            created_at=item.created_at,
            updated_at=item.updated_at,
            resolved_at=item.resolved_at,
            resolved_by=item.resolved_by,
        )
        for item, user_email in items
    ]


@router.patch("/feedback/{feedback_id}", response_model=AdminFeedbackResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_update_feedback(
    feedback_id: str,
    request: AdminFeedbackUpdateRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> AdminFeedbackResponse:
    await enforce_rate_limit(db, http_request, admin, "admin_feedback_update", 60, 60)
    repo = FeedbackRepository(db)
    item = await repo.mark_status(feedback_id, request.status, admin.id, request.admin_note)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy góp ý.")
    await AdminRepository(db).audit(admin.id, f"admin.feedback.{request.status}", "feedback", feedback_id, {"status": request.status})
    user = await AdminRepository(db).find_user(item.user_id)
    return AdminFeedbackResponse(
        id=item.id,
        user_id=item.user_id,
        user_email=user.email if user else None,
        subject=item.subject,
        message=item.message,
        status=item.status,  # type: ignore[arg-type]
        admin_note=item.admin_note,
        created_at=item.created_at,
        updated_at=item.updated_at,
        resolved_at=item.resolved_at,
        resolved_by=item.resolved_by,
    )


@router.get("/system-settings", response_model=list[SystemSettingResponse])
async def admin_system_settings(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> list[SystemSettingResponse]:
    settings = await AdminRepository(db).list_system_settings()
    return [SystemSettingResponse(key=item.key, value=parse_setting_value(item.value_json), updated_by=item.updated_by, updated_at=item.updated_at) for item in settings]

@router.get("/database/diagnostics")
async def admin_database_diagnostics(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> dict:
    return await build_database_diagnostics(db)


@router.post("/database/cleanup", dependencies=[Depends(require_trusted_origin)])
async def admin_database_cleanup(
    request: DatabaseCleanupRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict:
    await enforce_rate_limit(db, http_request, admin, "admin_database_cleanup", 5, 60)
    result = await cleanup_database(
        db,
        dry_run=request.dry_run,
        limit_per_table=request.limit_per_table,
        tables=request.tables,
        settings=settings,
        min_age_hours=request.min_age_hours,
        verify_remote=request.verify_remote,
        providers=request.providers,
        confirm=request.confirm,
        delete_remote=request.delete_remote,
        delete_db_record=request.delete_db_record,
    )
    if not request.dry_run:
        summary = {
            table: {
                "deleted": item.get("deleted", 0),
                "cleared": item.get("cleared", 0),
                "bytes_cleared": item.get("bytes_cleared", 0),
            }
            for table, item in result["tables"].items()
        }
        await AdminRepository(db).audit(
            admin.id,
            "admin.database.cleanup",
            "database",
            None,
            {
                "tables": request.tables,
                "summary": summary,
                "min_age_hours": request.min_age_hours,
                "providers": request.providers,
                "delete_remote": request.delete_remote,
                "delete_db_record": request.delete_db_record,
            },
        )
    return result


@router.post("/database/reset-dev-data", dependencies=[Depends(require_trusted_origin)])
async def admin_reset_dev_data(
    request: DevDataResetRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict:
    await enforce_rate_limit(db, http_request, admin, "admin_database_reset_dev_data", 3, 60)
    try:
        result = await reset_dev_data(
            db,
            dry_run=request.dry_run,
            confirm=request.confirm,
            settings=settings,
            delete_upload_remotes=request.delete_upload_remotes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if not request.dry_run:
        await AdminRepository(db).audit(
            admin.id,
            "admin.database.reset_dev_data",
            "database",
            None,
            {
                "tables": result.get("tables", {}),
                "delete_upload_remotes": request.delete_upload_remotes,
                "remote_deleted": result.get("remote_deleted", 0),
                "remote_skipped": result.get("remote_skipped", 0),
            },
        )
    return result


@router.put("/system-settings", response_model=SystemSettingResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_save_system_setting(
    request: SystemSettingRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> SystemSettingResponse:
    await enforce_rate_limit(db, http_request, admin, "admin_system_settings", 30, 60)
    repo = AdminRepository(db)
    raw_value = request.value
    if request.key == "ai_settings":
        current_rows = await repo.list_system_settings()
        current_ai = next((item for item in current_rows if item.key == "ai_settings"), None)
        base_value = parse_setting_value(current_ai.value_json) if current_ai is not None else {}
        raw_value = deep_merge_dict(base_value, request.value)
    value = validate_system_setting(request.key, raw_value)
    setting = await repo.upsert_system_setting(request.key, value, admin.id)
    if request.key == "ai_settings":
        await sync_ai_settings_to_registry(db, value, request.value)
    if request.key == "ai_profiles":
        await sync_ai_profiles_to_registry(db, value, request.value)
    if request.key == "ai_tier_profiles":
        await sync_ai_tier_profiles_to_registry(db, value, request.value)
    await repo.audit(admin.id, "admin.system_settings.update", "system_setting", request.key, {"key": request.key})
    return SystemSettingResponse(key=setting.key, value=parse_setting_value(setting.value_json), updated_by=setting.updated_by, updated_at=setting.updated_at)


@router.post("/storage/check", dependencies=[Depends(require_trusted_origin)])
async def admin_check_storage(
    request: StorageCheckRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict:
    await enforce_rate_limit(db, http_request, admin, "admin_storage_check", 6, 60)
    result = await check_upload_storage(settings, request.provider, request.write, request.read_back, request.delete_after)
    if request.write:
        await AdminRepository(db).audit(
            admin.id,
            "admin.storage.check",
            "storage",
            request.provider,
            {
                "write": request.write,
                "read_back": request.read_back,
                "delete_after": request.delete_after,
                "statuses": {item["provider"]: item["status"] for item in result.get("results", [])},
                "warnings": sum(len(item.get("warnings", [])) for item in result.get("results", [])),
            },
        )
    return result


@router.post("/providers/{provider}/check")
async def admin_check_provider(
    provider: str,
    request: ModelScanRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> dict:
    await enforce_rate_limit(db, http_request, admin, "admin_provider_check", 20, 60)

    settings = await resolve_effective_settings(db, request.runtime_settings)
    result = await ping_provider(provider, settings)
    await save_provider_check(db, result.provider, result.status, result.message)
    return result.as_dict()


@router.post("/providers/check-all")
async def admin_check_all_providers(
    request: ModelScanRequest,
    http_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> dict:
    await enforce_rate_limit(db, http_request, admin, "admin_provider_check_all", 5, 60)

    settings = await resolve_effective_settings(db, request.runtime_settings)
    results = await asyncio.gather(*(ping_provider(provider, settings) for provider in ADMIN_PING_PROVIDERS))
    for result in results:
        await save_provider_check(db, result.provider, result.status, result.message)
    return {"results": [result.as_dict() for result in results]}


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


def deep_merge_dict(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, patch_value in patch.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(patch_value, dict):
            merged[key] = deep_merge_dict(base_value, patch_value)
        else:
            merged[key] = patch_value
    return merged


def validate_system_setting(key: str, value: dict) -> dict:
    if key == "ai_settings":
        value = normalize_provider_defaults(value) or {}
    schemas = {
        "ai_settings": SystemAiSettings,
        "feature_flags": SystemFeatureFlags,
        "ai_profiles": SystemAiProfiles,
        "ai_tier_profiles": SystemAiTierProfiles,
        "ai_prompts": SystemAiPrompts,
    }
    schema = schemas.get(key)
    if schema is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cài đặt hệ thống không hợp lệ.")
    try:
        validated = schema.model_validate(value).model_dump(mode="json")
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=json.loads(error.json())) from error
    if key == "ai_settings":
        validate_ai_settings_rules(SystemAiSettings.model_validate(validated))
    if key == "ai_profiles":
        validate_ai_profiles_rules(SystemAiProfiles.model_validate(validated))
    if key == "ai_tier_profiles":
        validate_ai_tier_profiles_rules(SystemAiTierProfiles.model_validate(validated))
    return validated


def validate_ai_settings_rules(settings: SystemAiSettings) -> None:
    if settings.default_provider not in ADMIN_DEFAULT_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nhà cung cấp mặc định không hợp lệ.")
    for provider_id in ["openrouter", "nvidia", "ollama", "openai_compat", "router9"]:
        provider_settings = getattr(settings, provider_id)
        validate_provider_model_pair(provider_id, provider_settings.model)
        for model_id in provider_settings.allowed_model_ids:
            validate_provider_model_pair(provider_id, model_id)
    if settings.ocr.provider not in ADMIN_OCR_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nhà cung cấp OCR không hợp lệ.")
    validate_provider_model_pair(settings.ocr.provider, settings.ocr.model)
    if settings.router9.only_mode and not settings.router9.model and not settings.router9.allowed_model_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Router9 only mode cần ít nhất một model Router9.")


def validate_ai_profiles_rules(profiles: SystemAiProfiles) -> None:
    for profile in [profiles.geometry_reasoning, profiles.solver_explanation, profiles.ocr]:
        if profile.provider not in ADMIN_DEFAULT_PROVIDERS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nhà cung cấp AI không hợp lệ.")
        validate_provider_model_pair(profile.provider, profile.model)
        validate_profile_fallbacks(profile.provider, profile.fallbacks)


def validate_ai_tier_profiles_rules(profiles: SystemAiTierProfiles) -> None:
    """Validate render-only tier model pools."""
    seen: dict[str, str] = {}
    for tier_name in ["tier1", "tier2", "tier3"]:
        tier_profile = getattr(profiles, tier_name)
        for model_ref in tier_profile.models:
            provider_id = explicit_provider_from_model(model_ref)
            if provider_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Model tier phải có dạng provider/model: {model_ref}",
                )
            try:
                ref = canonicalize_model_ref(provider_id, model_ref, strict=True, allow_auto=False)
            except ValueError as error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
            canonical = f"{ref.provider_id}/{ref.model_id}"
            previous_tier = seen.get(canonical)
            if previous_tier and previous_tier != tier_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Model {canonical} đã nằm trong {previous_tier}, không thể chọn lại ở {tier_name}.",
                )
            seen[canonical] = tier_name


def validate_provider_model_pair(provider_id: str, model_id: str) -> None:
    if not model_id:
        return
    try:
        canonicalize_model_ref(provider_id, model_id, strict=True)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


def validate_profile_fallbacks(provider_id: str, fallbacks: list[str]) -> None:
    try:
        canonicalize_fallback_models(provider_id, fallbacks, strict=True)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


def build_user_update_audit_metadata(current: UserRecord, patch: dict) -> dict:
    metadata: dict[str, object] = {"fields": sorted(patch)}
    for field in ["role", "status", "plan"]:
        if field in patch:
            metadata[field] = {"from": getattr(current, field), "to": patch[field]}
    if "display_name" in patch:
        metadata["display_name"] = {"changed": current.display_name != patch["display_name"], "cleared": patch["display_name"] is None}
    return metadata


async def validate_known_plan(repo: AdminRepository, plan: str) -> str:
    record = await repo.find_plan(plan)
    if record is None or not record.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Gói người dùng không hợp lệ.")
    return plan


def plan_response(plan) -> AdminPlanResponse:
    return AdminPlanResponse(
        id=plan.id,
        name=plan.name,
        daily_render_limit=plan.daily_render_limit,
        daily_ocr_limit=plan.daily_ocr_limit,
        sort_order=plan.sort_order,
        is_active=plan.is_active,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


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
