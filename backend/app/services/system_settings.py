import json
from typing import TypeVar

from pydantic import BaseModel

from app.db.session import DatabaseClient
from app.schemas.auth import SystemFeatureFlags, SystemPlanSettings

T = TypeVar("T", bound=BaseModel)


async def load_system_setting(db: DatabaseClient, key: str, schema: type[T]) -> T:
    row = await db.fetch_one("SELECT value_json FROM system_settings WHERE key = ?", [key])
    if row is None:
        return schema()
    try:
        value = json.loads(str(row["value_json"]))
    except json.JSONDecodeError:
        return schema()
    return schema.model_validate(value if isinstance(value, dict) else {})


async def load_feature_flags(db: DatabaseClient) -> SystemFeatureFlags:
    return await load_system_setting(db, "feature_flags", SystemFeatureFlags)


async def load_plan_settings(db: DatabaseClient) -> SystemPlanSettings:
    return await load_system_setting(db, "plan_settings", SystemPlanSettings)
