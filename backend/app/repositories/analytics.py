from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median

from app.db.session import DatabaseClient
from app.repositories.errors import ErrorEventRepository


class AnalyticsRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db
        self.errors = ErrorEventRepository(db)

    def _since(self, days: int) -> str:
        return (datetime.now(UTC) - timedelta(days=max(1, days))).strftime("%Y-%m-%d %H:%M:%S")

    async def overview(self, days: int = 14) -> dict:
        since = self._since(days)
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        renders = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ?",
            [since],
        )
        completed = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ? AND status = 'completed'",
            [since],
        )
        failed = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ? AND status = 'failed'",
            [since],
        )
        renders_today = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ?",
            [today],
        )
        errors_24h = await self.errors.count_since(today)
        errors_period = await self.errors.count_since(since)
        dau = await self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT user_id) AS count
            FROM user_activity_events
            WHERE created_at >= ?
            """,
            [today],
        )
        activity = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM user_activity_events WHERE created_at >= ?",
            [since],
        )
        durations = await self.db.fetch_all(
            """
            SELECT duration_ms FROM render_jobs
            WHERE created_at >= ? AND duration_ms IS NOT NULL AND status = 'completed'
            ORDER BY duration_ms ASC
            """,
            [since],
        )
        duration_values = [int(row["duration_ms"]) for row in durations if row.get("duration_ms") is not None]
        completed_n = int((completed or {}).get("count") or 0)
        failed_n = int((failed or {}).get("count") or 0)
        total_terminal = completed_n + failed_n
        return {
            "days": days,
            "renders": int((renders or {}).get("count") or 0),
            "renders_today": int((renders_today or {}).get("count") or 0),
            "renders_completed": completed_n,
            "renders_failed": failed_n,
            "render_fail_rate": round((failed_n / total_terminal) * 100, 1) if total_terminal else 0.0,
            "errors_24h": errors_24h,
            "errors_period": errors_period,
            "dau": int((dau or {}).get("count") or 0),
            "activity_events": int((activity or {}).get("count") or 0),
            "duration_p50_ms": int(median(duration_values)) if duration_values else None,
            "duration_avg_ms": int(sum(duration_values) / len(duration_values)) if duration_values else None,
            "duration_p95_ms": _percentile(duration_values, 0.95),
            "daily_renders": await self._daily_renders(since),
            "daily_errors": [
                {"day": str(row["day"]), "count": int(row["count"] or 0)} for row in await self.errors.daily_counts(since)
            ],
        }

    async def _daily_renders(self, since: str) -> list[dict]:
        rows = await self.db.fetch_all(
            """
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            [since],
        )
        return [{"day": str(row["day"]), "count": int(row["count"] or 0)} for row in rows]

    async def renders(self, days: int = 14) -> dict:
        since = self._since(days)
        by_status = await self.db.fetch_all(
            """
            SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(status, 'unknown')
            ORDER BY count DESC
            """,
            [since],
        )
        by_provider = await self.db.fetch_all(
            """
            SELECT COALESCE(provider, 'unknown') AS provider, COUNT(*) AS count
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(provider, 'unknown')
            ORDER BY count DESC
            LIMIT 20
            """,
            [since],
        )
        by_model = await self.db.fetch_all(
            """
            SELECT COALESCE(model, 'unknown') AS model, COUNT(*) AS count
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(model, 'unknown')
            ORDER BY count DESC
            LIMIT 20
            """,
            [since],
        )
        overview = await self.overview(days)
        return {
            "days": days,
            "by_status": [{"key": str(r["status"]), "count": int(r["count"] or 0)} for r in by_status],
            "by_provider": [{"key": str(r["provider"]), "count": int(r["count"] or 0)} for r in by_provider],
            "by_model": [{"key": str(r["model"]), "count": int(r["count"] or 0)} for r in by_model],
            "duration_p50_ms": overview["duration_p50_ms"],
            "duration_p95_ms": overview["duration_p95_ms"],
            "duration_avg_ms": overview["duration_avg_ms"],
            "fail_rate": overview["render_fail_rate"],
            "daily": overview["daily_renders"],
        }

    async def errors(self, days: int = 14, limit: int = 50) -> dict:
        since = self._since(days)
        recent = await self.errors.list_recent(limit=limit, since=since)
        top = await self.errors.top_codes(since)
        return {
            "days": days,
            "top_codes": [{"error_code": str(r["error_code"]), "count": int(r["count"] or 0)} for r in top],
            "recent": [
                {
                    "id": str(r["id"]),
                    "request_id": r.get("request_id"),
                    "user_id": r.get("user_id"),
                    "source": str(r.get("source") or "server"),
                    "route": r.get("route"),
                    "method": r.get("method"),
                    "status_code": r.get("status_code"),
                    "error_code": r.get("error_code"),
                    "message": str(r.get("message") or ""),
                    "stack_fingerprint": r.get("stack_fingerprint"),
                    "created_at": str(r.get("created_at") or ""),
                }
                for r in recent
            ],
            "daily": [
                {"day": str(row["day"]), "count": int(row["count"] or 0)} for row in await self.errors.daily_counts(since)
            ],
        }

    async def activity(
        self,
        days: int = 7,
        limit: int = 50,
        event_type: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        since = self._since(days)
        clauses = ["created_at >= ?"]
        params: list[object] = [since]
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        params.append(min(max(limit, 1), 200))
        rows = await self.db.fetch_all(
            f"""
            SELECT id, user_id, session_id, event_type, target_type, target_id, source, metadata_json, created_at
            FROM user_activity_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        )
        by_type = await self.db.fetch_all(
            """
            SELECT event_type, COUNT(*) AS count
            FROM user_activity_events
            WHERE created_at >= ?
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 30
            """,
            [since],
        )
        return {
            "days": days,
            "by_type": [{"event_type": str(r["event_type"]), "count": int(r["count"] or 0)} for r in by_type],
            "recent": [
                {
                    "id": str(r["id"]),
                    "user_id": str(r["user_id"]),
                    "session_id": r.get("session_id"),
                    "event_type": str(r["event_type"]),
                    "target_type": r.get("target_type"),
                    "target_id": r.get("target_id"),
                    "source": str(r.get("source") or "server"),
                    "metadata_json": str(r.get("metadata_json") or "{}"),
                    "created_at": str(r["created_at"]),
                }
                for r in rows
            ],
        }

    async def funnel(self, days: int = 30) -> dict:
        since = self._since(days)
        registered = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM users WHERE created_at >= ?",
            [since],
        )
        verified = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM users WHERE created_at >= ? AND email_verified_at IS NOT NULL",
            [since],
        )
        first_render = await self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT user_id) AS count
            FROM render_jobs
            WHERE created_at >= ? AND status = 'completed' AND user_id IS NOT NULL
            """,
            [since],
        )
        ocr_users = await self.db.fetch_one(
            """
            SELECT COUNT(DISTINCT user_id) AS count
            FROM usage_events
            WHERE created_at >= ? AND event_type = 'ocr'
            """,
            [since],
        )
        return {
            "days": days,
            "registered": int((registered or {}).get("count") or 0),
            "verified": int((verified or {}).get("count") or 0),
            "users_with_completed_render": int((first_render or {}).get("count") or 0),
            "users_with_ocr": int((ocr_users or {}).get("count") or 0),
        }


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return int(ordered[index])
