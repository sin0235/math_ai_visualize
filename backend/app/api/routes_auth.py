from sqlite3 import IntegrityError

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.api.deps import get_current_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.auth import SESSION_COOKIE_NAME, SessionRepository, UserRepository
from app.schemas.auth import AuthRequest, AuthResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: AuthRequest, response: Response, db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> AuthResponse:
    users = UserRepository(db)
    sessions = SessionRepository(db)
    if await users.find_by_email(request.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được đăng ký.")
    try:
        user = await users.create(request.email, request.password)
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email này đã được đăng ký.") from error
    _, token = await sessions.create(user.id)
    set_session_cookie(response, token, settings)
    return AuthResponse(user=user_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthRequest, response: Response, db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> AuthResponse:
    users = UserRepository(db)
    user = await users.find_by_email(request.email)
    if user is None or not users.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng.")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị vô hiệu hoá.")
    await users.mark_login(user.id)
    user = await users.find_by_id(user.id) or user
    _, token = await SessionRepository(db).create(user.id)
    set_session_cookie(response, token, settings)
    return AuthResponse(user=user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def logout(
    response: Response,
    hinh_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> Response:
    if hinh_session:
        await SessionRepository(db).delete_by_token(hinh_session)
    response.delete_cookie(SESSION_COOKIE_NAME, **cookie_options(settings, include_httponly=False))
    return response


@router.get("/me", response_model=AuthResponse)
async def me(user: UserRecord = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=user_response(user))


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
    )
