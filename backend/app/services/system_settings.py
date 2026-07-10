import json
import time
from typing import TypeVar

from pydantic import BaseModel

from app.db.session import DatabaseClient
from app.schemas.auth import SystemFeatureFlags, SystemPlanSettings

T = TypeVar("T", bound=BaseModel)

# (monotonic_ts, db_token, value) — keyed by db so isolated tests don't share stale flags.
_FEATURE_FLAGS_CACHE: tuple[float, str, SystemFeatureFlags] | None = None
_PLAN_SETTINGS_CACHE: tuple[float, str, SystemPlanSettings] | None = None
_SETTINGS_CACHE_TTL_SECONDS = 45.0


async def load_system_setting(db: DatabaseClient, key: str, schema: type[T]) -> T:
    row = await db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", [key])
    if row is None:
        return schema()
    try:
        value = json.loads(str(row["value_json"]))
    except json.JSONDecodeError:
        return schema()
    return schema.model_validate(value if isinstance(value, dict) else {})


def _database_cache_token(db: DatabaseClient) -> str:
    backend = str(getattr(db, "backend", db.__class__.__name__))
    path = getattr(db, "path", None)
    return f"{backend}:{path}" if path else f"{backend}:{id(db)}"


async def load_feature_flags(db: DatabaseClient) -> SystemFeatureFlags:
    global _FEATURE_FLAGS_CACHE
    now = time.monotonic()
    token = _database_cache_token(db)
    if (
        _FEATURE_FLAGS_CACHE is not None
        and now - _FEATURE_FLAGS_CACHE[0] < _SETTINGS_CACHE_TTL_SECONDS
        and _FEATURE_FLAGS_CACHE[1] == token
    ):
        return _FEATURE_FLAGS_CACHE[2]
    flags = await load_system_setting(db, "feature_flags", SystemFeatureFlags)
    _FEATURE_FLAGS_CACHE = (now, token, flags)
    return flags


async def load_plan_settings(db: DatabaseClient) -> SystemPlanSettings:
    global _PLAN_SETTINGS_CACHE
    now = time.monotonic()
    token = _database_cache_token(db)
    if (
        _PLAN_SETTINGS_CACHE is not None
        and now - _PLAN_SETTINGS_CACHE[0] < _SETTINGS_CACHE_TTL_SECONDS
        and _PLAN_SETTINGS_CACHE[1] == token
    ):
        return _PLAN_SETTINGS_CACHE[2]
    plans = await load_system_setting(db, "plan_settings", SystemPlanSettings)
    _PLAN_SETTINGS_CACHE = (now, token, plans)
    return plans


def invalidate_system_settings_cache(*_keys: str) -> None:
    """Clear in-process settings cache (call after admin updates)."""
    global _FEATURE_FLAGS_CACHE, _PLAN_SETTINGS_CACHE
    _FEATURE_FLAGS_CACHE = None
    _PLAN_SETTINGS_CACHE = None
