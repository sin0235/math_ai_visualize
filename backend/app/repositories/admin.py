import json
from uuid import uuid4

from app.db.models import AuditLogRecord, DbRow, RenderJobRecord, SystemSettingsRecord, UserRecord
from app.db.session import DatabaseClient
from app.repositories.auth import user_from_row
from app.repositories.history import render_job_from_row


class AdminRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def summary(self) -> dict[str, int]:
        users = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users")
        active_users = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE status = 'active'")
        admins = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
        renders = await self.db.fetch_one("SELECT COUNT(*) AS count FROM render_jobs")
        return {
            "users": int((users or {}).get("count") or 0),
            "active_users": int((active_users or {}).get("count") or 0),
            "admins": int((admins or {}).get("count") or 0),
            "render_jobs": int((renders or {}).get("count") or 0),
        }

    async def list_users(self, query: str | None = None, limit: int = 100) -> list[UserRecord]:
        if query:
            rows = await self.db.fetch_all(
                "SELECT * FROM users WHERE lower(email) LIKE ? OR lower(COALESCE(display_name, '')) LIKE ? ORDER BY created_at DESC LIMIT ?",
                [f"%{query.lower()}%", f"%{query.lower()}%", limit],
            )
        else:
            rows = await self.db.fetch_all("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", [limit])
        return [user_from_row(row) for row in rows]

    async def update_user(self, user_id: str, *, role: str | None, status: str | None, display_name: str | None, plan: str | None) -> UserRecord | None:
        current = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if current is None:
            return None
        await self.db.execute(
            """
            UPDATE users
            SET role = COALESCE(?, role),
                status = COALESCE(?, status),
                display_name = ?,
                plan = COALESCE(?, plan),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [role, status, display_name, plan, user_id],
        )
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        return user_from_row(row) if row else None

    async def list_render_jobs(self, limit: int = 100) -> list[RenderJobRecord]:
        rows = await self.db.fetch_all("SELECT * FROM render_jobs ORDER BY created_at DESC LIMIT ?", [limit])
        return [render_job_from_row(row) for row in rows]

    async def find_render_job(self, job_id: str) -> RenderJobRecord | None:
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        return render_job_from_row(row) if row else None

    async def delete_render_job(self, job_id: str) -> None:
        await self.db.execute("DELETE FROM render_jobs WHERE id = ?", [job_id])

    async def list_system_settings(self) -> list[SystemSettingsRecord]:
        rows = await self.db.fetch_all("SELECT * FROM system_settings ORDER BY key ASC")
        return [system_settings_from_row(row) for row in rows]

    async def upsert_system_setting(self, key: str, value: dict, updated_by: str) -> SystemSettingsRecord:
        value_json = json.dumps(value, ensure_ascii=False)
        await self.db.execute(
            """
            INSERT INTO system_settings (key, value_json, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP
            """,
            [key, value_json, updated_by],
        )
        row = await self.db.fetch_one("SELECT * FROM system_settings WHERE key = ?", [key])
        if row is None:
            raise RuntimeError("Không thể lưu cấu hình hệ thống.")
        return system_settings_from_row(row)

    async def audit(self, actor_user_id: str | None, action: str, target_type: str, target_id: str | None = None, metadata: dict | None = None) -> AuditLogRecord:
        log_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO audit_logs (id, actor_user_id, action, target_type, target_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [log_id, actor_user_id, action, target_type, target_id, json.dumps(metadata or {}, ensure_ascii=False)],
        )
        row = await self.db.fetch_one("SELECT * FROM audit_logs WHERE id = ?", [log_id])
        if row is None:
            raise RuntimeError("Không thể ghi audit log.")
        return audit_log_from_row(row)

    async def list_audit_logs(self, limit: int = 100) -> list[AuditLogRecord]:
        rows = await self.db.fetch_all("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", [limit])
        return [audit_log_from_row(row) for row in rows]


def system_settings_from_row(row: DbRow) -> SystemSettingsRecord:
    return SystemSettingsRecord(
        key=str(row["key"]),
        value_json=str(row["value_json"]),
        updated_by=str(row["updated_by"]) if row.get("updated_by") is not None else None,
        updated_at=str(row["updated_at"]),
    )


def audit_log_from_row(row: DbRow) -> AuditLogRecord:
    return AuditLogRecord(
        id=str(row["id"]),
        actor_user_id=str(row["actor_user_id"]) if row.get("actor_user_id") is not None else None,
        action=str(row["action"]),
        target_type=str(row["target_type"]),
        target_id=str(row["target_id"]) if row.get("target_id") is not None else None,
        metadata_json=str(row["metadata_json"]),
        created_at=str(row["created_at"]),
    )
