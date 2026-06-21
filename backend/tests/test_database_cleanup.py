import pytest

from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.repositories.auth import UserRepository
from app.services.database_cleanup import DELETE_TEST_UPLOADS_CONFIRM, RESET_DEV_DATA_CONFIRM, cleanup_database, reset_dev_data


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


@pytest.mark.anyio
async def test_cleanup_uploaded_files_remote_requires_confirm_for_execute(db):
    await insert_uploaded_file(db, "old-r2", "r2", "", "uploads/ocr/file.png", None, "-2 days")

    result = await cleanup_database(db, dry_run=False, tables=["uploaded_files_remote"], delete_remote=True)
    row = await db.fetch_one("SELECT COUNT(*) AS count FROM uploaded_files")

    cleanup = result["tables"]["uploaded_files_remote"]
    assert cleanup["error"].startswith("Cần confirm=DELETE_TEST_UPLOADS")
    assert row is not None and row["count"] == 1


@pytest.mark.anyio
async def test_cleanup_uploaded_files_remote_deletes_remote_and_db_record(db, monkeypatch):
    await insert_uploaded_file(db, "old-r2", "r2", "", "uploads/ocr/file.png", None, "-2 days")
    deleted_keys = []
    settings = Settings(
        _env_file=None,
        r2_account_id="account",
        r2_access_key_id="access",
        r2_secret_access_key="secret",
        r2_bucket_name="bucket",
    )

    monkeypatch.setattr("app.services.r2_storage.delete_file", lambda object_key, settings: deleted_keys.append(object_key))

    result = await cleanup_database(
        db,
        dry_run=False,
        tables=["uploaded_files_remote"],
        settings=settings,
        confirm=DELETE_TEST_UPLOADS_CONFIRM,
        delete_remote=True,
        delete_db_record=True,
    )
    row = await db.fetch_one("SELECT COUNT(*) AS count FROM uploaded_files")

    cleanup = result["tables"]["uploaded_files_remote"]
    assert cleanup["candidates"] == 1
    assert cleanup["remote_deleted"] == 1
    assert cleanup["db_deleted"] == 1
    assert deleted_keys == ["uploads/ocr/file.png"]
    assert row is not None and row["count"] == 0


@pytest.mark.anyio
async def test_reset_dev_data_dry_run_counts_user_data(db):
    admin, user = await seed_admin_and_user_data(db)

    result = await reset_dev_data(db, dry_run=True)
    admin_row = await db.fetch_one("SELECT * FROM users WHERE id = ?", [admin.id])
    user_row = await db.fetch_one("SELECT * FROM users WHERE id = ?", [user.id])

    assert result["tables"]["users"] == 1
    assert result["tables"]["render_jobs"] == 1
    assert result["tables"]["uploaded_files"] == 1
    assert admin_row is not None
    assert user_row is not None


@pytest.mark.anyio
async def test_reset_dev_data_execute_keeps_admin_and_config(db):
    admin, user = await seed_admin_and_user_data(db)
    await db.execute("INSERT INTO system_settings (key, value_json, updated_by) VALUES (?, ?, ?)", ["ai_settings", "{}", admin.id])
    await db.execute("INSERT INTO ai_providers (id, label, base_url, default_model_id) VALUES (?, ?, ?, ?)", ["test_provider", "Test", "https://example.test", "model"])

    result = await reset_dev_data(db, dry_run=False, confirm=RESET_DEV_DATA_CONFIRM)
    admin_row = await db.fetch_one("SELECT * FROM users WHERE id = ?", [admin.id])
    user_row = await db.fetch_one("SELECT * FROM users WHERE id = ?", [user.id])
    settings_row = await db.fetch_one("SELECT * FROM system_settings WHERE key = ?", ["ai_settings"])
    provider_row = await db.fetch_one("SELECT * FROM ai_providers WHERE id = ?", ["test_provider"])
    upload_count = await db.fetch_one("SELECT COUNT(*) AS count FROM uploaded_files")
    render_count = await db.fetch_one("SELECT COUNT(*) AS count FROM render_jobs")

    assert result["tables"]["users"] == 1
    assert admin_row is not None and admin_row["role"] == "admin"
    assert user_row is None
    assert settings_row is not None
    assert provider_row is not None
    assert upload_count is not None and upload_count["count"] == 0
    assert render_count is not None and render_count["count"] == 0


@pytest.mark.anyio
async def test_reset_dev_data_rejects_wrong_confirm(db):
    await seed_admin_and_user_data(db)

    with pytest.raises(ValueError, match="RESET_DEV_DATA_KEEP_ADMIN_CONFIG"):
        await reset_dev_data(db, dry_run=False, confirm="WRONG")


async def seed_admin_and_user_data(db: SQLiteClient):
    admin = await UserRepository(db).create("admin@example.com", "StrongPass123")
    user = await UserRepository(db).create("user@example.com", "StrongPass123")
    await db.execute("UPDATE users SET role = 'admin' WHERE id = ?", [admin.id])
    await db.execute(
        """
        INSERT INTO render_jobs (id, user_id, problem_text, provider, model, scene_json, payload_json, warnings_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ["job-1", user.id, "Bài toán", "mock", "model", "{}", "{}", "[]"],
    )
    await db.execute("INSERT INTO usage_events (id, user_id, event_type) VALUES (?, ?, ?)", ["usage-1", user.id, "ocr"])
    await insert_uploaded_file(db, "upload-1", "database", "ZmFrZS1wbmc=", None, None, "-1 hours")
    return admin, user


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
