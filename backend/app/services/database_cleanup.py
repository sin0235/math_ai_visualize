from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.session import DatabaseClient


@dataclass(frozen=True)
class CleanupRule:
    table: str
    key_column: str
    where_sql: str
    order_sql: str
    params: tuple[Any, ...] = ()
    default_enabled: bool = True


LOW_RISK_TABLES = {"rate_limit_events", "oauth_states", "auth_tokens", "sessions", "model_scan_jobs"}
REPORT_ONLY_TABLES = {"usage_events", "audit_logs", "render_jobs"}


def cleanup_rules() -> dict[str, CleanupRule]:
    return {
        "rate_limit_events": CleanupRule(
            table="rate_limit_events",
            key_column="rowid",
            where_sql="expires_at <= CURRENT_TIMESTAMP",
            order_sql="expires_at ASC",
        ),
        "oauth_states": CleanupRule(
            table="oauth_states",
            key_column="state_hash",
            where_sql="expires_at <= CURRENT_TIMESTAMP OR (consumed_at IS NOT NULL AND consumed_at <= datetime('now', ?))",
            order_sql="expires_at ASC",
            params=("-7 days",),
        ),
        "auth_tokens": CleanupRule(
            table="auth_tokens",
            key_column="id",
            where_sql="expires_at <= CURRENT_TIMESTAMP OR (consumed_at IS NOT NULL AND consumed_at <= datetime('now', ?))",
            order_sql="expires_at ASC",
            params=("-7 days",),
        ),
        "sessions": CleanupRule(
            table="sessions",
            key_column="id",
            where_sql="expires_at <= CURRENT_TIMESTAMP OR (revoked_at IS NOT NULL AND revoked_at <= datetime('now', ?))",
            order_sql="expires_at ASC",
            params=("-30 days",),
        ),
        "model_scan_jobs": CleanupRule(
            table="model_scan_jobs",
            key_column="id",
            where_sql="status IN ('completed', 'failed') AND COALESCE(finished_at, created_at) <= datetime('now', ?)",
            order_sql="created_at ASC",
            params=("-30 days",),
        ),
        "usage_events": CleanupRule(
            table="usage_events",
            key_column="id",
            where_sql="created_at <= datetime('now', ?)",
            order_sql="created_at ASC",
            params=("-180 days",),
            default_enabled=False,
        ),
        "audit_logs": CleanupRule(
            table="audit_logs",
            key_column="id",
            where_sql="created_at <= datetime('now', ?)",
            order_sql="created_at ASC",
            params=("-365 days",),
            default_enabled=False,
        ),
        "render_jobs": CleanupRule(
            table="render_jobs",
            key_column="id",
            where_sql="status IN ('queued', 'running', 'failed') AND created_at <= datetime('now', ?)",
            order_sql="created_at ASC",
            params=("-30 days",),
            default_enabled=False,
        ),
    }


async def cleanup_database(
    db: DatabaseClient,
    *,
    dry_run: bool = True,
    limit_per_table: int = 100,
    tables: list[str] | None = None,
) -> dict[str, Any]:
    limit = min(max(int(limit_per_table), 1), 5000)
    rules = cleanup_rules()
    selected_tables = tables or [name for name, rule in rules.items() if rule.default_enabled]
    results: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for table in selected_tables:
        rule = rules.get(table)
        if rule is None:
            warnings.append(f"Bỏ qua bảng cleanup không hỗ trợ: {table}")
            continue
        try:
            candidates = await _count_candidates(db, rule, limit)
            deleted = 0 if dry_run else await _delete_candidates(db, rule, limit)
            results[table] = {
                "candidates": candidates,
                "deleted": deleted,
                "dry_run": dry_run,
                "limit": limit,
                "default_enabled": rule.default_enabled,
            }
        except Exception as error:
            results[table] = {
                "candidates": 0,
                "deleted": 0,
                "dry_run": dry_run,
                "limit": limit,
                "error": str(error),
            }
            warnings.append(f"Không thể cleanup {table}: {error}")

    skipped_report_only = sorted(REPORT_ONLY_TABLES - set(selected_tables))
    return {
        "dry_run": dry_run,
        "limit_per_table": limit,
        "tables": results,
        "warnings": warnings,
        "report_only_tables": skipped_report_only,
    }


async def _count_candidates(db: DatabaseClient, rule: CleanupRule, limit: int) -> int:
    row = await db.fetch_one(
        f"""
        SELECT COUNT(*) AS count
        FROM (
          SELECT {rule.key_column}
          FROM {rule.table}
          WHERE {rule.where_sql}
          ORDER BY {rule.order_sql}
          LIMIT ?
        )
        """,
        [*rule.params, limit],
    )
    return int((row or {}).get("count") or 0)


async def _delete_candidates(db: DatabaseClient, rule: CleanupRule, limit: int) -> int:
    candidates = await _count_candidates(db, rule, limit)
    if candidates == 0:
        return 0
    await db.execute(
        f"""
        DELETE FROM {rule.table}
        WHERE {rule.key_column} IN (
          SELECT {rule.key_column}
          FROM {rule.table}
          WHERE {rule.where_sql}
          ORDER BY {rule.order_sql}
          LIMIT ?
        )
        """,
        [*rule.params, limit],
    )
    return candidates
