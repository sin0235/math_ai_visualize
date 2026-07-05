from __future__ import annotations

import json
import logging
from uuid import uuid4

from app.db.models import DbRow, UserActivityEventRecord
from app.db.session import DatabaseClient

SENSITIVE_METADATA_MARKERS = ("api_key", "apikey", "key", "secret", "token", "password", "ciphertext", "authorization", "cookie", "base_url", "url")
logger = logging.getLogger(__name__)


class UserActivityRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        event_type: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict | None = None,
        session_id: str | None = None,
        source: str = "server",
    ) -> UserActivityEventRecord:
        event_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO user_activity_events (id, user_id, session_id, event_type, target_type, target_id, source, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [event_id, user_id, session_id, event_type, target_type, target_id, source, json.dumps(safe_activity_metadata(metadata or {}), ensure_ascii=False)],
        )
        row = await self.db.fetch_one("SELECT * FROM user_activity_events WHERE id = ?", [event_id])
        if row is None:
            raise RuntimeError("Không thể lưu log hoạt động.")
        return user_activity_event_from_row(row)


async def log_user_activity(
    db: DatabaseClient,
    user_id: str,
    event_type: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await UserActivityRepository(db).create(user_id, event_type, target_type=target_type, target_id=target_id, metadata=metadata)


async def try_log_user_activity(
    db: DatabaseClient,
    user_id: str,
    event_type: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        await log_user_activity(db, user_id, event_type, target_type=target_type, target_id=target_id, metadata=metadata)
    except Exception as error:
        logger.warning("Không thể lưu log hoạt động %s cho user %s: %s", event_type, user_id, error)


def safe_activity_metadata(value):
    if isinstance(value, dict):
        clean = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)[:80]
            if is_sensitive_metadata_key(key):
                continue
            clean[key] = safe_activity_metadata(raw_value)
        return clean
    if isinstance(value, list):
        return [safe_activity_metadata(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [safe_activity_metadata(item) for item in value[:20]]
    if isinstance(value, str):
        return value[:300]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:300]


def is_sensitive_metadata_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(marker in lowered for marker in SENSITIVE_METADATA_MARKERS)


def user_activity_event_from_row(row: DbRow) -> UserActivityEventRecord:
    return UserActivityEventRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        session_id=str(row["session_id"]) if row.get("session_id") is not None else None,
        event_type=str(row["event_type"]),
        target_type=str(row["target_type"]) if row.get("target_type") is not None else None,
        target_id=str(row["target_id"]) if row.get("target_id") is not None else None,
        source=str(row.get("source") or "server"),
        metadata_json=str(row.get("metadata_json") or "{}"),
        created_at=str(row["created_at"]),
    )