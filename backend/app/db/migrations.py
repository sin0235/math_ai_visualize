import logging
from pathlib import Path
from typing import Any

import aiosqlite

from app.core.config import Settings
from app.db.session import D1Client, DatabaseClient, PostgresClient, SQLiteClient

logger = logging.getLogger(__name__)

LEGACY_DUPLICATE_MIGRATION_PREFIXES = {
    "0008": {"0008_firebase_auth.sql", "0008_model_management.sql"},
    "0009": {"0009_ai_tier_profiles.sql", "0009_feedback.sql"},
}


async def apply_migrations(db: DatabaseClient, settings: Settings) -> None:
    if isinstance(db, SQLiteClient):
        if settings.auto_apply_sqlite_migrations:
            await apply_sqlite_migrations(db)
            await ensure_chat_image_columns(db)
        return
    if isinstance(db, D1Client) and settings.auto_apply_d1_migrations:
        await apply_d1_migrations(db)
        await ensure_chat_image_columns(db)
        return
    if isinstance(db, PostgresClient):
        await apply_postgres_migrations(db)


async def apply_sqlite_migrations(db: SQLiteClient) -> None:
    migrations_dir = migrations_path()
    migrations = sorted(migrations_dir.glob("*.sql"))
    warn_duplicate_migration_prefixes(migrations)
    async with aiosqlite.connect(db.path) as connection:
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              filename TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await connection.commit()
        for migration in migrations:
            cursor = await connection.execute("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name])
            if await cursor.fetchone():
                continue
            await apply_sqlite_migration_file(connection, migration)


async def apply_sqlite_migration_file(connection: aiosqlite.Connection, migration: Path) -> None:
    try:
        await connection.execute("BEGIN")
        for statement in split_sql_statements(migration.read_text(encoding="utf-8")):
            try:
                await connection.execute(statement)
            except aiosqlite.OperationalError as error:
                if "duplicate column name" not in str(error).lower():
                    raise
        await connection.execute("INSERT INTO schema_migrations (filename) VALUES (?)", [migration.name])
        await connection.commit()
    except Exception:
        await connection.rollback()
        raise


async def apply_d1_migrations(db: D1Client) -> None:
    migrations = sorted(migrations_path().glob("*.sql"))
    warn_duplicate_migration_prefixes(migrations)
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          filename TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for migration in migrations:
        if await db.fetch_one("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name]):
            continue
        for statement in split_sql_statements(migration.read_text(encoding="utf-8")):
            try:
                await db.execute(statement)
            except RuntimeError as error:
                if "duplicate column name" not in str(error).lower():
                    raise
        await db.execute("INSERT INTO schema_migrations (filename) VALUES (?)", [migration.name])


async def apply_postgres_migrations(db: PostgresClient) -> None:
    migrations = sorted(postgres_migrations_path().glob("*.sql"))
    if not migrations:
        raise RuntimeError("Không tìm thấy PostgreSQL migrations.")
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          filename TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for migration in migrations:
        if await db.fetch_one("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name]):
            continue
        statements = [(statement, None) for statement in split_sql_statements(migration.read_text(encoding="utf-8"))]
        statements.append(("INSERT INTO schema_migrations (filename) VALUES (?) ON CONFLICT (filename) DO NOTHING", [migration.name]))
        await db.execute_many(statements)


async def ensure_chat_image_columns(db: DatabaseClient) -> None:
    existing_rows = await db.fetch_all("PRAGMA table_info(chat_messages)")
    existing = {str(row["name"]) for row in existing_rows}
    columns = {
        "message_type": "TEXT NOT NULL DEFAULT 'text'",
        "image_url": "TEXT",
        "image_public_id": "TEXT",
        "image_width": "INTEGER",
        "image_height": "INTEGER",
        "image_bytes": "INTEGER",
        "image_format": "TEXT",
        "image_original_name": "TEXT",
    }
    for name, definition in columns.items():
        if name in existing:
            continue
        try:
            await db.execute(f"ALTER TABLE chat_messages ADD COLUMN {name} {definition}")
        except RuntimeError as error:
            if "duplicate column name" not in str(error).lower():
                raise


async def build_migration_drift(db: DatabaseClient) -> dict[str, Any]:
    local_paths = list_postgres_migration_files() if isinstance(db, PostgresClient) else list_migration_files()
    local_files = [migration.name for migration in local_paths]
    applied_rows = await db.fetch_all("SELECT filename, applied_at FROM schema_migrations ORDER BY filename")
    applied_files = [str(row["filename"]) for row in applied_rows]
    missing = [filename for filename in local_files if filename not in applied_files]
    extra = [filename for filename in applied_files if filename not in local_files]
    unexpected_duplicates = duplicate_migration_prefixes(list_migration_files())
    return {
        "ok": not missing and not extra and not unexpected_duplicates,
        "available_count": len(local_files),
        "applied_count": len(applied_files),
        "missing_migrations": missing,
        "extra_migrations": extra,
        "latest_available_migration": local_files[-1] if local_files else None,
        "latest_applied_migration": applied_files[-1] if applied_files else None,
        "unexpected_duplicate_prefixes": unexpected_duplicates,
    }


def list_migration_files() -> list[Path]:
    return sorted(migrations_path().glob("*.sql"))


def list_postgres_migration_files() -> list[Path]:
    return sorted(postgres_migrations_path().glob("*.sql"))


def migrations_path() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def postgres_migrations_path() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations_postgres"


def duplicate_migration_prefixes(migrations: list[Path]) -> dict[str, list[str]]:
    by_prefix: dict[str, list[str]] = {}
    for migration in migrations:
        prefix = migration.name.split("_", 1)[0]
        if prefix.isdigit():
            by_prefix.setdefault(prefix, []).append(migration.name)
    return {
        prefix: names
        for prefix, names in by_prefix.items()
        if len(names) > 1 and set(names) != LEGACY_DUPLICATE_MIGRATION_PREFIXES.get(prefix)
    }


def warn_duplicate_migration_prefixes(migrations: list[Path]) -> None:
    duplicates = duplicate_migration_prefixes(migrations)
    if duplicates:
        details = "; ".join(f"{prefix}: {', '.join(names)}" for prefix, names in sorted(duplicates.items()))
        logger.warning("Duplicate migration numeric prefixes found: %s", details)


def split_sql_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]
