from datetime import UTC, datetime, timedelta
from hashlib import sha256
from sqlite3 import IntegrityError

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.api.deps import get_current_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import SessionRecord, UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.auth import (
    SESSION_COOKIE_NAME,
    TOKEN_PURPOSE_EMAIL_VERIFICATION,
    TOKEN_PURPOSE_PASSWORD_RESET,
    AuthTokenRepository,
    RateLimitRepository,
    SessionRepository,
    UserRepository,
    normalize_email,
    parse_datetime,
)
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
GENERIC_LOGIN_ERROR = "Email hoặc mật khẩu không đúng."
GENERIC_RESET_MESSAGE = "Nếu tài khoản tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi."
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    raw_request: Request,
    response: Response,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    await enforce_rate_limit(db, f"auth:register:ip:{client_ip(raw_request)}", 10, 3600)
    await enforce_rate_limit(db, f"auth:register:email:{normalize_email(str(request.email))}", 3, 3600)
    users = UserRepository(db)
    sessions = SessionRepository(db)
    if await users.find_by_email(str(request.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được đăng ký.")
    try:
        user = await users.create(str(request.email), request.password)
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được đăng ký.") from error
    if request.display_name:
        user = await users.update_profile(user.id, request.display_name.strip())
    token_repo = AuthTokenRepository(db)
    _, verification_token = await token_repo.create(user.id, TOKEN_PURPOSE_EMAIL_VERIFICATION, 24 * 60, client_ip(raw_request), raw_request.headers.get("user-agent"))
    await send_verification_email(user, verification_token, settings)
    await audit(db, user.id, "auth.registered", "user", user.id, raw_request)
    await audit(db, user.id, "auth.email_verification_sent", "user", user.id, raw_request)
    _, token = await sessions.create(user.id, client_ip(raw_request), raw_request.headers.get("user-agent"))
    set_session_cookie(response, token, settings)
    return AuthResponse(user=user_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    raw_request: Request,
    response: Response,
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    email = normalize_email(str(request.email))
    await enforce_rate_limit(db, f"auth:login:ip:{client_ip(raw_request)}", 20, 15 * 60)
    await enforce_rate_limit(db, f"auth:login:email:{email}", 8, 15 * 60)
    users = UserRepository(db)
    user = await users.find_by_email(email)
    if user is None:
        await audit(db, None, "auth.login_failed", "user", None, raw_request, {"email_hash": email_hash(email)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    if is_locked(user):
        await audit(db, user.id, "auth.login_blocked", "user", user.id, raw_request)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Quá nhiều lần đăng nhập lỗi. Hãy thử lại sau.")
    if not users.verify_password(request.password, user.password_hash):
        user = await users.record_failed_login(user.id)
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            await users.lock_until(user.id, datetime.now(UTC) + timedelta(minutes=LOCK_MINUTES))
            await audit(db, user.id, "auth.login_blocked", "user", user.id, raw_request)
        else:
            await audit(db, user.id, "auth.login_failed", "user", user.id, raw_request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    if user.status != "active":
        await audit(db, user.id, "auth.login_blocked", "user", user.id, raw_request, {"reason": "disabled"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị vô hiệu hoá.")
    await users.mark_login(user.id)
    user = await users.find_by_id(user.id) or user
    _, token = await SessionRepository(db).create(user.id, client_ip(raw_request), raw_request.headers.get("user-agent"))
    set_session_cookie(response, token, settings)
    await audit(db, user.id, "auth.login_success", "user", user.id, raw_request)
    return AuthResponse(user=user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def logout(
    raw_request: Request,
    response: Response,
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    if hinh_session:
        session = await SessionRepository(db).find_by_token(hinh_session)
        await SessionRepository(db).revoke_by_token(hinh_session)
        await audit(db, session.user_id if session else None, "auth.logout", "session", session.id if session else None, raw_request)
    response.delete_cookie(SESSION_COOKIE_NAME, **cookie_options(settings, include_httponly=False))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthResponse)
async def me(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> AuthResponse:
    if hinh_session:
        session = await SessionRepository(db).find_by_token(hinh_session)
        if session:
            await SessionRepository(db).touch(session.id)
    return AuthResponse(user=user_response(user))


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, raw_request: Request, db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> MessageResponse:
    email = normalize_email(str(request.email))
    await enforce_rate_limit(db, f"auth:forgot:ip:{client_ip(raw_request)}", 10, 3600)
    await enforce_rate_limit(db, f"auth:forgot:email:{email}", 3, 3600)
    user = await UserRepository(db).find_by_email(email)
    if user and user.status == "active":
        _, token = await AuthTokenRepository(db).create(user.id, TOKEN_PURPOSE_PASSWORD_RESET, 60, client_ip(raw_request), raw_request.headers.get("user-agent"))
        await send_password_reset_email(user, token, settings)
        await audit(db, user.id, "auth.password_reset_requested", "user", user.id, raw_request)
    else:
        await audit(db, None, "auth.password_reset_requested", "user", None, raw_request, {"email_hash": email_hash(email)})
    return MessageResponse(message=GENERIC_RESET_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, raw_request: Request, db: DatabaseClient = Depends(get_database)) -> MessageResponse:
    await enforce_rate_limit(db, f"auth:reset:ip:{client_ip(raw_request)}", 20, 3600)
    tokens = AuthTokenRepository(db)
    token = await tokens.find_valid_by_token(request.token, TOKEN_PURPOSE_PASSWORD_RESET)
    if token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")
    user = await UserRepository(db).update_password(token.user_id, request.password)
    await tokens.consume(token.id)
    await SessionRepository(db).revoke_all_for_user(user.id)
    await audit(db, user.id, "auth.password_reset_completed", "user", user.id, raw_request)
    return MessageResponse(message="Mật khẩu đã được đặt lại. Hãy đăng nhập bằng mật khẩu mới.")


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(request: VerifyEmailRequest, raw_request: Request, db: DatabaseClient = Depends(get_database)) -> AuthResponse:
    tokens = AuthTokenRepository(db)
    token = await tokens.find_valid_by_token(request.token, TOKEN_PURPOSE_EMAIL_VERIFICATION)
    if token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Liên kết xác minh email không hợp lệ hoặc đã hết hạn.")
    user = await UserRepository(db).mark_email_verified(token.user_id)
    await tokens.consume(token.id)
    await audit(db, user.id, "auth.email_verified", "user", user.id, raw_request)
    return AuthResponse(user=user_response(user))


@router.post("/resend-verification", response_model=MessageResponse, dependencies=[Depends(require_trusted_origin)])
async def resend_verification(
    raw_request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    if user.email_verified_at:
        return MessageResponse(message="Email đã được xác minh.")
    await enforce_rate_limit(db, f"auth:verify:user:{user.id}", 3, 3600)
    _, token = await AuthTokenRepository(db).create(user.id, TOKEN_PURPOSE_EMAIL_VERIFICATION, 24 * 60, client_ip(raw_request), raw_request.headers.get("user-agent"))
    await send_verification_email(user, token, settings)
    await audit(db, user.id, "auth.email_verification_sent", "user", user.id, raw_request)
    return MessageResponse(message="Đã gửi lại liên kết xác minh email.")


@router.post("/change-password", response_model=MessageResponse, dependencies=[Depends(require_trusted_origin)])
async def change_password(
    request: ChangePasswordRequest,
    raw_request: Request,
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> MessageResponse:
    users = UserRepository(db)
    await enforce_rate_limit(db, f"auth:change-password:user:{user.id}", 5, 3600)
    if not users.verify_password(request.current_password, user.password_hash):
        await audit(db, user.id, "auth.password_change_failed", "user", user.id, raw_request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mật khẩu hiện tại không đúng.")
    await users.update_password(user.id, request.new_password)
    await SessionRepository(db).revoke_all_for_user(user.id, except_token=hinh_session)
    await audit(db, user.id, "auth.password_changed", "user", user.id, raw_request)
    return MessageResponse(message="Mật khẩu đã được cập nhật.")


@router.patch("/profile", response_model=AuthResponse, dependencies=[Depends(require_trusted_origin)])
async def update_profile(request: UpdateProfileRequest, raw_request: Request, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> AuthResponse:
    updated = await UserRepository(db).update_profile(user.id, request.display_name)
    await audit(db, user.id, "auth.profile_updated", "user", user.id, raw_request, {"fields": ["display_name"]})
    return AuthResponse(user=user_response(updated))


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> list[SessionResponse]:
    current = await SessionRepository(db).find_by_token(hinh_session) if hinh_session else None
    sessions = await SessionRepository(db).list_for_user(user.id)
    return [session_response(session, current.id if current else None) for session in sessions]


@router.delete("/sessions/{session_id}", response_model=MessageResponse, dependencies=[Depends(require_trusted_origin)])
async def revoke_session(session_id: str, raw_request: Request, user: UserRecord = Depends(get_current_user), db: DatabaseClient = Depends(get_database)) -> MessageResponse:
    revoked = await SessionRepository(db).revoke_by_id(user.id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên đăng nhập.")
    await audit(db, user.id, "auth.session_revoked", "session", session_id, raw_request)
    return MessageResponse(message="Phiên đăng nhập đã được thu hồi.")


@router.post("/sessions/revoke-others", response_model=MessageResponse, dependencies=[Depends(require_trusted_origin)])
async def revoke_other_sessions(
    raw_request: Request,
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> MessageResponse:
    count = await SessionRepository(db).revoke_all_for_user(user.id, except_token=hinh_session)
    await audit(db, user.id, "auth.sessions_revoked_others", "user", user.id, raw_request, {"count": count})
    return MessageResponse(message="Các phiên đăng nhập khác đã được thu hồi.")


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=60 * 60 * 24 * 30,
        **cookie_options(settings, include_httponly=True),
    )


def cookie_options(settings: Settings, include_httponly: bool) -> dict:
    options = {
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
    }
    if include_httponly:
        options["httponly"] = True
    if settings.session_cookie_domain:
        options["domain"] = settings.session_cookie_domain
    return options


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
        email_verified_at=user.email_verified_at,
        password_changed_at=user.password_changed_at,
    )


def session_response(session: SessionRecord, current_session_id: str | None) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        created_at=session.created_at,
        expires_at=session.expires_at,
        last_seen_at=session.last_seen_at,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        current=session.id == current_session_id,
    )


async def enforce_rate_limit(db: DatabaseClient, key: str, limit: int, window_seconds: int) -> None:
    result = await RateLimitRepository(db).hit(key, limit, window_seconds)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"message": "Quá nhiều yêu cầu. Hãy thử lại sau.", "retry_after_seconds": result.retry_after_seconds},
        )


async def audit(
    db: DatabaseClient,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    request: Request,
    metadata: dict | None = None,
) -> None:
    payload = {"ip": client_ip(request), "user_agent": (request.headers.get("user-agent") or "")[:300]}
    if metadata:
        payload.update(metadata)
    await AdminRepository(db).audit(actor_user_id, action, target_type, target_id, payload)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def email_hash(email: str) -> str:
    return sha256(email.encode("utf-8")).hexdigest()


def is_locked(user: UserRecord) -> bool:
    return bool(user.locked_until and parse_datetime(user.locked_until) > datetime.now(UTC))
