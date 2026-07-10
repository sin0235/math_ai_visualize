from __future__ import annotations

import json
from uuid import uuid4

from app.db.session import DatabaseClient


class AlgebraHistoryRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        *,
        title: str | None,
        problem_preview: str,
        topic: str,
        status: str,
        request_id: str | None,
        request_json: str,
        response_json: str,
    ) -> dict:
        item_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO algebra_history (
              id, user_id, title, problem_preview, topic, status, request_id,
              request_json, response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                item_id,
                user_id,
                title,
                (problem_preview or "")[:500],
                topic,
                status,
                request_id,
                request_json,
                response_json,
            ],
        )
        row = await self.db.fetch_one(
            "SELECT * FROM algebra_history WHERE id = ? AND user_id = ?",
            [item_id, user_id],
        )
        if row is None:
            raise RuntimeError("Không thể lưu lịch sử đại số.")
        return dict(row)

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 30,
        q: str | None = None,
        topic: str | None = None,
        favorite: bool | None = None,
        include_archived: bool = False,
    ) -> list[dict]:
        clauses = ["user_id = ?"]
        params: list[object] = [user_id]
        if not include_archived:
            clauses.append("archived_at IS NULL")
        if topic:
            clauses.append("topic = ?")
            params.append(topic)
        if favorite is True:
            clauses.append("is_favorite = 1")
        if favorite is False:
            clauses.append("is_favorite = 0")
        if q:
            clauses.append("(problem_preview LIKE ? OR COALESCE(title, '') LIKE ? OR COALESCE(request_id, '') LIKE ?)")
            like = f"%{q.strip()}%"
            params.extend([like, like, like])
        where = " AND ".join(clauses)
        params.append(max(1, min(int(limit), 100)))
        rows = await self.db.fetch_all(
            f"""
            SELECT id, user_id, title, problem_preview, topic, status, request_id,
                   is_favorite, archived_at, created_at, updated_at
            FROM algebra_history
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        )
        return [dict(row) for row in rows]

    async def find_for_user(self, user_id: str, item_id: str) -> dict | None:
        row = await self.db.fetch_one(
            "SELECT * FROM algebra_history WHERE id = ? AND user_id = ?",
            [item_id, user_id],
        )
        return dict(row) if row is not None else None

    async def delete_for_user(self, user_id: str, item_id: str) -> bool:
        if await self.find_for_user(user_id, item_id) is None:
            return False
        await self.db.execute(
            "DELETE FROM algebra_history WHERE id = ? AND user_id = ?",
            [item_id, user_id],
        )
        return True

    async def patch_for_user(
        self,
        user_id: str,
        item_id: str,
        *,
        title: str | None = None,
        is_favorite: bool | None = None,
        archive: bool | None = None,
    ) -> dict | None:
        if await self.find_for_user(user_id, item_id) is None:
            return None
        assignments: list[str] = []
        params: list[object] = []
        if title is not None:
            assignments.append("title = ?")
            params.append(title[:200] if title else None)
        if is_favorite is not None:
            assignments.append("is_favorite = ?")
            params.append(1 if is_favorite else 0)
        if archive is True:
            assignments.append("archived_at = CURRENT_TIMESTAMP")
        elif archive is False:
            assignments.append("archived_at = NULL")
        if not assignments:
            return await self.find_for_user(user_id, item_id)
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([item_id, user_id])
        await self.db.execute(
            f"UPDATE algebra_history SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            params,
        )
        return await self.find_for_user(user_id, item_id)


def compact_algebra_response_json(response_json: str, *, max_steps: int = 40) -> str:
    try:
        data = json.loads(response_json)
    except Exception:
        return response_json[:200_000]
    steps = data.get("steps")
    if isinstance(steps, list) and len(steps) > max_steps:
        data["steps"] = steps[:max_steps]
        warnings = data.get("warnings") or []
        if isinstance(warnings, list):
            warnings.append(f"Đã cắt steps còn {max_steps} khi lưu lịch sử.")
            data["warnings"] = warnings
    text = json.dumps(data, ensure_ascii=False)
    if len(text) > 400_000:
        data["steps"] = []
        data["milestones"] = (data.get("milestones") or [])[:10]
        text = json.dumps(data, ensure_ascii=False)
    return text
