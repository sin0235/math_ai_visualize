from sqlite3 import IntegrityError
from uuid import uuid4

from app.db.models import DbRow, FeedbackRecord
from app.db.session import DatabaseClient


class PendingFeedbackError(Exception):
    pass


class FeedbackRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, user_id: str, subject: str, message: str) -> FeedbackRecord:
        if await self.find_pending_for_user(user_id):
            raise PendingFeedbackError
        feedback_id = str(uuid4())
        try:
            await self.db.execute(
                """
                INSERT INTO feedback (id, user_id, subject, message)
                VALUES (?, ?, ?, ?)
                """,
                [feedback_id, user_id, subject, message],
            )
        except IntegrityError as error:
            raise PendingFeedbackError from error
        feedback = await self.find(feedback_id)
        if feedback is None:
            raise RuntimeError("Không thể tạo góp ý.")
        return feedback

    async def find(self, feedback_id: str) -> FeedbackRecord | None:
        row = await self.db.fetch_one("SELECT * FROM feedback WHERE id = ?", [feedback_id])
        return feedback_from_row(row) if row else None

    async def find_pending_for_user(self, user_id: str) -> FeedbackRecord | None:
        row = await self.db.fetch_one(
            "SELECT * FROM feedback WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            [user_id],
        )
        return feedback_from_row(row) if row else None

    async def latest_for_user(self, user_id: str) -> FeedbackRecord | None:
        row = await self.db.fetch_one("SELECT * FROM feedback WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", [user_id])
        return feedback_from_row(row) if row else None

    async def list_for_user(self, user_id: str, limit: int = 50) -> list[FeedbackRecord]:
        rows = await self.db.fetch_all(
            "SELECT * FROM feedback WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            [user_id, min(max(limit, 1), 100)],
        )
        return [feedback_from_row(row) for row in rows]

    async def list_admin(
        self,
        status: str | None = None,
        user_id: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[tuple[FeedbackRecord, str | None]]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("f.status = ?")
            params.append(status)
        if user_id:
            clauses.append("f.user_id = ?")
            params.append(user_id)
        if query:
            clauses.append("(lower(f.subject) LIKE ? OR lower(f.message) LIKE ? OR lower(u.email) LIKE ? OR f.id LIKE ?)")
            needle = f"%{query.lower()}%"
            params.extend([needle, needle, needle, f"%{query}%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(
            f"""
            SELECT f.*, u.email AS user_email
            FROM feedback f
            LEFT JOIN users u ON u.id = f.user_id
            {where}
            ORDER BY f.created_at DESC
            LIMIT ?
            """,
            params,
        )
        return [(feedback_from_row(row), str(row["user_email"]) if row.get("user_email") is not None else None) for row in rows]

    async def mark_status(self, feedback_id: str, status: str, admin_id: str, admin_note: str | None = None) -> FeedbackRecord | None:
        current = await self.find(feedback_id)
        if current is None:
            return None
        await self.db.execute(
            """
            UPDATE feedback
            SET status = ?, admin_note = ?, updated_at = CURRENT_TIMESTAMP, resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
            WHERE id = ?
            """,
            [status, admin_note, admin_id, feedback_id],
        )
        return await self.find(feedback_id)


def feedback_from_row(row: DbRow) -> FeedbackRecord:
    return FeedbackRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        subject=str(row["subject"]),
        message=str(row["message"]),
        status=str(row["status"]),
        admin_note=str(row["admin_note"]) if row.get("admin_note") is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        resolved_at=str(row["resolved_at"]) if row.get("resolved_at") is not None else None,
        resolved_by=str(row["resolved_by"]) if row.get("resolved_by") is not None else None,
    )
