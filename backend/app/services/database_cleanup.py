from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.db.session import DatabaseClient
from app.repositories.uploads import uploaded_file_from_row
from app.services.upload_storage import delete_remote_upload, load_remote_upload_body, verify_upload_body


@dataclass(frozen=True)
class CleanupRule:
    table: str
    key_column: str
    where_sql: str
    order_sql: str
    params: tuple[Any, ...] = ()
    default_enabled: bool = True


LOW_RISK_TABLES = {"rate_limit_events", "oauth_states", "auth_tokens", "sessions", "model_scan_jobs"}
REPORT_ONLY_TABLES = {"usage_events", "audit_logs", "render_jobs", "uploaded_files_base64", "uploaded_files_remote"}
REMOTE_UPLOAD_PROVIDERS = {"appwrite", "r2"}
DELETE_TEST_UPLOADS_CONFIRM = "DELETE_TEST_UPLOADS"
RESET_DEV_DATA_CONFIRM = "RESET_DEV_DATA_KEEP_ADMIN_CONFIG"
DEV_RESET_USER_TABLES = ["model_scan_jobs", "oauth_identities", "auth_tokens", "sessions", "legal_acceptances", "user_settings"]
DEV_RESET_GLOBAL_TABLES = [
    "chat_messages",
    "chat_conversations",
    "feedback",
    "usage_events",
    "render_jobs",
    "uploaded_files",
    "rate_limit_events",
    "oauth_states",
]


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
    settings: Settings | None = None,
    min_age_hours: int = 24,
    verify_remote: bool = True,
    providers: list[str] | None = None,
    confirm: str | None = None,
    delete_remote: bool = False,
    delete_db_record: bool = False,
) -> dict[str, Any]:
    limit = min(max(int(limit_per_table), 1), 5000)
    rules = cleanup_rules()
    selected_tables = tables or [name for name, rule in rules.items() if rule.default_enabled]
    results: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for table in selected_tables:
        if table == "uploaded_files_base64":
            try:
                results[table] = await cleanup_uploaded_files_base64(
                    db,
                    settings=settings or get_settings(),
                    dry_run=dry_run,
                    limit=limit,
                    min_age_hours=min_age_hours,
                    verify_remote=verify_remote,
                    providers=providers,
                )
            except Exception as error:
                results[table] = {
                    "candidates": 0,
                    "cleared": 0,
                    "skipped": 0,
                    "dry_run": dry_run,
                    "limit": limit,
                    "error": str(error),
                }
                warnings.append(f"Không thể cleanup {table}: {error}")
            continue

        if table == "uploaded_files_remote":
            try:
                results[table] = await cleanup_uploaded_files_remote(
                    db,
                    settings=settings or get_settings(),
                    dry_run=dry_run,
                    limit=limit,
                    min_age_hours=min_age_hours,
                    providers=providers,
                    confirm=confirm,
                    delete_remote=delete_remote,
                    delete_db_record=delete_db_record,
                )
            except Exception as error:
                results[table] = {
                    "candidates": 0,
                    "remote_deleted": 0,
                    "db_deleted": 0,
                    "skipped": 0,
                    "dry_run": dry_run,
                    "limit": limit,
                    "error": str(error),
                }
                warnings.append(f"Không thể cleanup {table}: {error}")
            continue

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


async def cleanup_uploaded_files_base64(
    db: DatabaseClient,
    *,
    settings: Settings,
    dry_run: bool,
    limit: int,
    min_age_hours: int,
    verify_remote: bool,
    providers: list[str] | None,
) -> dict[str, Any]:
    selected_providers = normalize_upload_providers(providers)
    rows = await uploaded_files_base64_candidates(db, limit, min_age_hours, selected_providers)
    breakdown = summarize_uploaded_file_candidates(rows)
    warnings: list[str] = []
    cleared = 0
    bytes_cleared = 0
    skipped = 0

    if not dry_run:
        for row in rows:
            record = uploaded_file_from_row(row)
            try:
                if verify_remote:
                    body = await load_remote_upload_body(record, settings)
                    verify_upload_body(record, body)
                await db.execute(
                    """
                    UPDATE uploaded_files
                    SET data_base64 = '', base64_cleared_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND data_base64 != ''
                    """,
                    [record.id],
                )
                cleared += 1
                bytes_cleared += estimated_base64_bytes(record.data_base64 or "")
            except Exception as error:
                skipped += 1
                warnings.append(f"Bỏ qua một uploaded_file provider {record.storage_provider}: {error}")

    return {
        "candidates": len(rows),
        "cleared": cleared,
        "skipped": skipped,
        "dry_run": dry_run,
        "limit": limit,
        "min_age_hours": min_age_hours,
        "verify_remote": verify_remote,
        "providers": sorted(selected_providers),
        "bytes_reclaimable": breakdown["bytes_reclaimable"],
        "bytes_cleared": bytes_cleared,
        "by_provider": breakdown["by_provider"],
        "warnings": warnings[:50],
    }


