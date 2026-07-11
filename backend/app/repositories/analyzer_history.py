from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.db.session import DatabaseClient


class AnalyzerHistoryRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        *,
        original_expression: str,
        canonical_expression: str,
        parameters: dict[str, Any],
        window: dict[str, Any],
        tools: dict[str, Any],
        result: dict[str, Any],
        verification: dict[str, Any],
        tags: list[str],
        pinned: bool,
        grade: int,
        chapter: str,
        explanation_level: str,
        engine_version: str,
        schema_version: str,
        parent_history_id: str | None = None,
    ) -> dict[str, Any]:
        item_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO analyzer_history (
              id, user_id, original_expression, canonical_expression, parameter_json, window_json,
              tools_json, result_json, verification_json, tags_json, is_pinned, grade, chapter,
              explanation_level, engine_version, schema_version, parent_history_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item_id, user_id, original_expression, canonical_expression,
                _json(parameters), _json(window), _json(tools), _json(result), _json(verification),
                _json(normalize_tags(tags)), 1 if pinned else 0, grade, chapter,
                explanation_level, engine_version, schema_version, parent_history_id,
            ],
        )
        row = await self.find_for_user(user_id, item_id, touch=False)
        if row is None:
            raise RuntimeError("Không thể lưu lịch sử analyzer.")
        return row

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 30,
        q: str | None = None,
        tag: str | None = None,
        pinned: bool | None = None,
        chapter: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["user_id = ?"]
        params: list[object] = [user_id]
        if q:
            like = f"%{q.strip().lower()}%"
            clauses.append("(lower(original_expression) LIKE ? OR lower(canonical_expression) LIKE ? OR lower(COALESCE(chapter, '')) LIKE ?)")
            params.extend([like, like, like])
        if tag:
            clauses.append("lower(tags_json) LIKE ?")
            params.append(f'%"{tag.strip().lower()}"%')
        if pinned is not None:
            clauses.append("is_pinned = ?")
            params.append(1 if pinned else 0)
        if chapter:
            clauses.append("chapter = ?")
            params.append(chapter)
        params.append(max(1, min(limit, 100)))
        rows = await self.db.fetch_all(
            f"""
            SELECT id, user_id, original_expression, canonical_expression, parameter_json, tags_json,
                   is_pinned, grade, chapter, explanation_level, engine_version, schema_version,
                   parent_history_id, last_opened_at, created_at, updated_at
            FROM analyzer_history
            WHERE {' AND '.join(clauses)}
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT ?
            """,
            params,
        )
        return [decode_row(row) for row in rows]

    async def find_for_user(self, user_id: str, item_id: str, *, touch: bool = True) -> dict[str, Any] | None:
        row = await self.db.fetch_one("SELECT * FROM analyzer_history WHERE id = ? AND user_id = ?", [item_id, user_id])
        if row is None:
            return None
        if touch:
            await self.db.execute(
                "UPDATE analyzer_history SET last_opened_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                [item_id, user_id],
            )
        return decode_row(row)

    async def patch_for_user(
        self,
        user_id: str,
        item_id: str,
        *,
        tags: list[str] | None = None,
        pinned: bool | None = None,
        chapter: str | None = None,
    ) -> dict[str, Any] | None:
        if await self.find_for_user(user_id, item_id, touch=False) is None:
            return None
        assignments: list[str] = []
        params: list[object] = []
        if tags is not None:
            assignments.append("tags_json = ?")
            params.append(_json(normalize_tags(tags)))
        if pinned is not None:
            assignments.append("is_pinned = ?")
            params.append(1 if pinned else 0)
        if chapter is not None:
            assignments.append("chapter = ?")
            params.append(chapter)
        if assignments:
            params.extend([item_id, user_id])
            await self.db.execute(
                f"UPDATE analyzer_history SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                params,
            )
        return await self.find_for_user(user_id, item_id, touch=False)

    async def delete_for_user(self, user_id: str, item_id: str) -> bool:
        if await self.find_for_user(user_id, item_id, touch=False) is None:
            return False
        await self.db.execute("DELETE FROM analyzer_history WHERE id = ? AND user_id = ?", [item_id, user_id])
        return True


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in tags:
        value = raw.strip().lower()
        if value and len(value) <= 32 and value not in normalized:
            normalized.append(value)
    return normalized[:12]


def decode_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    for source, target, fallback in (
        ("parameter_json", "parameters", {}),
        ("window_json", "window", {}),
        ("tools_json", "tools", {}),
        ("result_json", "result", {}),
        ("verification_json", "verification", {}),
        ("tags_json", "tags", []),
    ):
        if source in output:
            try:
                output[target] = json.loads(output.pop(source) or _json(fallback))
            except (TypeError, ValueError):
                output[target] = fallback
    output["pinned"] = bool(output.pop("is_pinned", False))
    return output


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)