from ipaddress import ip_address, ip_network
from urllib.parse import urlparse

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.auth import SESSION_COOKIE_NAME, RateLimitRepository, SessionRepository, UserRepository


async def get_current_user(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserRecord:
    if settings.dev_bypass_auth:
        return UserRecord(
            id="dev_user",
            email="dev@example.com",
            password_hash="",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            role="admin",
            status="active",
            display_name="Dev User",
            email_verified_at="2024-01-01T00:00:00Z",
        )
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
    if settings.require_email_verification and user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn cần xác minh email trước khi dùng tài khoản.")
    return user


async def get_optional_current_user(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserRecord | None:
    if settings.dev_bypass_auth:
        return UserRecord(
            id="dev_user",
            email="dev@example.com",
            password_hash="",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            role="admin",
            status="active",
            display_name="Dev User",
            email_verified_at="2024-01-01T00:00:00Z",
        )
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


async def enforce_rate_limit(
    db: DatabaseClient,
    request: Request,
    user: UserRecord | None,
    name: str,
    limit: int,
    window_seconds: int,
    settings: Settings | None = None,
) -> None:
    subject = f"user:{user.id}" if user is not None else f"ip:{client_ip(request, settings)}"
    result = await RateLimitRepository(db).hit(f"endpoint:{name}:{subject}", limit, window_seconds)
    if result.allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Bạn thao tác quá nhanh. Hãy thử lại sau.",
        headers={"Retry-After": str(result.retry_after_seconds)},
    )


def origin_allowed(source: str, allowed_origins: list[str]) -> bool:
    parsed_source = urlparse(source)
    if not parsed_source.scheme or not parsed_source.netloc:
        return False
    source_origin = f"{parsed_source.scheme}://{parsed_source.netloc}"
    return "*" in allowed_origins or source_origin in allowed_origins


def client_ip(request: Request, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    peer = request.client.host if request.client else "unknown"
    if not peer_is_trusted_proxy(peer, current_settings.trusted_proxy_ips):
        return peer[:64]
    for header_name in ("x-forwarded-for", "x-real-ip"):
        header_value = request.headers.get(header_name)
        if not header_value:
            continue
        forwarded = first_valid_forwarded_ip(header_value)
        if forwarded:
            return forwarded[:64]
    return peer[:64]


def peer_is_trusted_proxy(peer: str, trusted_proxy_ips: list[str]) -> bool:
    try:
        peer_ip = ip_address(peer)
    except ValueError:
        return False
    for value in trusted_proxy_ips:
        try:
            if peer_ip in ip_network(value, strict=False):
                return True
        except ValueError:
            continue
    return False


def first_valid_forwarded_ip(header_value: str) -> str | None:
    for value in header_value.split(","):
        candidate = value.strip()
        if not candidate:
            continue
        try:
            return str(ip_address(candidate))
        except ValueError:
            continue
    return None
