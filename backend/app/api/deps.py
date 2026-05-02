from urllib.parse import urlparse

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository


async def get_current_user(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
) -> UserRecord:
    if not hinh_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập.")
    session = await SessionRepository(db).find_by_token(hinh_session)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn.")
    user = await UserRepository(db).find_by_id(session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không còn tồn tại.")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị vô hiệu hoá.")
    return user


async def get_optional_current_user(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
) -> UserRecord | None:
    if not hinh_session:
        return None
    session = await SessionRepository(db).find_by_token(hinh_session)
    if session is None:
        return None
    user = await UserRepository(db).find_by_id(session.user_id)
    if user is None or user.status != "active":
        return None
    return user


async def require_active_user(user: UserRecord = Depends(get_current_user)) -> UserRecord:
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị vô hiệu hoá.")
    return user


async def require_admin_user(user: UserRecord = Depends(require_active_user)) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập trang quản trị.")
    return user


async def require_trusted_origin(
    request: Request,
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    settings: Settings = Depends(get_settings),
) -> None:
    if not hinh_session or request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    source = origin or referer
    if not source:
        if settings.allow_missing_origin_for_cookie_mutations:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thiếu thông tin nguồn yêu cầu cho phiên đăng nhập.")
    if origin_allowed(source, settings.cors_origins):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nguồn yêu cầu không được phép dùng phiên đăng nhập này.")


def origin_allowed(source: str, allowed_origins: list[str]) -> bool:
    parsed_source = urlparse(source)
    if not parsed_source.scheme or not parsed_source.netloc:
        return False
    source_origin = f"{parsed_source.scheme}://{parsed_source.netloc}"
    return "*" in allowed_origins or source_origin in allowed_origins
