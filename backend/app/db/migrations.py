import logging
from pathlib import Path

import aiosqlite

from app.core.config import Settings
from app.db.session import D1Client, DatabaseClient, SQLiteClient

logger = logging.getLogger(__name__)

LEGACY_DUPLICATE_MIGRATION_PREFIXES = {
    "0008": {"0008_firebase_auth.sql", "0008_model_management.sql"},
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
        for migration in migrations:
            cursor = await connection.execute("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name])
            if await cursor.fetchone():
                continue
            await connection.executescript(migration.read_text(encoding="utf-8"))
            await connection.execute("INSERT INTO schema_migrations (filename) VALUES (?)", [migration.name])
        await connection.commit()


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


def migrations_path() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def warn_duplicate_migration_prefixes(migrations: list[Path]) -> None:
    by_prefix: dict[str, list[str]] = {}
    for migration in migrations:
        prefix = migration.name.split("_", 1)[0]
        if prefix.isdigit():
            by_prefix.setdefault(prefix, []).append(migration.name)
    duplicates = {
        prefix: names
        for prefix, names in by_prefix.items()
        if len(names) > 1 and set(names) != LEGACY_DUPLICATE_MIGRATION_PREFIXES.get(prefix)
    }
    if duplicates:
        details = "; ".join(f"{prefix}: {', '.join(names)}" for prefix, names in sorted(duplicates.items()))
        logger.warning("Duplicate migration numeric prefixes found: %s", details)


def split_sql_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]
