from pathlib import Path

from app.db.migrations import warn_duplicate_migration_prefixes


def test_warn_duplicate_migration_prefixes_logs_duplicate_numbers(caplog):
    migrations = [
        Path("0008_firebase_auth.sql"),
        Path("0008_model_management.sql"),
        Path("0009_feedback.sql"),
    ]

    warn_duplicate_migration_prefixes(migrations)

    assert "Duplicate migration numeric prefixes found" in caplog.text
    assert "0008_firebase_auth.sql" in caplog.text
    assert "0008_model_management.sql" in caplog.text
