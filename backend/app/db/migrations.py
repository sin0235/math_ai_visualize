from pathlib import Path

from app.db.session import DatabaseClient


async def apply_migrations(db: DatabaseClient) -> None:
    migrations_dir = Path(__file__).resolve().parents[3] / "migrations"
    for migration in sorted(migrations_dir.glob("*.sql")):
        statements = [statement.strip() for statement in migration.read_text(encoding="utf-8").split(";")]
        for statement in statements:
            if statement:
                await db.execute(statement)
