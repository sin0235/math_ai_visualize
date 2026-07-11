from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.api.routes_analyzer_links import create_analyzer_handoff, create_analyzer_share, consume_analyzer_link, revoke_analyzer_link
from app.core.config import Settings
from app.db.migrations import apply_sqlite_migrations
from app.db.models import UserRecord
from app.db.session import SQLiteClient
from app.repositories.analyzer_links import AnalyzerLinkRepository
from app.schemas.analyzer_links import AnalyzerLinkConsumeRequest, AnalyzerLinkCreateRequest, AnalyzerShareCreateRequest
from app.services.analyzer_handoff import build_analyzer_handoff_payload
from app.services.analyzer_runtime import analysis_scope, clear_runtime_state, create_analysis_session


def _request(path: str, *, origin: str | None = "http://localhost:5173") -> Request:
    headers = [] if origin is None else [(b"origin", origin.encode())]
    return Request({
        "type": "http", "method": "POST", "path": path, "headers": headers,
        "query_string": b"", "server": ("test", 80), "client": ("127.0.0.1", 1),
        "scheme": "http", "root_path": "",
    })


def _user(user_id: str = "user-1") -> UserRecord:
    return UserRecord(
        id=user_id, email=f"{user_id}@example.com", password_hash="hash",
        created_at="2026-01-01", updated_at="2026-01-01",
    )


async def _db(tmp_path) -> SQLiteClient:
    db = SQLiteClient(str(tmp_path / "links.db"))
    await apply_sqlite_migrations(db)
    await db.execute("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)", ["user-1", "u@example.com", "hash"])
    await db.execute("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)", ["user-2", "v@example.com", "hash"])
    return db


def _result() -> dict:
    return {
        "expression": "x**3-3*x",
        "evaluated_expression": "x**3 - 3*x",
        "derivative": "3*x**2 - 3",
        "verification": {"status": "verified"},
        "geogebra_commands": ["f(x)=x^3-3*x"],
        "graph_analysis_v2": {"window": {"x_min": -4, "x_max": 4}},
        "analysis_steps": [{"title": "Đạo hàm", "status": "complete"}],
    }


def test_handoff_payloads_are_versioned_destination_allowlists():
    expected = {
        "algebra_solver": {"version", "input", "input_format", "topic", "domain"},
        "simulation": {"version", "simulation_id", "expression", "x_min", "x_max", "verification_status"},
        "geogebra_lab": {"version", "mode", "commands"},
        "render": {"version", "problem_text", "preferred_renderer"},
        "practice": {"version", "problem_text", "source_verification"},
    }
    for target, keys in expected.items():
        payload = build_analyzer_handoff_payload(target, _result()).model_dump(mode="json")
        assert set(payload) == keys
        assert payload["version"].endswith("-v1")


def test_share_schema_requires_origin_for_embed_and_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        AnalyzerShareCreateRequest(analysis_id="a" * 16, target="render", scopes=["embed"])
    with pytest.raises(ValidationError):
        AnalyzerShareCreateRequest(analysis_id="a" * 16, target="render", scopes=["api"])
    with pytest.raises(ValidationError):
        AnalyzerLinkCreateRequest(analysis_id="a" * 16, target="render", expression="x")


