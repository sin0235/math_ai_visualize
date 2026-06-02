from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, require_trusted_origin
from app.api.routes_render import enforce_render_access
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, create_database_client
from app.repositories.admin import AdminRepository
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository
from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.algebra import solve_algebra_with_optional_ai
from app.services.api_errors import api_error

router = APIRouter(prefix="/api/algebra", tags=["algebra"])


@router.post("/solve", response_model=AlgebraSolveResponse, dependencies=[Depends(require_trusted_origin)])
async def solve_algebra_endpoint(
    request: AlgebraSolveRequest,
    http_request: Request,
    settings: Settings = Depends(get_settings),
) -> AlgebraSolveResponse:
    uses_ai = request.options.use_ai_extraction or request.options.ai_explanation
    db: DatabaseClient | None = None
    user: UserRecord | None = None
    if uses_ai:
        db = create_database_client(settings)
        user = await _active_user_from_request(http_request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn cần đăng nhập để dùng AI nhận dạng đề đại số.")
        if settings.require_email_verification and user.email_verified_at is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn cần xác minh email trước khi dùng AI nhận dạng đề đại số.")
        await enforce_rate_limit(db, http_request, user, "algebra_solve", 60, 60, settings)
        await enforce_rate_limit(db, http_request, user, "algebra_ai", 20, 60)
        await enforce_render_access(db, user)
    try:
        response = await solve_algebra_with_optional_ai(request)
    except Exception as error:
        raise api_error(400, f"Lỗi khi giải bài đại số: {error}", "ALGEBRA_SOLVE_FAILED") from error
    if uses_ai and user is not None and db is not None:
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