async def cleanup_uploaded_files_remote(
    db: DatabaseClient,
    *,
    settings: Settings,
    dry_run: bool,
    limit: int,
    min_age_hours: int,
    providers: list[str] | None,
    confirm: str | None,
    delete_remote: bool,
    delete_db_record: bool,
) -> dict[str, Any]:
    selected_providers = normalize_upload_providers(providers)
    rows = await uploaded_files_remote_candidates(db, limit, min_age_hours, selected_providers)
    breakdown = summarize_uploaded_file_candidates(rows)
    warnings: list[str] = []
    remote_deleted = 0
    db_deleted = 0
    skipped = 0

    if not dry_run:
        if confirm != DELETE_TEST_UPLOADS_CONFIRM:
            raise ValueError(f"Cần confirm={DELETE_TEST_UPLOADS_CONFIRM} để xoá uploaded_files.")
        if not delete_remote and not delete_db_record:
            raise ValueError("Cần chọn delete_remote hoặc delete_db_record khi chạy cleanup uploaded_files_remote.")
        for row in rows:
            record = uploaded_file_from_row(row)
            try:
                if delete_remote and record.storage_provider in REMOTE_UPLOAD_PROVIDERS:
                    await delete_remote_upload(record, settings)
                    remote_deleted += 1
                if delete_db_record:
                    await db.execute("DELETE FROM uploaded_files WHERE id = ?", [record.id])
                    db_deleted += 1
            except Exception as error:
                skipped += 1
                warnings.append(f"Bỏ qua uploaded_file provider {record.storage_provider}: {error}")

    return {
        "candidates": len(rows),
        "remote_deleted": remote_deleted,
        "db_deleted": db_deleted,
        "skipped": skipped,
        "dry_run": dry_run,
        "limit": limit,
        "min_age_hours": min_age_hours,
        "providers": sorted(selected_providers),
        "delete_remote": delete_remote,
        "delete_db_record": delete_db_record,
        "bytes_reclaimable": breakdown["bytes_reclaimable"],
        "by_provider": breakdown["by_provider"],
        "warnings": warnings[:50],
    }


async def reset_dev_data(
    db: DatabaseClient,
    *,
    dry_run: bool = True,
    confirm: str | None = None,
    settings: Settings | None = None,
    delete_upload_remotes: bool = False,
) -> dict[str, Any]:
    table_counts = await dev_reset_counts(db)
    warnings: list[str] = []
    remote_deleted = 0
    remote_skipped = 0

    if not dry_run:
        if confirm != RESET_DEV_DATA_CONFIRM:
            raise ValueError(f"Cần confirm={RESET_DEV_DATA_CONFIRM} để reset dữ liệu dev.")
        current_settings = settings or get_settings()
        if current_settings.environment == "production":
            raise ValueError("Không được reset dữ liệu dev khi ENVIRONMENT=production.")
        if delete_upload_remotes:
            rows = await all_remote_uploaded_files(db)
            for row in rows:
                record = uploaded_file_from_row(row)
                try:
                    await delete_remote_upload(record, current_settings)
                    remote_deleted += 1
                except Exception as error:
                    remote_skipped += 1
                    warnings.append(f"Không xoá được remote upload provider {record.storage_provider}: {error}")
        await execute_dev_reset(db)

    return {
        "dry_run": dry_run,
        "confirm_required": RESET_DEV_DATA_CONFIRM,
        "tables": table_counts,
        "remote_deleted": remote_deleted,
        "remote_skipped": remote_skipped,
        "warnings": warnings[:50],
    }


