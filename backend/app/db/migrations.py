from pathlib import Path

import aiosqlite

from app.core.config import Settings
from app.db.session import D1Client, DatabaseClient, SQLiteClient


async def apply_migrations(db: DatabaseClient, settings: Settings) -> None:
    if isinstance(db, SQLiteClient):
        if settings.auto_apply_sqlite_migrations:
            await apply_sqlite_migrations(db)
        return
    if isinstance(db, D1Client) and settings.auto_apply_d1_migrations:
        await apply_d1_migrations(db)


async def apply_sqlite_migrations(db: SQLiteClient) -> None:
    migrations_dir = migrations_path()
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
        for migration in sorted(migrations_dir.glob("*.sql")):
            cursor = await connection.execute("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name])
            if await cursor.fetchone():
                continue
            await connection.executescript(migration.read_text(encoding="utf-8"))
            await connection.execute("INSERT INTO schema_migrations (filename) VALUES (?)", [migration.name])
        await connection.commit()


async def apply_d1_migrations(db: D1Client) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          filename TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    for migration in sorted(migrations_path().glob("*.sql")):
        if await db.fetch_one("SELECT 1 FROM schema_migrations WHERE filename = ?", [migration.name]):
            continue
        for statement in split_sql_statements(migration.read_text(encoding="utf-8")):
            await db.execute(statement)
        await db.execute("INSERT INTO schema_migrations (filename) VALUES (?)", [migration.name])


def migrations_path() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def split_sql_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]
