from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_ai_models import router as ai_models_router
from app.api.routes_algebra_solve import router as algebra_solve_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_diagram import router as diagram_router
from app.api.routes_export import router as export_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_function_analysis import router as function_analysis_router
from app.api.routes_history import router as history_router
from app.api.routes_ocr import router as ocr_router
from app.api.routes_render import router as render_router
from app.api.routes_settings import router as settings_router
from app.api.routes_solve import router as solve_router
from app.api.routes_user_settings import router as user_settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.migrations import apply_migrations
from app.db.session import create_database_client
from app.services.router9_bootstrap import bootstrap_router9_models

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_settings = get_settings()
    await apply_migrations(create_database_client(current_settings), current_settings)
    await bootstrap_router9_models(current_settings)
    yield
    from app.services.http_pool import close_all
    await close_all()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(user_settings_router)
app.include_router(solve_router)
app.include_router(function_analysis_router)
