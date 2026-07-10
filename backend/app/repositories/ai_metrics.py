from __future__ import annotations

import json
import logging
from uuid import uuid4

from app.core.logging import get_request_id
from app.db.session import DatabaseClient
from app.repositories.activity import safe_activity_metadata

logger = logging.getLogger(__name__)


class AiCallMetricsRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        *,
        task: str,
        provider: str | None = None,
        model: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        success: bool = True,
        error_code: str | None = None,
        elapsed_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        metadata: dict | None = None,
    ) -> str:
        event_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO ai_call_metrics (
              id, user_id, request_id, task, provider, model, success, error_code,
              elapsed_ms, prompt_tokens, completion_tokens, total_tokens, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_id,
                user_id,
                request_id or get_request_id(),
                task[:64],
                provider,
                model,
                1 if success else 0,
                error_code,
                elapsed_ms,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                json.dumps(safe_activity_metadata(metadata or {}), ensure_ascii=False),
            ],
        )
        return event_id

    async def summary(self, since: str) -> dict:
        by_provider = await self.db.fetch_all(
            """
            SELECT COALESCE(provider, 'unknown') AS provider,
                   COUNT(*) AS calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                   SUM(COALESCE(total_tokens, 0)) AS tokens,
                   AVG(elapsed_ms) AS avg_ms
            FROM ai_call_metrics
            WHERE created_at >= ?
            GROUP BY COALESCE(provider, 'unknown')
            ORDER BY calls DESC
            LIMIT 20
            """,
            [since],
        )
        by_task = await self.db.fetch_all(
            """
            SELECT COALESCE(task, 'unknown') AS task,
                   COUNT(*) AS calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                   SUM(COALESCE(total_tokens, 0)) AS tokens,
                   AVG(elapsed_ms) AS avg_ms
            FROM ai_call_metrics
            WHERE created_at >= ?
            GROUP BY COALESCE(task, 'unknown')
            ORDER BY calls DESC
            LIMIT 20
            """,
            [since],
        )
        by_model = await self.db.fetch_all(
            """
            SELECT COALESCE(provider, 'unknown') AS provider,
                   COALESCE(model, 'unknown') AS model,
                   COUNT(*) AS calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                   SUM(COALESCE(total_tokens, 0)) AS tokens,
                   AVG(elapsed_ms) AS avg_ms
            FROM ai_call_metrics
            WHERE created_at >= ?
            GROUP BY COALESCE(provider, 'unknown'), COALESCE(model, 'unknown')
            ORDER BY calls DESC
            LIMIT 30
            """,
            [since],
        )
        totals = await self.db.fetch_one(
            """
            SELECT COUNT(*) AS calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS ok,
                   SUM(COALESCE(total_tokens, 0)) AS tokens,
                   AVG(elapsed_ms) AS avg_ms
            FROM ai_call_metrics
            WHERE created_at >= ?
            """,
            [since],
        )
        total_calls = int((totals or {}).get("calls") or 0)
        total_ok = int((totals or {}).get("ok") or 0)
        return {
            "by_provider": [_metric_breakdown(r, "provider") for r in by_provider],
            "by_task": [_metric_breakdown(r, "task") for r in by_task],
            "by_model": [
                {
                    **_metric_breakdown(r, "model"),
                    "provider": str(r["provider"]),
                }
                for r in by_model
            ],
            "calls": total_calls,
            "ok": total_ok,
            "failed": total_calls - total_ok,
            "success_rate": round((total_ok / total_calls) * 100, 1) if total_calls else None,
            "tokens": int((totals or {}).get("tokens") or 0),
            "avg_ms": int((totals or {}).get("avg_ms") or 0) if (totals or {}).get("avg_ms") is not None else None,
        }


def _metric_breakdown(row: dict, key: str) -> dict:
    calls = int(row.get("calls") or 0)
    ok = int(row.get("ok") or 0)
    return {
        key: str(row[key]),
        "calls": calls,
        "ok": ok,
        "failed": calls - ok,
        "success_rate": round((ok / calls) * 100, 1) if calls else None,
        "tokens": int(row.get("tokens") or 0),
        "avg_ms": int(row.get("avg_ms") or 0) if row.get("avg_ms") is not None else None,
    }


async def try_record_ai_call(db: DatabaseClient | None, **kwargs) -> None:
    if db is None:
        return
    try:
        await AiCallMetricsRepository(db).create(**kwargs)
    except Exception as error:
        logger.warning("Không thể lưu ai_call_metrics: %s", error)
