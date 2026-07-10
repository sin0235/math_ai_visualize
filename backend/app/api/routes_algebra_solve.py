from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import enforce_rate_limit, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository
from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.ai_resolution import resolve_byok_ai_config, settings_with_byok_connection
from app.services.algebra import solve_algebra_with_optional_ai
from app.services.algebra.load_gate import algebra_load_gate
from app.services.api_errors import api_error
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api/algebra", tags=["algebra"])
_DAY = 86_400


@router.post("/solve", response_model=AlgebraSolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_algebra_endpoint(
    request: AlgebraSolveRequest,
    http_request: Request,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AlgebraSolveResponse | JSONResponse:
    uses_ai = request.options.use_ai_extraction or request.options.ai_explanation
    user = await _active_user_from_request(http_request, db)
    await enforce_rate_limit(db, http_request, user, "algebra_solve", 60 if user else 20, 60, settings)
    daily = max(1, int(settings.algebra_daily_limit or 200))
    await enforce_rate_limit(db, http_request, user, "algebra_solve_daily", daily, _DAY, settings)
    byok_used = False
    if uses_ai:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn cần đăng nhập để dùng AI nhận dạng đề đại số.")
        if settings.require_email_verification and user.email_verified_at is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn cần xác minh email trước khi dùng AI nhận dạng đề đại số.")
        await enforce_rate_limit(db, http_request, user, "algebra_ai", 20, 60)
        ai_daily = max(1, int(settings.algebra_ai_daily_limit or 50))
        await enforce_rate_limit(db, http_request, user, "algebra_ai_daily", ai_daily, _DAY, settings)
        await enforce_render_access(db, user)
        try:
            byok = await resolve_byok_ai_config(db, user, "solver", settings)
        except UserAiSettingsError as error:
            raise api_error(400, f"Cấu hình BYOK không hợp lệ: {error}", "ALGEBRA_SOLVE_FAILED") from error
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            byok_used = True

    limit = max(1, int(settings.algebra_max_concurrent or 8))
    slot = await algebra_load_gate.try_acquire(limit)
    if slot is None:
        raise api_error(
            429,
            "Hệ thống đang xử lý quá nhiều bài đại số. Vui lòng thử lại sau.",
            "ALGEBRA_CONCURRENT_LIMIT",
        )

    try:
        try:
            response = await solve_algebra_with_optional_ai(request, settings, load_slot=slot)
        except Exception as error:
            message = str(error)
            if "timeout" in message.lower() or "ALGEBRA_TIMEOUT" in message:
                timeout_body = _timeout_payload(request, message)
                return JSONResponse(status_code=504, content=timeout_body)
            raise api_error(500, "Lỗi nội bộ khi giải bài đại số.", "ALGEBRA_INTERNAL_ERROR") from error
        if response.problem_type == "timeout" or any("ALGEBRA_TIMEOUT" in item for item in response.errors):
            # Preserve structured body (request_id, warnings, timings) for the client.
            return JSONResponse(status_code=504, content=response.model_dump(mode="json"))
        if user is not None:
            await AdminRepository(db).record_user_usage_event(
                user.id,
                "algebra_solve",
                {"topic": response.topic, "status": response.status, "request_id": response.request_id},
            )
        if uses_ai and user is not None and not byok_used:
            await AdminRepository(db).record_user_usage_event(
                user.id,
                "algebra_ai",
                {
                    "use_ai_extraction": request.options.use_ai_extraction,
                    "ai_explanation": request.options.ai_explanation,
                    "request_id": response.request_id,
                },
            )
        return response
    finally:
        # If worker never started (or already finished), this frees the slot.
        # If an orphan worker is still running, leave_worker will free it later.
        slot.release_http()


def _timeout_payload(request: AlgebraSolveRequest, message: str) -> dict:
    return AlgebraSolveResponse(
        input=request.input,
        normalized_input=request.input,
        topic=str(request.topic),
        problem_type="timeout",
        status="error",
        answer="Phép giải đại số vượt quá thời gian cho phép.",
        errors=[f"ALGEBRA_TIMEOUT: {message}"],
        warnings=["Timeout; worker process có thể đã bị terminate khi isolation bật."],
    ).model_dump(mode="json")


async def _active_user_from_request(request: Request, db: DatabaseClient) -> UserRecord | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session = await SessionRepository(db).find_by_token(token)
    if session is None:
        return None
    user = await UserRepository(db).find_by_id(session.user_id)
    if user is None or user.status != "active":
        return None
    return user
