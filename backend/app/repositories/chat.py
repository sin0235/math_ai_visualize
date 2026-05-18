from uuid import uuid4

from app.db.models import ChatConversationRecord, ChatMessageRecord, DbRow
from app.db.session import DatabaseClient


class ChatRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def get_or_create_open_conversation(self, user_id: str) -> ChatConversationRecord:
        existing = await self.find_open_for_user(user_id)
        if existing is not None:
            return existing
        conversation_id = str(uuid4())
        await self.db.execute("INSERT INTO chat_conversations (id, user_id) VALUES (?, ?)", [conversation_id, user_id])
        conversation = await self.find_conversation(conversation_id)
        if conversation is None:
            raise RuntimeError("Không thể tạo cuộc trò chuyện.")
        return conversation

    async def find_open_for_user(self, user_id: str) -> ChatConversationRecord | None:
        row = await self.db.fetch_one(
            "SELECT * FROM chat_conversations WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1",
            [user_id],
        )
        return conversation_from_row(row) if row else None

    async def find_conversation(self, conversation_id: str) -> ChatConversationRecord | None:
        row = await self.db.fetch_one("SELECT * FROM chat_conversations WHERE id = ?", [conversation_id])
        return conversation_from_row(row) if row else None

    async def list_admin_conversations(
        self,
        status: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[tuple[ChatConversationRecord, str | None, str | None, int, ChatMessageRecord | None]]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("c.status = ?")
            params.append(status)
        if query:
            clauses.append("(lower(u.email) LIKE ? OR lower(COALESCE(u.display_name, '')) LIKE ? OR c.id LIKE ?)")
            needle = f"%{query.lower()}%"
            params.extend([needle, needle, f"%{query}%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(
            f"""
            SELECT c.*, u.email AS user_email, u.display_name AS user_display_name,
                (
                    SELECT COUNT(*) FROM chat_messages m
                    WHERE m.conversation_id = c.id
                    AND m.sender_role = 'user'
                    AND (c.admin_last_read_at IS NULL OR m.created_at > c.admin_last_read_at)
                ) AS unread_count,
                lm.id AS latest_message_id,
                lm.conversation_id AS latest_conversation_id,
                lm.sender_user_id AS latest_sender_user_id,
                lm.sender_role AS latest_sender_role,
                lm.body AS latest_body,
                lm.created_at AS latest_created_at,
                lm.message_type AS latest_message_type,
                lm.image_url AS latest_image_url,
                lm.image_public_id AS latest_image_public_id,
                lm.image_width AS latest_image_width,
                lm.image_height AS latest_image_height,
                lm.image_bytes AS latest_image_bytes,
                lm.image_format AS latest_image_format,
                lm.image_original_name AS latest_image_original_name
            FROM chat_conversations c
            LEFT JOIN users u ON u.id = c.user_id
            LEFT JOIN chat_messages lm ON lm.id = (
                SELECT id FROM chat_messages
                WHERE conversation_id = c.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            )
            {where}
            ORDER BY c.last_message_at DESC
            LIMIT ?
            """,
            params,
        )
        return [
            (
                conversation_from_row(row),
                str(row["user_email"]) if row.get("user_email") is not None else None,
                str(row["user_display_name"]) if row.get("user_display_name") is not None else None,
                int(row.get("unread_count") or 0),
                latest_message_from_row(row),
            )
            for row in rows
        ]

    async def list_messages(self, conversation_id: str, limit: int = 100, before: str | None = None) -> list[ChatMessageRecord]:
        params: list[object] = [conversation_id]
        before_clause = ""
        if before:
            before_clause = " AND created_at < ?"
            params.append(before)
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(
            f"""
            SELECT * FROM chat_messages
            WHERE conversation_id = ?{before_clause}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            params,
        )
        return [message_from_row(row) for row in rows]

    async def create_message(self, conversation_id: str, sender_user_id: str, sender_role: str, body: str) -> ChatMessageRecord:
        message_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO chat_messages (id, conversation_id, sender_user_id, sender_role, body, message_type)
            VALUES (?, ?, ?, ?, ?, 'text')
            """,
            [message_id, conversation_id, sender_user_id, sender_role, body],
        )
        return await self._after_message_created(conversation_id, message_id)

    async def create_image_message(
        self,
        conversation_id: str,
        sender_user_id: str,
        sender_role: str,
        caption: str,
        image_url: str,
        image_public_id: str,
        image_width: int | None,
        image_height: int | None,
        image_bytes: int | None,
        image_format: str | None,
        image_original_name: str | None,
    ) -> ChatMessageRecord:
        message_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO chat_messages (
                id, conversation_id, sender_user_id, sender_role, body, message_type,
                image_url, image_public_id, image_width, image_height, image_bytes, image_format, image_original_name
            )
            VALUES (?, ?, ?, ?, ?, 'image', ?, ?, ?, ?, ?, ?, ?)
            """,
            [message_id, conversation_id, sender_user_id, sender_role, caption, image_url, image_public_id, image_width, image_height, image_bytes, image_format, image_original_name],
        )
        return await self._after_message_created(conversation_id, message_id)

    async def _after_message_created(self, conversation_id: str, message_id: str) -> ChatMessageRecord:
        await self.db.execute(
            "UPDATE chat_conversations SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [conversation_id],
        )
        message = await self.find_message(message_id)
        if message is None:
            raise RuntimeError("Không thể gửi tin nhắn.")
        return message

    async def find_message(self, message_id: str) -> ChatMessageRecord | None:
        row = await self.db.fetch_one("SELECT * FROM chat_messages WHERE id = ?", [message_id])
        return message_from_row(row) if row else None

    async def mark_read_for_user(self, conversation_id: str, user_id: str) -> ChatConversationRecord | None:
        await self.db.execute(
            "UPDATE chat_conversations SET user_last_read_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            [conversation_id, user_id],
        )
        return await self.find_conversation(conversation_id)

    async def mark_read_for_admin(self, conversation_id: str) -> ChatConversationRecord | None:
        await self.db.execute(
            "UPDATE chat_conversations SET admin_last_read_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [conversation_id],
        )
        return await self.find_conversation(conversation_id)

    async def assign_admin_if_empty(self, conversation_id: str, admin_id: str) -> ChatConversationRecord | None:
        await self.db.execute(
            "UPDATE chat_conversations SET assigned_admin_id = COALESCE(assigned_admin_id, ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [admin_id, conversation_id],
        )
        return await self.find_conversation(conversation_id)

    async def close_conversation(self, conversation_id: str, admin_id: str) -> ChatConversationRecord | None:
        await self.db.execute(
            """
            UPDATE chat_conversations
            SET status = 'closed', assigned_admin_id = COALESCE(assigned_admin_id, ?), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [admin_id, conversation_id],
        )
        return await self.find_conversation(conversation_id)


def conversation_from_row(row: DbRow) -> ChatConversationRecord:
    return ChatConversationRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        status=str(row["status"]),
        assigned_admin_id=str(row["assigned_admin_id"]) if row.get("assigned_admin_id") is not None else None,
        last_message_at=str(row["last_message_at"]),
        user_last_read_at=str(row["user_last_read_at"]) if row.get("user_last_read_at") is not None else None,
        admin_last_read_at=str(row["admin_last_read_at"]) if row.get("admin_last_read_at") is not None else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def message_from_row(row: DbRow) -> ChatMessageRecord:
    return ChatMessageRecord(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        sender_user_id=str(row["sender_user_id"]),
        sender_role=str(row["sender_role"]),
        body=str(row["body"] or ""),
        created_at=str(row["created_at"]),
        message_type=str(row.get("message_type") or "text"),
        image_url=str(row["image_url"]) if row.get("image_url") is not None else None,
        image_public_id=str(row["image_public_id"]) if row.get("image_public_id") is not None else None,
        image_width=int(row["image_width"]) if row.get("image_width") is not None else None,
        image_height=int(row["image_height"]) if row.get("image_height") is not None else None,
        image_bytes=int(row["image_bytes"]) if row.get("image_bytes") is not None else None,
        image_format=str(row["image_format"]) if row.get("image_format") is not None else None,
        image_original_name=str(row["image_original_name"]) if row.get("image_original_name") is not None else None,
    )


def latest_message_from_row(row: DbRow) -> ChatMessageRecord | None:
    if row.get("latest_message_id") is None:
        return None
    return ChatMessageRecord(
        id=str(row["latest_message_id"]),
        conversation_id=str(row["latest_conversation_id"]),
        sender_user_id=str(row["latest_sender_user_id"]),
        sender_role=str(row["latest_sender_role"]),
        body=str(row["latest_body"] or ""),
        created_at=str(row["latest_created_at"]),
        message_type=str(row.get("latest_message_type") or "text"),
        image_url=str(row["latest_image_url"]) if row.get("latest_image_url") is not None else None,
        image_public_id=str(row["latest_image_public_id"]) if row.get("latest_image_public_id") is not None else None,
        image_width=int(row["latest_image_width"]) if row.get("latest_image_width") is not None else None,
        image_height=int(row["latest_image_height"]) if row.get("latest_image_height") is not None else None,
        image_bytes=int(row["latest_image_bytes"]) if row.get("latest_image_bytes") is not None else None,
        image_format=str(row["latest_image_format"]) if row.get("latest_image_format") is not None else None,
        image_original_name=str(row["latest_image_original_name"]) if row.get("latest_image_original_name") is not None else None,
    )
