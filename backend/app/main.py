from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_ai_models import router as ai_models_router
from app.api.routes_health import router as health_router
from app.api.routes_ocr import router as ocr_router
from app.api.routes_render import router as render_router
from app.api.routes_settings import router as settings_router
from app.core.config import get_settings
from app.services.router9_bootstrap import bootstrap_router9_models

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bootstrap_router9_models(settings)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_models_router)
app.include_router(health_router)
app.include_router(ocr_router)
app.include_router(render_router)
app.include_router(settings_router)
