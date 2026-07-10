from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median

from app.db.session import DatabaseClient
from app.repositories.errors import ErrorEventRepository
from app.services.analytics_taxonomy import (
    ALGEBRA_COMPLETED,
    ALGEBRA_FAILED,
    ANALYZE_COMPLETED,
    ANALYZE_FAILED,
    EXPORT_COMPLETED,
    OCR_COMPLETED,
    OCR_FAILED,
    RENDER_COMPLETED,
    RENDER_FAILED,
    SOLVE_COMPLETED,
    SOLVE_FAILED,
)


COMPLETED_OUTCOMES = (
    RENDER_COMPLETED,
    OCR_COMPLETED,
    ALGEBRA_COMPLETED,
    SOLVE_COMPLETED,
    ANALYZE_COMPLETED,
    EXPORT_COMPLETED,
)
FAILED_OUTCOMES = (RENDER_FAILED, OCR_FAILED, ALGEBRA_FAILED, SOLVE_FAILED, ANALYZE_FAILED)
OUTCOME_FEATURES = ("render", "ocr", "algebra", "solve", "analyze", "export")


class AnalyticsRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db
        self.error_events = ErrorEventRepository(db)

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
        errors_24h = await self.error_events.count_since(today)
        errors_period = await self.error_events.count_since(since)
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
                {"day": str(row["day"]), "count": int(row["count"] or 0)} for row in await self.error_events.daily_counts(since)
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

    async def product_usage(self, days: int = 14) -> dict:
        now = datetime.now(UTC)
        current_start = now - timedelta(days=max(1, days))
        previous_start = current_start - timedelta(days=max(1, days))
        since = current_start.strftime("%Y-%m-%d %H:%M:%S")

        feature_rows = await self.db.fetch_all(
            """
            SELECT COALESCE(target_id, 'unknown') AS feature,
                   COUNT(*) AS opens,
                   COUNT(DISTINCT user_id) AS unique_users,
                   COUNT(DISTINCT COALESCE(session_id, user_id || ':' || substr(created_at, 1, 10))) AS sessions
            FROM user_activity_events
            WHERE created_at >= ? AND event_type = 'feature.open'
            GROUP BY COALESCE(target_id, 'unknown')
            ORDER BY unique_users DESC, opens DESC
            LIMIT 30
            """,
            [since],
        )
        total_opens = sum(int(row["opens"] or 0) for row in feature_rows)
        feature_usage = [
            {
                "feature": str(row["feature"]),
                "opens": int(row["opens"] or 0),
                "unique_users": int(row["unique_users"] or 0),
                "sessions": int(row["sessions"] or 0),
                "share_pct": round((int(row["opens"] or 0) / total_opens) * 100, 1) if total_opens else 0.0,
            }
            for row in feature_rows
        ]

        outcome_events = {
            "render": (RENDER_COMPLETED, RENDER_FAILED),
            "ocr": (OCR_COMPLETED, OCR_FAILED),
            "algebra": (ALGEBRA_COMPLETED, ALGEBRA_FAILED),
            "solve": (SOLVE_COMPLETED, SOLVE_FAILED),
            "analyze": (ANALYZE_COMPLETED, ANALYZE_FAILED),
            "export": (EXPORT_COMPLETED,),
        }
        case_parts: list[str] = []
        case_params: list[str] = []
        for feature, event_types in outcome_events.items():
            case_parts.append(f"WHEN event_type IN ({', '.join('?' for _ in event_types)}) THEN ?")
            case_params.extend([*event_types, feature])
        all_outcomes = (*COMPLETED_OUTCOMES, *FAILED_OUTCOMES)
        all_placeholders = ", ".join("?" for _ in all_outcomes)
        completed_placeholders = ", ".join("?" for _ in COMPLETED_OUTCOMES)
        failed_placeholders = ", ".join("?" for _ in FAILED_OUTCOMES)
        outcome_rows = await self.db.fetch_all(
            f"""
            SELECT CASE {' '.join(case_parts)} END AS feature,
                   SUM(CASE WHEN event_type IN ({completed_placeholders}) THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN event_type IN ({failed_placeholders}) THEN 1 ELSE 0 END) AS failed,
                   COUNT(DISTINCT user_id) AS unique_users
            FROM user_activity_events
            WHERE created_at >= ? AND event_type IN ({all_placeholders})
            GROUP BY feature
            """,
            [*case_params, *COMPLETED_OUTCOMES, *FAILED_OUTCOMES, since, *all_outcomes],
        )
        outcome_by_feature = {str(row["feature"]): row for row in outcome_rows}
        outcomes = []
        for feature in OUTCOME_FEATURES:
            row = outcome_by_feature.get(feature, {})
            completed = int(row.get("completed") or 0)
            failed = int(row.get("failed") or 0)
            terminal = completed + failed
            outcomes.append(
                {
                    "feature": feature,
                    "completed": completed,
                    "failed": failed,
                    "unique_users": int(row.get("unique_users") or 0),
                    "success_rate": round((completed / terminal) * 100, 1) if terminal else None,
                }
            )

        daily_placeholders = ", ".join("?" for _ in COMPLETED_OUTCOMES)
        daily_rows = await self.db.fetch_all(
            f"""
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(DISTINCT user_id) AS unique_users,
                   COUNT(*) AS events,
                   SUM(CASE WHEN event_type IN ({daily_placeholders}) THEN 1 ELSE 0 END) AS completed
            FROM user_activity_events
            WHERE created_at >= ?
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day ASC
            """,
            [*COMPLETED_OUTCOMES, since],
        )
        current_metrics = await self._period_metrics(current_start, now + timedelta(seconds=1))
        previous_metrics = await self._period_metrics(previous_start, current_start)
        comparison = {
            key: {
                "current": current_metrics[key],
                "previous": previous_metrics[key],
                "change_pct": _change_pct(current_metrics[key], previous_metrics[key]),
            }
            for key in ("active_users", "feature_opens", "completed_outcomes", "errors")
        }
        return {
            "days": days,
            "sample_scope": "authenticated_users",
            "feature_usage": feature_usage,
            "outcomes": outcomes,
            "daily_active_users": [
                {
                    "day": str(row["day"]),
                    "unique_users": int(row["unique_users"] or 0),
                    "events": int(row["events"] or 0),
                    "completed": int(row["completed"] or 0),
                }
                for row in daily_rows
            ],
            "period_comparison": comparison,
        }

    async def _period_metrics(self, start: datetime, end: datetime) -> dict[str, int]:
        start_value = start.strftime("%Y-%m-%d %H:%M:%S")
        end_value = end.strftime("%Y-%m-%d %H:%M:%S")
        completed_placeholders = ", ".join("?" for _ in COMPLETED_OUTCOMES)
        activity = await self.db.fetch_one(
            f"""
            SELECT COUNT(DISTINCT user_id) AS active_users,
                   SUM(CASE WHEN event_type = 'feature.open' THEN 1 ELSE 0 END) AS feature_opens,
                   SUM(CASE WHEN event_type IN ({completed_placeholders}) THEN 1 ELSE 0 END) AS completed_outcomes
            FROM user_activity_events
            WHERE created_at >= ? AND created_at < ?
            """,
            [*COMPLETED_OUTCOMES, start_value, end_value],
        )
        errors = await self.db.fetch_one(
            "SELECT COUNT(*) AS count FROM error_events WHERE created_at >= ? AND created_at < ?",
            [start_value, end_value],
        )
        return {
            "active_users": int((activity or {}).get("active_users") or 0),
            "feature_opens": int((activity or {}).get("feature_opens") or 0),
            "completed_outcomes": int((activity or {}).get("completed_outcomes") or 0),
            "errors": int((errors or {}).get("count") or 0),
        }

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
            SELECT COALESCE(provider, 'unknown') AS provider,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   AVG(CASE WHEN status = 'completed' THEN duration_ms END) AS avg_ms
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(provider, 'unknown')
            ORDER BY count DESC
            LIMIT 20
            """,
            [since],
        )
        by_renderer = await self.db.fetch_all(
            """
            SELECT COALESCE(renderer, 'unknown') AS renderer,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   AVG(CASE WHEN status = 'completed' THEN duration_ms END) AS avg_ms
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(renderer, 'unknown')
            ORDER BY count DESC
            LIMIT 20
            """,
            [since],
        )
        by_source = await self.db.fetch_all(
            """
            SELECT COALESCE(source_type, 'unknown') AS source,
                   COUNT(*) AS count,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM render_jobs
            WHERE created_at >= ?
            GROUP BY COALESCE(source_type, 'unknown')
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
            "by_provider": [_quality_breakdown(r, "provider") for r in by_provider],
            "by_renderer": [_quality_breakdown(r, "renderer") for r in by_renderer],
            "by_source": [_quality_breakdown(r, "source", include_latency=False) for r in by_source],
            "by_model": [{"key": str(r["model"]), "count": int(r["count"] or 0)} for r in by_model],
            "duration_p50_ms": overview["duration_p50_ms"],
            "duration_p95_ms": overview["duration_p95_ms"],
            "duration_avg_ms": overview["duration_avg_ms"],
            "fail_rate": overview["render_fail_rate"],
            "daily": overview["daily_renders"],
        }

    async def errors(self, days: int = 14, limit: int = 50) -> dict:
        since = self._since(days)
        recent = await self.error_events.list_recent(limit=limit, since=since)
        top = await self.error_events.top_codes(since)
        by_route = await self.db.fetch_all(
            """
            SELECT COALESCE(route, 'unknown') AS key, COUNT(*) AS count
            FROM error_events WHERE created_at >= ?
            GROUP BY COALESCE(route, 'unknown') ORDER BY count DESC LIMIT 20
            """,
            [since],
        )
        by_source = await self.db.fetch_all(
            """
            SELECT COALESCE(source, 'unknown') AS key, COUNT(*) AS count
            FROM error_events WHERE created_at >= ?
            GROUP BY COALESCE(source, 'unknown') ORDER BY count DESC LIMIT 20
            """,
            [since],
        )
        by_status = await self.db.fetch_all(
            """
            SELECT COALESCE(CAST(status_code AS TEXT), 'unknown') AS key, COUNT(*) AS count
            FROM error_events WHERE created_at >= ?
            GROUP BY COALESCE(CAST(status_code AS TEXT), 'unknown') ORDER BY count DESC LIMIT 20
            """,
            [since],
        )
        affected = await self.db.fetch_one(
            "SELECT COUNT(DISTINCT user_id) AS count FROM error_events WHERE created_at >= ? AND user_id IS NOT NULL",
            [since],
        )
        return {
            "days": days,
            "affected_users": int((affected or {}).get("count") or 0),
            "top_codes": [{"error_code": str(r["error_code"]), "count": int(r["count"] or 0)} for r in top],
            "by_route": _key_counts(by_route),
            "by_source": _key_counts(by_source),
            "by_status": _key_counts(by_status),
            "top_fingerprints": await self.error_groups(days, 10),
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
                {"day": str(row["day"]), "count": int(row["count"] or 0)} for row in await self.error_events.daily_counts(since)
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
        feature_opens = await self.db.fetch_all(
            """
            SELECT COALESCE(target_id, 'unknown') AS feature, COUNT(*) AS count
            FROM user_activity_events
            WHERE created_at >= ? AND event_type = 'feature.open'
            GROUP BY COALESCE(target_id, 'unknown')
            ORDER BY count DESC
            LIMIT 20
            """,
            [since],
        )
        return {
            "days": days,
            "registered": int((registered or {}).get("count") or 0),
            "verified": int((verified or {}).get("count") or 0),
            "users_with_completed_render": int((first_render or {}).get("count") or 0),
            "users_with_ocr": int((ocr_users or {}).get("count") or 0),
            "feature_opens": [{"feature": str(r["feature"]), "count": int(r["count"] or 0)} for r in feature_opens],
        }

    async def error_groups(self, days: int = 14, limit: int = 30) -> list[dict]:
        since = self._since(days)
        rows = await self.db.fetch_all(
            """
            SELECT COALESCE(stack_fingerprint, 'unknown') AS fingerprint,
                   COALESCE(error_code, 'UNKNOWN') AS error_code,
                   COUNT(*) AS count,
                   MIN(created_at) AS first_seen,
                   MAX(created_at) AS last_seen,
                   MAX(message) AS sample_message
            FROM error_events
            WHERE created_at >= ?
            GROUP BY COALESCE(stack_fingerprint, 'unknown'), COALESCE(error_code, 'UNKNOWN')
            ORDER BY count DESC
            LIMIT ?
            """,
            [since, min(max(limit, 1), 100)],
        )
        return [
            {
                "fingerprint": str(r["fingerprint"]),
                "error_code": str(r["error_code"]),
                "count": int(r["count"] or 0),
                "first_seen": str(r.get("first_seen") or ""),
                "last_seen": str(r.get("last_seen") or ""),
                "sample_message": str(r.get("sample_message") or "")[:300],
            }
            for r in rows
        ]

    async def ai_usage(self, days: int = 14) -> dict:
        from app.repositories.ai_metrics import AiCallMetricsRepository

        since = self._since(days)
        try:
            summary = await AiCallMetricsRepository(self.db).summary(since)
        except Exception:
            summary = {
                "by_provider": [],
                "by_task": [],
                "by_model": [],
                "calls": 0,
                "ok": 0,
                "failed": 0,
                "success_rate": None,
                "tokens": 0,
                "avg_ms": None,
            }
        summary["days"] = days
        return summary

    async def user_timeline(self, user_id: str, limit: int = 100) -> list[dict]:
        limit = min(max(limit, 1), 200)
        activity = await self.db.fetch_all(
            """
            SELECT id, event_type AS kind, created_at, metadata_json, target_type, target_id, 'activity' AS source
            FROM user_activity_events
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [user_id, limit],
        )
        errors = await self.db.fetch_all(
            """
            SELECT id, COALESCE(error_code, 'ERROR') AS kind, created_at, message AS metadata_json,
                   route AS target_type, request_id AS target_id, 'error' AS source
            FROM error_events
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [user_id, limit],
        )
        merged = [
            {
                "id": str(r["id"]),
                "source": str(r["source"]),
                "kind": str(r["kind"]),
                "created_at": str(r["created_at"]),
                "target_type": r.get("target_type"),
                "target_id": r.get("target_id"),
                "detail": str(r.get("metadata_json") or "")[:500],
            }
            for r in [*activity, *errors]
        ]
        merged.sort(key=lambda item: item["created_at"], reverse=True)
        return merged[:limit]


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return int(ordered[index])


def _change_pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return 0.0 if current == 0 else None
    return round(((current - previous) / previous) * 100, 1)


def _key_counts(rows: list[dict]) -> list[dict]:
    return [{"key": str(row["key"]), "count": int(row["count"] or 0)} for row in rows]


def _quality_breakdown(row: dict, key: str, *, include_latency: bool = True) -> dict:
    completed = int(row.get("completed") or 0)
    failed = int(row.get("failed") or 0)
    terminal = completed + failed
    result = {
        "key": str(row[key]),
        "count": int(row.get("count") or 0),
        "completed": completed,
        "failed": failed,
        "fail_rate": round((failed / terminal) * 100, 1) if terminal else None,
    }
    if include_latency:
        result["avg_ms"] = int(row["avg_ms"] or 0) if row.get("avg_ms") is not None else None
    return result
