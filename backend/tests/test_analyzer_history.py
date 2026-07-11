import json

import pytest
from fastapi import Request
from pydantic import ValidationError

from app.api.routes_analyzer_history import create_analyzer_history, get_analyzer_history
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient
from app.repositories.analyzer_history import AnalyzerHistoryRepository, normalize_tags
from app.schemas.analysis import AnalyzeResponse, CurriculumProfile
from app.schemas.analyzer_history import AnalyzerExportRequest, AnalyzerHistoryCreateRequest
from app.services.analyzer_runtime import analysis_scope, clear_runtime_state, create_analysis_session
from app.services.function_analysis_curriculum import apply_curriculum_profile, build_curriculum_presentation
from app.services.function_analysis_export import build_analyzer_export_document, render_analyzer_export


@pytest.mark.parametrize(
    ("grade", "term"),
    [(10, "Tập xác định"), (11, "Tính tuần hoàn"), (12, "Đạo hàm")],
)
def test_curriculum_profiles_change_presentation_not_math_truth(grade, term):
    result = {
        "expression": "x**2",
        "domain": "Reals",
        "verification": {"status": "verified"},
        "capabilities_v2": {"tools": {"line": True}},
        "analysis_steps": [
            {"key": "derivative", "order": 1, "title": "Đạo hàm", "status": "complete", "evidence": ["2*x"], "warnings": []},
            {"key": "domain", "order": 2, "title": "Tập xác định", "status": "complete", "evidence": ["R"], "warnings": []},
        ],
    }
    profile = CurriculumProfile(grade=grade, chapter="Fixture", explanation_level="standard")

    presentation = build_curriculum_presentation(profile, result)
    output = apply_curriculum_profile(result, profile)

    assert term in presentation.terminology.values()
    assert presentation.step_order
    assert presentation.common_mistakes
    assert presentation.predicted_questions
    assert output["expression"] == result["expression"]
    assert output["domain"] == result["domain"]
    assert output["verification"] == result["verification"]
    assert output["capabilities_v2"] == result["capabilities_v2"]
    assert result.get("curriculum_presentation") is None


def test_analyzer_export_preserves_warning_and_exact_approx_metadata():
    result = {
        "expression": "sqrt(2)*x",
        "expression_latex": r"\sqrt{2}x",
        "verification": {"status": "partially_verified"},
        "warnings": ["Nghiệm số chỉ là evidence gần đúng."],
        "analysis_steps": [{
            "key": "roots",
            "title": "Nghiệm",
            "status": "partial",
            "formula_latex": "x=0",
            "evidence": ["Một nghiệm đã kiểm chứng."],
            "warnings": ["Có thể chưa đầy đủ."],
        }],
        "x_value": {"exact": "sqrt(2)", "latex": r"\sqrt{2}", "approx": 1.414, "precision": 4, "method": "symbolic"},
    }
    document = build_analyzer_export_document(
        result,
        engine_version="function-analyzer-v2",
        template="teacher_report",
        profile=CurriculumProfile(),
    )

    assert document.warnings == ["Nghiệm số chỉ là evidence gần đúng."]
    assert document.exact_approx_metadata[0]["exact"] == "sqrt(2)"
    markdown, media_type, filename = render_analyzer_export(document, "markdown")
    assert "Có thể chưa đầy đủ." in markdown.decode()
    assert media_type.startswith("text/markdown")
    assert filename.endswith(".md")
    json.loads(render_analyzer_export(document, "json")[0])


def test_analyzer_export_requires_exactly_one_owned_source():
    with pytest.raises(ValidationError):
        AnalyzerExportRequest(format="json")
    with pytest.raises(ValidationError):
        AnalyzerExportRequest(analysis_id="a" * 16, history_id="b" * 16, format="json")


def test_analyzer_history_tags_are_bounded_and_deduplicated():
    assert normalize_tags([" Ôn thi ", "ôn thi", "", "x" * 33, "Đạo hàm"]) == ["ôn thi", "đạo hàm"]


@pytest.mark.anyio
async def test_history_reopen_reuses_saved_evidence_without_solver(tmp_path, monkeypatch):
    db = SQLiteClient(str(tmp_path / "history.db"))
    await apply_sqlite_migrations(db)
    await db.execute("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)", ["user-1", "u@example.com", "hash"])
    user = UserRecord(
        id="user-1",
        email="u@example.com",
        password_hash="hash",
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )
    request = Request({
        "type": "http", "method": "GET", "path": "/api/analyzer/history", "headers": [],
        "query_string": b"", "server": ("test", 80), "client": ("127.0.0.1", 1), "scheme": "http", "root_path": "",
    })
    result = AnalyzeResponse(expression="x**2", domain="Reals", warnings=[]).model_dump(mode="json")
    session = create_analysis_session(analysis_scope(user.id, request), result)
    item = await create_analyzer_history(
        AnalyzerHistoryCreateRequest(analysis_id=session.analysis_id), request, user, db
    )

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Reopen không được chạy solver.")

    monkeypatch.setattr("app.api.routes_analyzer_history.run_cached_analysis", fail_if_called)
    detail = await get_analyzer_history(item.id, request, user, db)

    assert detail.result.expression == "x**2"
    assert detail.result.domain == "Reals"
    assert detail.result.analysis_id != session.analysis_id
    clear_runtime_state()
    await db.close()


class FakeHistoryDb:
    def __init__(self):
        self.sql = ""
        self.params = []

    async def fetch_all(self, sql, params):
        self.sql = sql
        self.params = params
        return [{
            "id": "history-1",
            "user_id": "user-1",
            "original_expression": "x^2",
            "canonical_expression": "x**2",
            "parameter_json": "{}",
            "tags_json": '["ôn thi"]',
            "is_pinned": 1,
            "grade": 12,
            "chapter": "Khảo sát hàm số",
            "explanation_level": "standard",
            "engine_version": "v2",
            "schema_version": "v2",
            "parent_history_id": None,
            "last_opened_at": None,
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }]


@pytest.mark.anyio
async def test_analyzer_history_list_omits_heavy_result_json():
    db = FakeHistoryDb()
    rows = await AnalyzerHistoryRepository(db).list_for_user("user-1", q="x", tag="ôn thi", pinned=True)

    selected = db.sql.lower().split("from analyzer_history", 1)[0]
    assert "result_json" not in selected
    assert "verification_json" not in selected
    assert rows[0]["pinned"] is True