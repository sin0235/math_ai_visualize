from pathlib import Path

from app.db.session import resolve_sqlite_path, sqlite_path_diagnostics


def test_resolve_sqlite_path_keeps_absolute_path(tmp_path):
    path = tmp_path / "data.db"

    assert resolve_sqlite_path(str(path)) == path


def test_resolve_sqlite_path_uses_project_root_for_relative_path():
    resolved = resolve_sqlite_path("backend/.data/hinh.db")

    assert resolved.is_absolute()
    assert resolved == Path(__file__).resolve().parents[2] / "backend/.data/hinh.db"


def test_sqlite_path_diagnostics_reports_resolved_path(tmp_path):
    path = tmp_path / "missing.db"

    diagnostics = sqlite_path_diagnostics(str(path))

    assert diagnostics["configured_path"] == str(path)
    assert diagnostics["resolved_path"] == str(path)
    assert diagnostics["parent_exists"] is True
    assert diagnostics["file_exists"] is False
