"""Lightweight alert checks + webhook fanout for analytics ops."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient

logger = logging.getLogger(__name__)


async def run_alert_checks(db: DatabaseClient, settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    since = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    alerts: list[dict[str, Any]] = []

    errors = await db.fetch_one("SELECT COUNT(*) AS count FROM error_events WHERE created_at >= ?", [since])
    error_count = int((errors or {}).get("count") or 0)
    if error_count >= max(1, settings.alert_error_spike_threshold):
        alerts.append(
            {
                "type": "error_spike",
                "severity": "1h",
                "count": error_count,
                "threshold": settings.alert_error_spike_threshold,
                "message": f"Error spike: {error_count} errors in last hour (threshold {settings.alert_error_spike_threshold}).",
            }
        )

    renders = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ? AND status IN ('completed', 'failed')",
        [since],
    )
    failed = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM render_jobs WHERE created_at >= ? AND status = 'failed'",
        [since],
    )
    total = int((renders or {}).get("count") or 0)
    fail_n = int((failed or {}).get("count") or 0)
    fail_rate = (fail_n / total * 100) if total else 0.0
    if total >= 5 and fail_rate >= settings.alert_render_fail_rate_percent:
        alerts.append(
            {
                "type": "render_fail_rate",
                "window": "1h",
                "fail_rate": round(fail_rate, 1),
                "failed": fail_n,
                "total": total,
                "threshold": settings.alert_render_fail_rate_percent,
                "message": f"Render fail rate {fail_rate:.1f}% in last hour ({fail_n}/{total}).",
            }
        )

    queued = await db.fetch_one(
        """
        SELECT COUNT(*) AS count FROM render_jobs
        WHERE status = 'queued' AND created_at <= ?
        """,
        [(datetime.now(UTC) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")],
    )
    queued_stale = int((queued or {}).get("count") or 0)
    if queued_stale > 0:
        alerts.append(
            {
                "type": "queue_lag",
                "stale_queued": queued_stale,
                "message": f"{queued_stale} render job(s) queued > 10 minutes.",
            }
        )

    for alert in alerts:
        await _dispatch_webhook(settings, alert)
        logger.warning("ALERT %s: %s", alert.get("type"), alert.get("message"))
    return alerts


async def _dispatch_webhook(settings: Settings, alert: dict[str, Any]) -> None:
    url = (settings.alert_webhook_url or "").strip()
    if not url:
        return
    payload = {
        "text": f"[AI Math Renderer] {alert.get('message')}",
        "alert": alert,
        "ts": datetime.now(UTC).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(url, json=payload)
    except Exception:
        logger.exception("Alert webhook failed")