async def uploaded_files_base64_candidates(db: DatabaseClient, limit: int, min_age_hours: int, providers: set[str]) -> list[Any]:
    placeholders = ", ".join("?" for _ in providers)
    return await db.fetch_all(
        f"""
        SELECT *
        FROM uploaded_files
        WHERE storage_provider IN ({placeholders})
          AND data_base64 IS NOT NULL
          AND data_base64 != ''
          AND created_at <= datetime('now', ?)
          AND (
            (storage_provider = 'appwrite' AND external_file_id IS NOT NULL AND external_file_id != '')
            OR (storage_provider = 'r2' AND storage_key IS NOT NULL AND storage_key != '')
          )
        ORDER BY created_at ASC
        LIMIT ?
        """,
        [*sorted(providers), f"-{max(1, int(min_age_hours))} hours", limit],
    )


async def uploaded_files_remote_candidates(db: DatabaseClient, limit: int, min_age_hours: int, providers: set[str]) -> list[Any]:
    placeholders = ", ".join("?" for _ in providers)
    return await db.fetch_all(
        f"""
        SELECT *
        FROM uploaded_files
        WHERE storage_provider IN ({placeholders})
          AND created_at <= datetime('now', ?)
          AND (
            (storage_provider = 'appwrite' AND external_file_id IS NOT NULL AND external_file_id != '')
            OR (storage_provider = 'r2' AND storage_key IS NOT NULL AND storage_key != '')
          )
        ORDER BY created_at ASC
        LIMIT ?
        """,
        [*sorted(providers), f"-{max(1, int(min_age_hours))} hours", limit],
    )


async def all_remote_uploaded_files(db: DatabaseClient) -> list[Any]:
    return await db.fetch_all(
        """
        SELECT *
        FROM uploaded_files
        WHERE storage_provider IN ('appwrite', 'r2')
          AND (
            (storage_provider = 'appwrite' AND external_file_id IS NOT NULL AND external_file_id != '')
            OR (storage_provider = 'r2' AND storage_key IS NOT NULL AND storage_key != '')
          )
        ORDER BY created_at ASC
        """
    )


async def dev_reset_counts(db: DatabaseClient) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in DEV_RESET_GLOBAL_TABLES:
        counts[table] = await count_where(db, table, "1 = 1")
    for table in DEV_RESET_USER_TABLES:
        counts[table] = await count_where(db, table, "user_id IN (SELECT id FROM users WHERE role != 'admin')")
    counts["users"] = await count_where(db, "users", "role != 'admin'")
    return counts


async def execute_dev_reset(db: DatabaseClient) -> None:
    for table in DEV_RESET_GLOBAL_TABLES:
        await delete_where(db, table, "1 = 1")
    for table in DEV_RESET_USER_TABLES:
        await delete_where(db, table, "user_id IN (SELECT id FROM users WHERE role != 'admin')")
    await delete_where(db, "users", "role != 'admin'")


def normalize_upload_providers(providers: list[str] | None) -> set[str]:
    if providers is None:
        return set(REMOTE_UPLOAD_PROVIDERS)
    selected = {provider for provider in providers if provider in REMOTE_UPLOAD_PROVIDERS}
    return selected or set(REMOTE_UPLOAD_PROVIDERS)


def summarize_uploaded_file_candidates(rows: list[Any]) -> dict[str, Any]:
    by_provider: dict[str, dict[str, int]] = {}
    bytes_reclaimable = 0
    for row in rows:
        provider = str(row.get("storage_provider") or "database")
        inline_bytes = int(row.get("size") or 0) or estimated_base64_bytes(str(row.get("data_base64") or ""))
        item = by_provider.setdefault(provider, {"candidates": 0, "bytes_reclaimable": 0})
        item["candidates"] += 1
        item["bytes_reclaimable"] += inline_bytes
        bytes_reclaimable += inline_bytes
    return {"by_provider": by_provider, "bytes_reclaimable": bytes_reclaimable}


def estimated_base64_bytes(value: str) -> int:
    text = value.strip()
    if not text:
        return 0
    padding = text.count("=")
    return max(0, (len(text) * 3 // 4) - padding)


async def count_where(db: DatabaseClient, table: str, where_sql: str) -> int:
    row = await db.fetch_one(f"SELECT COUNT(*) AS count FROM {table} WHERE {where_sql}")
    return int((row or {}).get("count") or 0)


async def delete_where(db: DatabaseClient, table: str, where_sql: str) -> None:
    await db.execute(f"DELETE FROM {table} WHERE {where_sql}")


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
