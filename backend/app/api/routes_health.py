from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_admin_user
from app.core.config import get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.services.model_registry import load_model_registry

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/detail")
async def detailed_health(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> dict[str, Any]:
    settings = get_settings()
    database = await _database_status(db)
    providers = await _provider_status(db)
    status = "ok" if database["ok"] else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "database": database,
        "providers": providers,
    }


@router.get("/ai/status")
async def ai_status(db: DatabaseClient = Depends(get_database)) -> dict[str, Any]:
    settings = get_settings()
    registry = await load_model_registry(db, settings)
    return {
        "provider": settings.ai_provider,
        "router9_only": bool(registry.settings.get("router9_only", settings.router9_only)),
        "providers": [
            {
                "id": provider.id,
                "label": provider.label,
                "enabled": provider.enabled,
                "allowed_model_count": len(registry.allowed_model_ids(provider.id)),
                "model_count": len(registry.models.get(provider.id, [])),
            }
            for provider in registry.providers.values()
        ],
    }


async def _database_status(db: DatabaseClient) -> dict[str, Any]:
    try:
        probe = await db.fetch_one("SELECT 1 AS ok")
        migrations = await db.fetch_all("SELECT filename, applied_at FROM schema_migrations ORDER BY filename")
        return {
            "ok": bool(probe and probe.get("ok") == 1),
            "backend": getattr(db, "backend", "unknown"),
            "migration_count": len(migrations),
            "latest_migration": migrations[-1]["filename"] if migrations else None,
        }
    except Exception as error:
        return {
            "ok": False,
            "backend": getattr(db, "backend", "unknown"),
            "error": str(error),
        }


async def _provider_status(db: DatabaseClient) -> list[dict[str, Any]]:
    settings = get_settings()
    registry = await load_model_registry(db, settings)
    return [
        {
            "id": provider.id,
            "label": provider.label,
            "enabled": provider.enabled,
            "base_url_configured": bool(provider.base_url),
            "api_key_configured": provider.api_key_configured,
            "default_model_id": provider.default_model_id,
            "allowed_model_count": len(registry.allowed_model_ids(provider.id)),
            "model_count": len(registry.models.get(provider.id, [])),
            "last_check_status": provider.last_check_status,
            "last_check_message": provider.last_check_message,
            "last_checked_at": provider.last_checked_at,
        }
        for provider in registry.providers.values()
    ]
