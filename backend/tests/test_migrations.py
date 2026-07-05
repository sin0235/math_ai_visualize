import asyncio
import subprocess
from pathlib import Path

from app.db.migrations import apply_sqlite_migrations, build_migration_drift, duplicate_migration_prefixes, warn_duplicate_migration_prefixes
from app.db.session import SQLiteClient, postgres_sql


def test_warn_duplicate_migration_prefixes_ignores_known_legacy_duplicate(caplog):
    migrations = [
        Path("0008_firebase_auth.sql"),
        Path("0008_model_management.sql"),
        Path("0009_feedback.sql"),
    ]

    warn_duplicate_migration_prefixes(migrations)

    assert "Duplicate migration numeric prefixes found" not in caplog.text


def test_warn_duplicate_migration_prefixes_logs_new_duplicate_numbers(caplog):
    migrations = [
        Path("0018_first.sql"),
        Path("0018_second.sql"),
    ]

    warn_duplicate_migration_prefixes(migrations)

    assert "Duplicate migration numeric prefixes found" in caplog.text
    assert "0018_first.sql" in caplog.text
    assert "0018_second.sql" in caplog.text


def test_duplicate_migration_prefixes_ignores_known_legacy_duplicates():
    migrations = [
        Path("0008_firebase_auth.sql"),
        Path("0008_model_management.sql"),
        Path("0009_ai_tier_profiles.sql"),
        Path("0009_feedback.sql"),
    ]

    assert duplicate_migration_prefixes(migrations) == {}


def test_uploaded_files_cleanup_migration_adds_base64_cleared_at(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    columns = asyncio.run(db.fetch_all("PRAGMA table_info(uploaded_files)"))
    indexes = asyncio.run(db.fetch_all("PRAGMA index_list(uploaded_files)"))

    assert "base64_cleared_at" in {str(row["name"]) for row in columns}
    assert "idx_uploaded_files_provider_created" in {str(row["name"]) for row in indexes}


def test_system_hardening_migration_adds_byok_and_render_metadata(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    tables = asyncio.run(db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'"))
    table_names = {str(row["name"]) for row in tables}
    render_columns = asyncio.run(db.fetch_all("PRAGMA table_info(render_jobs)"))
    render_indexes = asyncio.run(db.fetch_all("PRAGMA index_list(render_jobs)"))

    assert {
        "user_ai_provider_settings",
        "user_ai_models",
        "user_ai_task_profiles",
    }.issubset(table_names)
    assert {"degraded", "fallback_source", "ai_source"}.issubset({str(row["name"]) for row in render_columns})
    assert "idx_render_jobs_status_created" in {str(row["name"]) for row in render_indexes}


def test_ai_model_capabilities_migration_adds_registry_metadata(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    model_columns = asyncio.run(db.fetch_all("PRAGMA table_info(ai_models)"))
    model_indexes = asyncio.run(db.fetch_all("PRAGMA index_list(ai_models)"))
    scan_columns = asyncio.run(db.fetch_all("PRAGMA table_info(model_scan_jobs)"))
    tables = asyncio.run(db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'"))

    assert {
        "is_free_endpoint",
        "supports_thinking",
        "supports_vision",
        "pricing_json",
        "endpoint_metadata_json",
        "supported_parameters_json",
    }.issubset({str(row["name"]) for row in model_columns})
    assert {
        "idx_ai_models_provider_free_allowed",
        "idx_ai_models_provider_thinking_allowed",
    }.issubset({str(row["name"]) for row in model_indexes})
    assert {"runtime_json", "base_url", "result_count", "free_count", "thinking_count", "warnings_json", "updated_at"}.issubset({str(row["name"]) for row in scan_columns})
    assert "model_scan_job_models" in {str(row["name"]) for row in tables}


def test_postgres_sql_translates_placeholders_outside_literals():
    assert postgres_sql("SELECT * FROM users WHERE email = ? AND note = '?' AND created_at >= CURRENT_TIMESTAMP") == (
        "SELECT * FROM users WHERE email = $1 AND note = '?' AND created_at >= (CURRENT_TIMESTAMP::text)"
    )


def test_secret_files_are_not_tracked():
    blocked = {
        ".wrangler/cache/wrangler-account.json",
        "backend/.data/hinh.db",
        "backend/backend/.data/hinh.db",
    }
    result = subprocess.run(
        ["git", "ls-files", ".wrangler/cache/wrangler-account.json", "backend/.codex_pytest_tmp_base_url", "backend/.data/hinh.db", "backend/backend/.data/hinh.db"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    assert not tracked & blocked
    assert not any(path.startswith("backend/.codex_pytest_tmp_base_url/") for path in tracked)


def test_build_migration_drift_reports_missing_and_extra(tmp_path, monkeypatch):
    import app.db.migrations as migrations_module

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "0002_next.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr(migrations_module, "migrations_path", lambda: migrations_dir)

    db = SQLiteClient(str(tmp_path / "test.db"))
    asyncio.run(db.execute("CREATE TABLE schema_migrations (filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
    asyncio.run(db.execute("INSERT INTO schema_migrations (filename) VALUES (?)", ["0001_initial.sql"]))
    asyncio.run(db.execute("INSERT INTO schema_migrations (filename) VALUES (?)", ["9999_removed.sql"]))

    drift = asyncio.run(build_migration_drift(db))

    assert drift["ok"] is False
    assert drift["available_count"] == 2
    assert drift["applied_count"] == 2
    assert drift["missing_migrations"] == ["0002_next.sql"]
    assert drift["extra_migrations"] == ["9999_removed.sql"]
    assert drift["latest_available_migration"] == "0002_next.sql"
    assert drift["latest_applied_migration"] == "9999_removed.sql"
