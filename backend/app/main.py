from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_admin import router as admin_router
from app.api.routes_ai_models import router as ai_models_router
from app.api.routes_algebra_solve import router as algebra_solve_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_diagram import router as diagram_router
from app.api.routes_export import router as export_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_function_analysis import router as function_analysis_router
from app.api.routes_health import router as health_router
from app.api.routes_history import router as history_router
from app.api.routes_ocr import router as ocr_router
from app.api.routes_render import router as render_router
from app.api.routes_settings import router as settings_router
from app.api.routes_solve import router as solve_router
from app.api.routes_telemetry import router as telemetry_router
from app.api.routes_user_profile import router as user_profile_router
from app.api.routes_user_settings import router as user_settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_request_id, set_request_id
from app.db.migrations import apply_migrations
from app.db.session import create_database_client  # re-export for tests
from app.services.router9_bootstrap import bootstrap_router9_models

configure_logging()
settings = get_settings()


def _init_sentry() -> None:
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.05, environment=settings.environment)
    except Exception:
        pass


_init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_settings = get_settings()
    from app.db.session import close_shared_database, init_shared_database

    db = await init_shared_database(current_settings)
    await apply_migrations(db, current_settings)
    await bootstrap_router9_models(current_settings)
    yield
    from app.services.http_pool import close_all
    from app.services.redis_client import close_redis

    await close_all()
    await close_redis()
    await close_shared_database()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        set_request_id(None)
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(("/api/analyze", "/api/analyzer")):
        request_id = get_request_id() or ""
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "ANALYZER_INPUT_INVALID",
                    "message": "Dữ liệu yêu cầu phân tích không hợp lệ.",
                    "correlation_id": request_id,
                    "stage": "request",
                    "retryable": False,
                }
            },
            headers={"X-Request-Id": request_id},
        )
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith(("/api/analyze", "/api/analyzer")) and exc.status_code == 429:
        current = exc.detail if isinstance(exc.detail, dict) else {}
        if current.get("code") != "ANALYZER_RATE_LIMITED":
            exc.detail = {
                "code": "ANALYZER_RATE_LIMITED",
                "message": "Analyzer đang quá tải. Hãy thử lại sau.",
                "correlation_id": get_request_id() or "",
                "stage": "rate_limit",
                "retryable": True,
            }
    # Only persist true server failures — coded 4xx from api_error would flood analytics.
    if exc.status_code >= 500:
        try:
            from app.db.session import get_shared_database
            from app.repositories.errors import try_record_error_event
            from app.services.provider_logging import redact_sensitive

            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            raw = str(detail.get("message") or detail.get("debug_message") or exc.detail)
            message = redact_sensitive(raw)[:1000]
            await try_record_error_event(
                get_shared_database(),
                message=message,
                source="server",
                request_id=get_request_id(),
                route=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                error_code=str(detail.get("code") or f"HTTP_{exc.status_code}"),
                metadata={"detail_type": type(exc.detail).__name__},
            )
        except Exception:
            pass
    headers = {str(k): str(v) for k, v in (exc.headers or {}).items()}
    headers["X-Request-Id"] = get_request_id() or headers.get("X-Request-Id") or ""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging

    logging.getLogger("app").exception("Unhandled error path=%s", request.url.path)
    try:
        from app.db.session import get_shared_database
        from app.repositories.errors import try_record_error_event
        from app.services.provider_logging import redact_sensitive

        safe_message = redact_sensitive(f"{exc.__class__.__name__}: {exc}")[:1000]
        safe_stack = redact_sensitive(repr(exc))[:2000]
        await try_record_error_event(
            get_shared_database(),
            message=safe_message or exc.__class__.__name__,
            source="server",
            request_id=get_request_id(),
            route=str(request.url.path),
            method=request.method,
            status_code=500,
            error_code="INTERNAL_ERROR",
            stack=safe_stack,
        )
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": "Lỗi nội bộ máy chủ."}},
        headers={"X-Request-Id": get_request_id() or ""},
    )


app.include_router(admin_router)
app.include_router(ai_models_router)
app.include_router(algebra_solve_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(history_router)
app.include_router(ocr_router)
app.include_router(render_router)
app.include_router(export_router)
app.include_router(diagram_router)
app.include_router(feedback_router)
app.include_router(settings_router)
app.include_router(user_profile_router)
app.include_router(user_settings_router)
app.include_router(solve_router)
app.include_router(function_analysis_router)
app.include_router(telemetry_router)
