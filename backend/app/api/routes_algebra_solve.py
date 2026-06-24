from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from app.services.api_errors import api_error
from app.services.user_ai_settings import UserAiSettingsError

router = APIRouter(prefix="/api/algebra", tags=["algebra"])


@router.post("/solve", response_model=AlgebraSolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_algebra_endpoint(
    request: AlgebraSolveRequest,
    http_request: Request,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AlgebraSolveResponse:
    uses_ai = request.options.use_ai_extraction or request.options.ai_explanation
    user = await _active_user_from_request(http_request, db)
    await enforce_rate_limit(db, http_request, user, "algebra_solve", 60 if user else 20, 60, settings)
    byok_used = False
    if uses_ai:
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn cần đăng nhập để dùng AI nhận dạng đề đại số.")
        if settings.require_email_verification and user.email_verified_at is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn cần xác minh email trước khi dùng AI nhận dạng đề đại số.")
        await enforce_rate_limit(db, http_request, user, "algebra_ai", 20, 60)
        await enforce_render_access(db, user)
        try:
            byok = await resolve_byok_ai_config(db, user, "solver", settings)
        except UserAiSettingsError as error:
            raise api_error(400, f"Cấu hình BYOK không hợp lệ: {error}", "ALGEBRA_SOLVE_FAILED") from error
        if byok is not None:
            settings = settings_with_byok_connection(settings, byok)
            byok_used = True
    try:
        response = await solve_algebra_with_optional_ai(request, settings)
    except Exception as error:
        raise api_error(400, f"Lỗi khi giải bài đại số: {error}", "ALGEBRA_SOLVE_FAILED") from error
    if uses_ai and user is not None and not byok_used:
        await AdminRepository(db).record_user_usage_event(
            user.id,
            "algebra_ai",
            {
                "use_ai_extraction": request.options.use_ai_extraction,
                "ai_explanation": request.options.ai_explanation,
            },
        )
    return response


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
