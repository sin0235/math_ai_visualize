import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models import AuditLogRecord, DbRow, PlanRecord, RenderJobRecord, SessionRecord, SystemSettingsRecord, UserRecord
from app.db.session import DatabaseClient
from app.repositories.auth import SessionRepository, session_from_row, user_from_row
from app.repositories.history import render_job_from_row


class AdminRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def summary(self) -> dict[str, int | float]:
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        stats_start = (datetime.now(UTC) - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        users = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users")
        active_users = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE status = 'active'")
        admins = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
        renders = await self.db.fetch_one("SELECT COUNT(*) AS count FROM render_jobs")
        renders_today = await self.db.fetch_one("SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ?", [today_start])
        users_today = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE created_at >= ?", [today_start])
        warning_jobs = await self.db.fetch_one("SELECT COUNT(*) AS count FROM render_jobs WHERE warnings_json IS NOT NULL AND warnings_json NOT IN ('[]', '')")
        render_count = int((renders or {}).get("count") or 0)
        warning_count = int((warning_jobs or {}).get("count") or 0)

        daily_stats_rows = await self.db.fetch_all(
            """
            SELECT substr(created_at, 1, 10) as day, COUNT(*) as count
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            [stats_start],
        )
        daily_stats = [{"day": row["day"], "count": row["count"]} for row in daily_stats_rows]

        return {
            "users": int((users or {}).get("count") or 0),
            "active_users": int((active_users or {}).get("count") or 0),
            "admins": int((admins or {}).get("count") or 0),
            "render_jobs": render_count,
            "render_jobs_today": int((renders_today or {}).get("count") or 0),
            "users_today": int((users_today or {}).get("count") or 0),
            "ai_warning_jobs": warning_count,
            "ai_warning_rate": round((warning_count / render_count) * 100, 1) if render_count else 0,
            "daily_stats": daily_stats,
        }

    async def list_users(
        self,
        query: str | None = None,
        role: str | None = None,
        status: str | None = None,
        plan: str | None = None,
        limit: int = 100,
    ) -> list[UserRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if query:
            clauses.append("(lower(email) LIKE ? OR lower(COALESCE(display_name, '')) LIKE ? OR id LIKE ?)")
            params.extend([f"%{query.lower()}%", f"%{query.lower()}%", f"%{query}%"])
        if role:
            clauses.append("role = ?")
            params.append(role)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if plan:
            clauses.append("plan = ?")
            params.append(plan)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(f"SELECT * FROM users{where} ORDER BY created_at DESC LIMIT ?", params)
        return [user_from_row(row) for row in rows]

    async def find_user(self, user_id: str) -> UserRecord | None:
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        return user_from_row(row) if row else None

    async def update_user(self, user_id: str, patch: dict[str, object]) -> UserRecord | None:
        current = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        if current is None:
            return None
        allowed_fields = ["role", "status", "display_name", "plan"]
        assignments = [f"{field} = ?" for field in allowed_fields if field in patch]
        if assignments:
            params = [patch[field] for field in allowed_fields if field in patch]
            params.append(user_id)
            await self.db.execute(
                f"UPDATE users SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                params,
            )
        row = await self.db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
        return user_from_row(row) if row else None

    async def count_active_admins(self) -> int:
        row = await self.db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND status = 'active'")
        return int((row or {}).get("count") or 0)

    async def list_render_jobs(
        self,
        provider: str | None = None,
        model: str | None = None,
        renderer: str | None = None,
        source_type: str | None = None,
        user_id: str | None = None,
        query: str | None = None,
        limit: int = 100,
    ) -> list[RenderJobRecord]:
        clauses: list[str] = []
        params: list[object] = []
        for column, value in (("provider", provider), ("model", model), ("renderer", renderer), ("source_type", source_type), ("user_id", user_id)):
            if value:
                clauses.append(f"r.{column} = ?")
                params.append(value)
        if query:
            clauses.append("(lower(r.problem_text) LIKE ? OR lower(COALESCE(h.title, '')) LIKE ? OR r.id LIKE ?)")
            params.extend([f"%{query.lower()}%", f"%{query.lower()}%", f"%{query}%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(
            f"""
            SELECT r.*, h.id AS history_item_id, h.title, h.problem_preview, h.topic, h.grade, h.tier, h.is_favorite,
                   h.archived_at, h.last_opened_at, h.updated_at AS history_updated_at
            FROM render_jobs r
            LEFT JOIN history_items h ON h.render_job_id = r.id
            {where}
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            params,
        )
        return [render_job_from_row(row) for row in rows]

    async def count_user_render_jobs_since(self, user_id: str, since_iso: str, source_type: str | None = None, ai_source: str | None = None) -> int:
        params: list[object] = [user_id, since_iso]
        clauses = ["user_id = ?", "created_at >= ?"]
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if ai_source:
            clauses.append("ai_source = ?")
            params.append(ai_source)
        row = await self.db.fetch_one(f"SELECT COUNT(*) AS count FROM render_jobs WHERE {' AND '.join(clauses)}", params)
        return int((row or {}).get("count") or 0)

    async def count_user_usage_events_since(self, user_id: str, event_type: str, since_iso: str) -> int:
        row = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM usage_events WHERE user_id = ? AND event_type = ? AND created_at >= ?",
            [user_id, event_type, since_iso],
        )
        return int((row or {}).get("count") or 0)

    async def count_user_usage_events_since_any(self, user_id: str, event_types: list[str], since_iso: str) -> int:
        if not event_types:
            return 0
        placeholders = ", ".join("?" for _ in event_types)
        row = await self.db.fetch_one(
            f"SELECT COUNT(*) AS count FROM usage_events WHERE user_id = ? AND event_type IN ({placeholders}) AND created_at >= ?",
            [user_id, *event_types, since_iso],
        )
        return int((row or {}).get("count") or 0)

    async def record_user_usage_event(self, user_id: str, event_type: str, metadata: dict | None = None) -> None:
        await self.db.execute(
            "INSERT INTO usage_events (id, user_id, event_type, metadata_json) VALUES (?, ?, ?, ?)",
            [str(uuid4()), user_id, event_type, json.dumps(metadata or {}, ensure_ascii=False)],
        )

    async def find_render_job(self, job_id: str) -> RenderJobRecord | None:
        row = await self.db.fetch_one(
            """
            SELECT r.*, h.id AS history_item_id, h.title, h.problem_preview, h.topic, h.grade, h.tier, h.is_favorite,
                   h.archived_at, h.last_opened_at, h.updated_at AS history_updated_at
            FROM render_jobs r
            LEFT JOIN history_items h ON h.render_job_id = r.id
            WHERE r.id = ?
            """,
            [job_id],
        )
        return render_job_from_row(row) if row else None

    async def delete_render_job(self, job_id: str) -> None:
        await self.db.execute("DELETE FROM render_jobs WHERE id = ?", [job_id])

    async def list_plans(self, active_only: bool = False) -> list[PlanRecord]:
        await self.ensure_default_plans()
        where = " WHERE is_active = 1" if active_only else ""
        rows = await self.db.fetch_all(f"SELECT * FROM plans{where} ORDER BY sort_order ASC, id ASC")
        return [plan_from_row(row) for row in rows]

    async def find_plan(self, plan_id: str) -> PlanRecord | None:
        await self.ensure_default_plans()
        row = await self.db.fetch_one("SELECT * FROM plans WHERE id = ?", [plan_id])
        return plan_from_row(row) if row else None

    async def ensure_default_plans(self) -> None:
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                daily_render_limit INTEGER CHECK(daily_render_limit IS NULL OR daily_render_limit >= 0),
                daily_ocr_limit INTEGER CHECK(daily_ocr_limit IS NULL OR daily_ocr_limit >= 0),
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for plan_id, name, render_limit, ocr_limit, sort_order in [("free", "Free", 20, 20, 10), ("pro", "Pro", 200, 200, 20), ("pro_plus", "Pro+", None, None, 30)]:
            await self.db.execute(
                """
                INSERT INTO plans (id, name, daily_render_limit, daily_ocr_limit, sort_order, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO NOTHING
                """,
                [plan_id, name, render_limit, ocr_limit, sort_order],
            )

    async def update_plan(self, plan_id: str, patch: dict[str, object]) -> PlanRecord | None:
        current = await self.db.fetch_one("SELECT * FROM plans WHERE id = ?", [plan_id])
        if current is None:
            return None
        allowed_fields = ["name", "daily_render_limit", "daily_ocr_limit", "sort_order", "is_active"]
        assignments = [f"{field} = ?" for field in allowed_fields if field in patch]
        if assignments:
            params = [int(patch[field]) if field == "is_active" else patch[field] for field in allowed_fields if field in patch]
            params.append(plan_id)
            await self.db.execute(
                f"UPDATE plans SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                params,
            )
        row = await self.db.fetch_one("SELECT * FROM plans WHERE id = ?", [plan_id])
        return plan_from_row(row) if row else None

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

    async def list_user_sessions(self, user_id: str) -> list[SessionRecord]:
        rows = await self.db.fetch_all(
            "SELECT * FROM sessions WHERE user_id = ? AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP ORDER BY last_seen_at DESC, created_at DESC",
            [user_id],
        )
        return [session_from_row(row) for row in rows]

    async def revoke_user_session(self, user_id: str, session_id: str) -> bool:
        return await SessionRepository(self.db).revoke_by_id(user_id, session_id)

    async def revoke_user_sessions(self, user_id: str) -> int:
        return await SessionRepository(self.db).revoke_all_for_user(user_id)

    async def list_audit_logs(
        self,
        action: str | None = None,
        actor_user_id: str | None = None,
        target_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditLogRecord]:
        clauses: list[str] = []
        params: list[object] = []
        for column, value in (("action", action), ("actor_user_id", actor_user_id), ("target_type", target_type)):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(f"SELECT * FROM audit_logs{where} ORDER BY created_at DESC LIMIT ?", params)
        return [audit_log_from_row(row) for row in rows]


def plan_from_row(row: DbRow) -> PlanRecord:
    return PlanRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        daily_render_limit=int(row["daily_render_limit"]) if row.get("daily_render_limit") is not None else None,
        daily_ocr_limit=int(row["daily_ocr_limit"]) if row.get("daily_ocr_limit") is not None else None,
        sort_order=int(row["sort_order"]),
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


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
