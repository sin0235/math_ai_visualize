from pathlib import Path

from app.db.migrations import warn_duplicate_migration_prefixes


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
