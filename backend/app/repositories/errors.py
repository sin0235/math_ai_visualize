from __future__ import annotations

import hashlib
import json
import logging
from uuid import uuid4

from app.db.models import DbRow
from app.db.session import DatabaseClient
from app.repositories.activity import safe_activity_metadata

logger = logging.getLogger(__name__)


class ErrorEventRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        *,
        message: str,
        source: str = "server",
        request_id: str | None = None,
        user_id: str | None = None,
        route: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        error_code: str | None = None,
        stack: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        event_id = str(uuid4())
        fingerprint = fingerprint_stack(stack or message)
        await self.db.execute(
            """
            INSERT INTO error_events (
              id, request_id, user_id, source, route, method, status_code, error_code,
              message, stack_fingerprint, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                request_id,
                user_id,
                source,
                route,
                method,
                status_code,
                error_code,
                str(message)[:1000],
                fingerprint,
                json.dumps(safe_activity_metadata(metadata or {}), ensure_ascii=False),
            ],
        )
        return event_id

    async def list_recent(
        self,
        *,
        limit: int = 50,
        error_code: str | None = None,
        source: str | None = None,
        since: str | None = None,
    ) -> list[DbRow]:
        clauses: list[str] = []
        params: list[object] = []
        if error_code:
            clauses.append("error_code = ?")
            params.append(error_code)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        return await self.db.fetch_all(
            f"SELECT * FROM error_events{where} ORDER BY created_at DESC LIMIT ?",
            params,
        )

    async def top_codes(self, since: str, limit: int = 15) -> list[DbRow]:
        return await self.db.fetch_all(
            """
            SELECT COALESCE(error_code, 'UNKNOWN') AS error_code, COUNT(*) AS count
            FROM error_events
            WHERE created_at >= ?
            GROUP BY COALESCE(error_code, 'UNKNOWN')
            ORDER BY count DESC
            LIMIT ?
            """,
            [since, min(max(limit, 1), 50)],
        )

    async def count_since(self, since: str) -> int:
        row = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM error_events WHERE created_at >= ?",
            [since],
        )
        return int((row or {}).get("count") or 0)

    async def daily_counts(self, since: str) -> list[DbRow]:
        return await self.db.fetch_all(
            """
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count
            FROM error_events
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            [since],
        )


async def try_record_error_event(db: DatabaseClient | None, **kwargs) -> None:
    if db is None:
        return
    try:
        await ErrorEventRepository(db).create(**kwargs)
    except Exception as error:
        logger.warning("Không thể lưu error_event: %s", error)


def fingerprint_stack(text: str) -> str:
    normalized = " ".join((text or "").strip().split())[:800]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
