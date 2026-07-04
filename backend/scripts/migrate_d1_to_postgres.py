from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from typing import Any

from app.core.config import Settings
from app.db.session import D1Client, PostgresClient

TABLE_ORDER = [
    "users",
    "sessions",
    "auth_tokens",
    "legal_acceptances",
    "oauth_identities",
    "oauth_states",
    "user_settings",
    "render_jobs",
    "system_settings",
    "audit_logs",
    "usage_events",
    "ai_providers",
    "ai_models",
    "ai_task_profiles",
    "ai_model_settings",
    "feedback",
    "plans",
    "model_scan_jobs",
    "uploaded_files",
    "chat_conversations",
    "chat_messages",
    "user_ai_provider_settings",
    "user_ai_models",
    "user_ai_task_profiles",
    "rate_limit_events",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate Cloudflare D1 rows into PostgreSQL after raw D1 backup/export.")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--tables", nargs="*", default=None, help="Optional table subset, keeps provided order.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = Settings()
    if not settings.d1_account_id or not settings.d1_database_id or not settings.d1_api_token:
        raise SystemExit("Missing D1_ACCOUNT_ID, D1_DATABASE_ID, or D1_API_TOKEN.")
    if not settings.database_url:
        raise SystemExit("Missing DATABASE_URL for PostgreSQL target.")

    source = D1Client(settings.d1_account_id, settings.d1_database_id, settings.d1_api_token)
    target = PostgresClient(settings.database_url)
    tables = args.tables or TABLE_ORDER
    batch_size = max(1, int(args.batch_size))

    for table in tables:
        source_count = await count_rows(source, table)
        target_before = await count_rows(target, table)
        copied = 0
        offset = 0
        while offset < source_count:
            rows = await source.fetch_all(f"SELECT * FROM {table} LIMIT ? OFFSET ?", [batch_size, offset])
            if not rows:
                break
            if not args.dry_run:
                await insert_rows(target, table, rows)
            copied += len(rows)
            offset += batch_size
        target_after = await count_rows(target, table)
        print(f"{table}: source={source_count} target_before={target_before} copied={copied} target_after={target_after}")


async def count_rows(db: D1Client | PostgresClient, table: str) -> int:
    row = await db.fetch_one(f"SELECT COUNT(*) AS count FROM {table}")
    return int((row or {}).get("count") or 0)


async def insert_rows(db: PostgresClient, table: str, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    column_sql = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {quote_identifier(table)} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    statements = [(sql, [row.get(column) for column in columns]) for row in rows]
    await db.execute_many(statements)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


if __name__ == "__main__":
    asyncio.run(main())