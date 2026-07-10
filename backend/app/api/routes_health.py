from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import require_admin_user
from app.core.config import get_settings
from app.db.migrations import build_migration_drift
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.errors import ErrorEventRepository
from app.services.model_registry import load_model_registry

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(response: Response, db: DatabaseClient = Depends(get_database)) -> dict[str, Any]:
    database = await _database_status(db)
    if not database.get("ok"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": database}
    return {"status": "ready", "database": {"ok": True, "backend": database.get("backend")}}


@router.get("/health/detail")
async def detailed_health(_: UserRecord = Depends(require_admin_user), db: DatabaseClient = Depends(get_database)) -> dict[str, Any]:
    settings = get_settings()
    database = await _database_status(db)
    providers = await _provider_status(db)
    status_value = "ok" if database["ok"] else "degraded"
    from app.services.load_gates import all_gate_stats
    from app.services.redis_client import redis_ping

    load = {
        "gates": all_gate_stats(),
        "render_max_concurrent": settings.render_max_concurrent,
        "ocr_max_concurrent": settings.ocr_max_concurrent,
        "algebra_max_concurrent": settings.algebra_max_concurrent,
        "render_async_enabled": settings.render_async_enabled,
    }
    redis = await redis_ping()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    analytics = {
        "errors_24h": await ErrorEventRepository(db).count_since(today),
        "failed_renders_24h": await _count_failed_renders_since(db, today),
    }
    return {
        "status": status_value,
        "app": settings.app_name,
        "database": database,
        "providers": providers,
        "load": load,
        "redis": redis,
        "analytics": analytics,
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


async def _count_failed_renders_since(db: DatabaseClient, since: str) -> int:
    try:
        row = await db.fetch_one(
            "SELECT COUNT(*) AS count FROM render_jobs WHERE status = 'failed' AND created_at >= ?",
            [since],
        )
        return int((row or {}).get("count") or 0)
    except Exception:
        return 0


async def _database_status(db: DatabaseClient) -> dict[str, Any]:
    try:
        probe = await db.fetch_one("SELECT 1 AS ok")
        migrations = await db.fetch_all("SELECT filename, applied_at FROM schema_migrations ORDER BY filename")
        migration_drift = await build_migration_drift(db)
        database_ok = bool(probe and probe.get("ok") == 1)
        pool = db.pool_stats() if hasattr(db, "pool_stats") else {"backend": getattr(db, "backend", "unknown")}
        return {
            "ok": database_ok and bool(migration_drift["ok"]),
            "backend": getattr(db, "backend", "unknown"),
            "migration_count": len(migrations),
            "latest_migration": migrations[-1]["filename"] if migrations else None,
            "migration_drift": migration_drift,
            "pool": pool,
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
            "allowed_model_count": len(registry.allowed_model_ids(provider.id)),
            "model_count": len(registry.models.get(provider.id, [])),
            "last_check_status": provider.last_check_status,
            "last_check_message": provider.last_check_message,
            "last_checked_at": provider.last_checked_at,
        }
        for provider in registry.providers.values()
    ]
