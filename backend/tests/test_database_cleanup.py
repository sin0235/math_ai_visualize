import pytest

from app.core.config import Settings
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


@pytest.mark.anyio
async def test_cleanup_uploaded_files_base64_dry_run_does_not_clear_rows(db):
    await insert_uploaded_file(db, "old-r2", "r2", "ZmFrZS1wbmc=", "uploads/ocr/file.png", None, "-2 days")

    result = await cleanup_database(db, dry_run=True, tables=["uploaded_files_base64"])
    row = await db.fetch_one("SELECT data_base64 FROM uploaded_files WHERE id = ?", ["old-r2"])

    cleanup = result["tables"]["uploaded_files_base64"]
    assert cleanup["candidates"] == 1
    assert cleanup["cleared"] == 0
    assert cleanup["bytes_reclaimable"] == len(b"fake-png")
    assert row is not None
    assert row["data_base64"] == "ZmFrZS1wbmc="


@pytest.mark.anyio
async def test_cleanup_uploaded_files_base64_clears_verified_remote_rows(db, monkeypatch):
    await insert_uploaded_file(db, "old-r2", "r2", "ZmFrZS1wbmc=", "uploads/ocr/file.png", None, "-2 days")
    await insert_uploaded_file(db, "database-row", "database", "ZmFrZS1wbmc=", None, None, "-2 days")
    await insert_uploaded_file(db, "new-r2", "r2", "ZmFrZS1wbmc=", "uploads/ocr/new.png", None, "-1 hours")
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"fake-png")

    result = await cleanup_database(db, dry_run=False, tables=["uploaded_files_base64"], settings=settings, min_age_hours=24)
    old_row = await db.fetch_one("SELECT data_base64, base64_cleared_at FROM uploaded_files WHERE id = ?", ["old-r2"])
    db_row = await db.fetch_one("SELECT data_base64 FROM uploaded_files WHERE id = ?", ["database-row"])
    new_row = await db.fetch_one("SELECT data_base64 FROM uploaded_files WHERE id = ?", ["new-r2"])

    cleanup = result["tables"]["uploaded_files_base64"]
    assert cleanup["candidates"] == 1
    assert cleanup["cleared"] == 1
    assert cleanup["bytes_cleared"] == len(b"fake-png")
    assert old_row is not None
    assert old_row["data_base64"] == ""
    assert old_row["base64_cleared_at"] is not None
    assert db_row is not None and db_row["data_base64"] == "ZmFrZS1wbmc="
    assert new_row is not None and new_row["data_base64"] == "ZmFrZS1wbmc="


@pytest.mark.anyio
async def test_cleanup_uploaded_files_base64_skips_remote_mismatch(db, monkeypatch):
    await insert_uploaded_file(db, "old-r2", "r2", "ZmFrZS1wbmc=", "uploads/ocr/file.png", None, "-2 days")
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.load_file", lambda object_key, settings: b"different")

    result = await cleanup_database(db, dry_run=False, tables=["uploaded_files_base64"], settings=settings)
    row = await db.fetch_one("SELECT data_base64 FROM uploaded_files WHERE id = ?", ["old-r2"])

    cleanup = result["tables"]["uploaded_files_base64"]
    assert cleanup["candidates"] == 1
    assert cleanup["cleared"] == 0
    assert cleanup["skipped"] == 1
    assert cleanup["warnings"]
    assert row is not None
    assert row["data_base64"] == "ZmFrZS1wbmc="


async def insert_uploaded_file(
    db: SQLiteClient,
    upload_id: str,
    provider: str,
    data_base64: str,
    storage_key: str | None,
    external_file_id: str | None,
    age_sql: str,
) -> None:
    await db.execute(
        """
        INSERT INTO uploaded_files (
          id, user_id, filename, content_type, size, sha256, data_base64,
          storage_key, public_url, storage_provider, storage_bucket, external_file_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', ?))
        """,
        [
            upload_id,
            None,
            "problem.png",
            "image/png",
            len(b"fake-png"),
            "f084b1351c41cf3c554d932a3a978992a39b902f289c6e213b6428c3b38541ed",
            data_base64,
            storage_key,
            None,
            provider,
            "bucket" if provider in {"appwrite", "r2"} else None,
            external_file_id,
            age_sql,
        ],
    )
