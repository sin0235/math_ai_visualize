import pytest

from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.services.database_cleanup import cleanup_database


@pytest.fixture
async def db(tmp_path):
    client = SQLiteClient(str(tmp_path / "cleanup.db"))
    await apply_sqlite_migrations(client)
    return client


@pytest.mark.anyio
async def test_cleanup_database_dry_run_does_not_delete_expired_rows(db):
    await db.execute(
        "INSERT INTO rate_limit_events (key, bucket, count, expires_at) VALUES (?, ?, ?, datetime('now', '-1 day'))",
        ["ip:test", "bucket", 1],
    )

    result = await cleanup_database(db, dry_run=True, tables=["rate_limit_events"])
    row = await db.fetch_one("SELECT COUNT(*) AS count FROM rate_limit_events")

    assert result["tables"]["rate_limit_events"]["candidates"] == 1
    assert result["tables"]["rate_limit_events"]["deleted"] == 0
    assert row is not None
    assert row["count"] == 1


@pytest.mark.anyio
async def test_cleanup_database_deletes_only_limited_expired_rows(db):
    for index in range(3):
        await db.execute(
            "INSERT INTO rate_limit_events (key, bucket, count, expires_at) VALUES (?, ?, ?, datetime('now', '-1 day'))",
            [f"ip:test:{index}", "bucket", 1],
        )

    result = await cleanup_database(db, dry_run=False, limit_per_table=2, tables=["rate_limit_events"])
    row = await db.fetch_one("SELECT COUNT(*) AS count FROM rate_limit_events")

    assert result["tables"]["rate_limit_events"]["candidates"] == 2
    assert result["tables"]["rate_limit_events"]["deleted"] == 2
    assert row is not None
    assert row["count"] == 1


@pytest.mark.anyio
async def test_cleanup_database_ignores_unsupported_tables(db):
    result = await cleanup_database(db, tables=["unknown_table"])

    assert result["tables"] == {}
    assert result["warnings"] == ["Bỏ qua bảng cleanup không hỗ trợ: unknown_table"]
