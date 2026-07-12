import asyncio
import json
import subprocess
from pathlib import Path

import httpx

from app.db.migrations import apply_sqlite_migrations, build_migration_drift, duplicate_migration_prefixes, list_postgres_migration_files, warn_duplicate_migration_prefixes
from app.db.session import D1Client, SQLiteClient, postgres_sql


def test_d1_execute_many_uses_one_atomic_batch_request():
    requests: list[list[dict]] = []

    async def run():
        client = D1Client("account", "database", "token")
        await client._client.aclose()

        async def handler(request: httpx.Request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"success": True, "result": [{"success": True}, {"success": True}]})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await client.execute_many([
            ("INSERT INTO scene_commands (id) VALUES (?)", ["command-1"]),
            ("UPDATE scene_workspaces SET revision = ? WHERE scene_id = ?", [2, "scene-1"]),
        ])
        await client.close()

    asyncio.run(run())

    assert requests == [[
        {"sql": "INSERT INTO scene_commands (id) VALUES (?)", "params": ["command-1"]},
        {"sql": "UPDATE scene_workspaces SET revision = ? WHERE scene_id = ?", "params": [2, "scene-1"]},
    ]]


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


def test_postgres_ai_model_capabilities_migration_exists():
    migration_names = {migration.name for migration in list_postgres_migration_files()}
    migration = Path(__file__).resolve().parents[2] / "migrations_postgres" / "0002_ai_model_capabilities.sql"
    sql = migration.read_text(encoding="utf-8")

    assert "0002_ai_model_capabilities.sql" in migration_names
    assert "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS is_free_endpoint" in sql
    assert "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_thinking" in sql
    assert "CREATE TABLE IF NOT EXISTS model_scan_job_models" in sql


def test_structured_user_history_migration_adds_profile_history_tables(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    tables = asyncio.run(db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'"))
    table_names = {str(row["name"]) for row in tables}
    history_columns = asyncio.run(db.fetch_all("PRAGMA table_info(history_items)"))
    history_indexes = asyncio.run(db.fetch_all("PRAGMA index_list(history_items)"))

    assert {
        "user_learning_profiles",
        "history_projects",
        "history_items",
        "scene_revisions",
        "history_tags",
        "history_item_tags",
    }.issubset(table_names)
    assert {"render_job_id", "title", "topic", "is_favorite", "archived_at", "last_opened_at"}.issubset({str(row["name"]) for row in history_columns})
    assert {
        "idx_history_items_user_updated",
        "idx_history_items_user_favorite",
        "idx_history_items_user_topic",
    }.issubset({str(row["name"]) for row in history_indexes})


def test_postgres_structured_user_history_migration_exists():
    migration_names = {migration.name for migration in list_postgres_migration_files()}
    migration = Path(__file__).resolve().parents[2] / "migrations_postgres" / "0003_structured_user_history.sql"
    sql = migration.read_text(encoding="utf-8")

    assert "0003_structured_user_history.sql" in migration_names
    assert "CREATE TABLE IF NOT EXISTS user_learning_profiles" in sql
    assert "CREATE TABLE IF NOT EXISTS history_items" in sql
    assert "CREATE TABLE IF NOT EXISTS scene_revisions" in sql


def test_user_activity_events_migration_adds_activity_table(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    tables = asyncio.run(db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'"))
    columns = asyncio.run(db.fetch_all("PRAGMA table_info(user_activity_events)"))
    indexes = asyncio.run(db.fetch_all("PRAGMA index_list(user_activity_events)"))

    assert "user_activity_events" in {str(row["name"]) for row in tables}
    assert {"user_id", "event_type", "target_type", "target_id", "metadata_json", "created_at"}.issubset({str(row["name"]) for row in columns})
    assert {
        "idx_user_activity_events_user_created",
        "idx_user_activity_events_type_created",
        "idx_user_activity_events_target",
    }.issubset({str(row["name"]) for row in indexes})


def test_postgres_user_activity_events_migration_exists():
    migration_names = {migration.name for migration in list_postgres_migration_files()}
    migration = Path(__file__).resolve().parents[2] / "migrations_postgres" / "0005_user_activity_events.sql"
    sql = migration.read_text(encoding="utf-8")

    assert "0005_user_activity_events.sql" in migration_names
    assert "CREATE TABLE IF NOT EXISTS user_activity_events" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_user_activity_events_user_created" in sql


def test_analyzer_history_migrations_are_additive(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    columns = asyncio.run(db.fetch_all("PRAGMA table_info(analyzer_history)"))
    indexes = asyncio.run(db.fetch_all("PRAGMA index_list(analyzer_history)"))
    migration_names = {migration.name for migration in list_postgres_migration_files()}

    assert {
        "user_id", "original_expression", "canonical_expression", "result_json", "verification_json",
        "tags_json", "is_pinned", "grade", "chapter", "engine_version", "schema_version", "parent_history_id",
    }.issubset({str(row["name"]) for row in columns})
    assert {
        "idx_analyzer_history_user_updated",
        "idx_analyzer_history_user_pinned",
        "idx_analyzer_history_user_chapter",
    }.issubset({str(row["name"]) for row in indexes})
    assert "0009_analyzer_history.sql" in migration_names


def test_analyzer_links_migrations_are_additive(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    columns = asyncio.run(db.fetch_all("PRAGMA table_info(analyzer_links)"))
    indexes = asyncio.run(db.fetch_all("PRAGMA index_list(analyzer_links)"))
    migration_names = {migration.name for migration in list_postgres_migration_files()}

    assert {
        "short_id", "owner_user_id", "kind", "target", "payload_version", "payload_json",
        "visibility", "scopes_json", "allowed_origins_json", "max_uses", "use_count",
        "expires_at", "revoked_at", "consumed_at",
    }.issubset({str(row["name"]) for row in columns})
    assert {"idx_analyzer_links_owner_created", "idx_analyzer_links_expiry"}.issubset(
        {str(row["name"]) for row in indexes}
    )
    assert "0010_analyzer_links.sql" in migration_names


def test_scene_v3_migrations_add_command_log_and_metadata(tmp_path):
    db = SQLiteClient(str(tmp_path / "test.db"))

    asyncio.run(apply_sqlite_migrations(db))
    tables = asyncio.run(db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'"))
    revision_columns = asyncio.run(db.fetch_all("PRAGMA table_info(scene_revisions)"))
    command_indexes = asyncio.run(db.fetch_all("PRAGMA index_list(scene_commands)"))
    migration_names = {migration.name for migration in list_postgres_migration_files()}

    assert {"scene_workspaces", "scene_commands"}.issubset({str(row["name"]) for row in tables})
    assert {"schema_version", "migration_report_json", "command_log_json"}.issubset(
        {str(row["name"]) for row in revision_columns}
    )
    assert {"idx_scene_commands_scene_revision", "idx_scene_commands_user_created"}.issubset(
        {str(row["name"]) for row in command_indexes}
    )
    assert "0011_scene_v3.sql" in migration_names


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