@pytest.mark.anyio
async def test_owner_handoff_is_opaque_and_consumed_once(tmp_path):
    db = await _db(tmp_path)
    user = _user()
    request = _request("/api/analyzer/handoffs")
    session = create_analysis_session(analysis_scope(user.id, request), _result())
    settings = Settings(database_backend="sqlite", sqlite_path=str(tmp_path / "links.db"), public_app_url="https://app.example")

    created = await create_analyzer_handoff(
        AnalyzerLinkCreateRequest(analysis_id=session.analysis_id, target="algebra_solver"),
        request, user, db, settings,
    )

    assert "x**3" not in created.url
    assert created.url == f"https://app.example/algebra-solver?handoff={created.short_id}"
    with pytest.raises(HTTPException) as hidden_from_other_user:
        await consume_analyzer_link(
            created.short_id, AnalyzerLinkConsumeRequest(target="algebra_solver"), request, _user("user-2"), db, settings
        )
    assert hidden_from_other_user.value.status_code == 404
    consumed = await consume_analyzer_link(
        created.short_id, AnalyzerLinkConsumeRequest(target="algebra_solver"), request, user, db, settings
    )
    assert consumed.payload.input == "(3*x**2 - 3) = 0"
    with pytest.raises(HTTPException) as replay:
        await consume_analyzer_link(
            created.short_id, AnalyzerLinkConsumeRequest(target="algebra_solver"), request, user, db, settings
        )
    assert replay.value.status_code == 404

    concurrent = await AnalyzerLinkRepository(db).create(
        user.id, kind="handoff", target="render", payload_version="render-problem-v1",
        payload={"version": "render-problem-v1", "problem_text": "Vẽ y=x", "preferred_renderer": "geogebra"},
        visibility="user", scopes=["open"], allowed_origins=[], expires_in_minutes=5, max_uses=1,
    )
    attempts = await asyncio.gather(
        AnalyzerLinkRepository(db).consume(concurrent["short_id"]),
        AnalyzerLinkRepository(db).consume(concurrent["short_id"]),
    )
    assert sum(item is not None for item in attempts) == 1
    clear_runtime_state()
    await db.close()


@pytest.mark.anyio
async def test_public_share_enforces_scope_origin_quota_and_revoke(tmp_path):
    db = await _db(tmp_path)
    user = _user()
    request = _request("/api/analyzer/shares")
    session = create_analysis_session(analysis_scope(user.id, request), _result())
    settings = Settings(database_backend="sqlite", sqlite_path=str(tmp_path / "links.db"))
    created = await create_analyzer_share(
        AnalyzerShareCreateRequest(
            analysis_id=session.analysis_id,
            target="geogebra_lab",
            visibility="public",
            scopes=["api"],
            allowed_origins=["https://school.example"],
            max_uses=1,
        ),
        request, user, db, settings,
    )
    body = AnalyzerLinkConsumeRequest(target="geogebra_lab", scope="api")

    with pytest.raises(HTTPException) as forbidden:
        await consume_analyzer_link(created.short_id, body, _request("/consume", origin="https://evil.example"), None, db, settings)
    assert forbidden.value.status_code == 403
    consumed = await consume_analyzer_link(
        created.short_id, body, _request("/consume", origin="https://school.example/path"), None, db, settings
    )
    assert consumed.payload.commands == ["f(x)=x^3-3*x"]
    with pytest.raises(HTTPException) as exhausted:
        await consume_analyzer_link(
            created.short_id, body, _request("/consume", origin="https://school.example"), None, db, settings
        )
    assert exhausted.value.status_code == 404

    second = await AnalyzerLinkRepository(db).create(
        user.id, kind="share", target="render", payload_version="render-problem-v1",
        payload={"version": "render-problem-v1", "problem_text": "Vẽ y=x", "preferred_renderer": "geogebra"},
        visibility="public", scopes=["open"], allowed_origins=[], expires_in_minutes=5, max_uses=2,
    )
    await revoke_analyzer_link(second["short_id"], user, db)
    assert await AnalyzerLinkRepository(db).consume(second["short_id"]) is None

    expired = await AnalyzerLinkRepository(db).create(
        user.id, kind="share", target="render", payload_version="render-problem-v1",
        payload={"version": "render-problem-v1", "problem_text": "Vẽ y=x", "preferred_renderer": "geogebra"},
        visibility="public", scopes=["open"], allowed_origins=[], expires_in_minutes=5, max_uses=2,
    )
    await db.execute(
        "UPDATE analyzer_links SET expires_at = ? WHERE short_id = ?",
        [(datetime.now(UTC) - timedelta(minutes=1)).isoformat(), expired["short_id"]],
    )
    assert await AnalyzerLinkRepository(db).consume(expired["short_id"]) is None
    clear_runtime_state()
    await db.close()