from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from sqlite3 import IntegrityError
from typing import Any

from app.db.session import DatabaseClient


class AnalyzerLinkRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        owner_user_id: str,
        *,
        kind: str,
        target: str,
        payload_version: str,
        payload: dict[str, Any],
        visibility: str,
        scopes: list[str],
        allowed_origins: list[str],
        expires_in_minutes: int,
        max_uses: int,
    ) -> dict[str, Any]:
        expires_at = (datetime.now(UTC) + timedelta(minutes=expires_in_minutes)).isoformat()
        for _ in range(3):
            short_id = secrets.token_urlsafe(12)
            try:
                await self.db.execute(
                    """
                    INSERT INTO analyzer_links (
                      short_id, owner_user_id, kind, target, payload_version, payload_json,
                      visibility, scopes_json, allowed_origins_json, max_uses, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [short_id, owner_user_id, kind, target, payload_version, _json(payload), visibility,
                     _json(scopes), _json(allowed_origins), max_uses, expires_at],
                )
                return (await self.find(short_id)) or {}
            except IntegrityError:
                continue
        raise RuntimeError("Không thể tạo short ID duy nhất.")

    async def find(self, short_id: str) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM analyzer_links WHERE short_id = ?", [short_id])
        return decode_link(row) if row else None

    async def consume(self, short_id: str) -> dict[str, Any] | None:
        current = await self.find(short_id)
        if current is None:
            return None
        now = datetime.now(UTC).isoformat()
        one_time_clause = "AND consumed_at IS NULL" if current["kind"] == "handoff" else ""
        consumed_at = now if current["kind"] == "handoff" else None
        row = await self.db.fetch_one(
            f"""
            UPDATE analyzer_links
            SET use_count = use_count + 1, consumed_at = COALESCE(consumed_at, ?)
            WHERE short_id = ? AND revoked_at IS NULL AND expires_at > ?
              AND use_count < max_uses {one_time_clause}
            RETURNING *
            """,
            [consumed_at, short_id, now],
        )
        return decode_link(row) if row else None

    async def revoke(self, owner_user_id: str, short_id: str) -> bool:
        row = await self.find(short_id)
        if row is None or row["owner_user_id"] != owner_user_id:
            return False
        await self.db.execute(
            "UPDATE analyzer_links SET revoked_at = CURRENT_TIMESTAMP WHERE short_id = ? AND owner_user_id = ?",
            [short_id, owner_user_id],
        )
        return True


def decode_link(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    for source, target in (("payload_json", "payload"), ("scopes_json", "scopes"), ("allowed_origins_json", "allowed_origins")):
        try:
            output[target] = json.loads(output.pop(source))
        except (TypeError, ValueError):
            output[target] = {} if target == "payload" else []
    return output


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)