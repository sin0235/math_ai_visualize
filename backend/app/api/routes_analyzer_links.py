from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, get_current_user, get_optional_current_user, origin_allowed, require_trusted_origin
from app.api.routes_analyzer_history import _owned_session
from app.core.config import Settings, get_settings
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.analyzer_links import AnalyzerLinkRepository
from app.schemas.analyzer_links import (
    AnalyzerLinkConsumeRequest,
    AnalyzerLinkConsumed,
    AnalyzerLinkCreated,
    AnalyzerLinkCreateRequest,
    AnalyzerShareCreateRequest,
)
from app.services.analyzer_handoff import build_analyzer_handoff_payload

router = APIRouter(prefix="/api/analyzer", tags=["analyzer-links"])

_TARGET_PATHS = {
    "algebra_solver": "/algebra-solver",
    "simulation": "/simulation/g12.calc.derivative-survey",
    "geogebra_lab": "/geogebra-lab",
    "render": "/render",
    "practice": "/practice",
}


@router.post("/handoffs", response_model=AnalyzerLinkCreated, dependencies=[Depends(require_trusted_origin)])
async def create_analyzer_handoff(
    body: AnalyzerLinkCreateRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AnalyzerLinkCreated:
    await enforce_rate_limit(db, request, user, "analyzer_handoff_create", 30, 60, settings)
    session = _owned_session(body.analysis_id, user, request)
    payload = build_analyzer_handoff_payload(body.target, session.result)
    row = await AnalyzerLinkRepository(db).create(
        user.id,
        kind="handoff",
        target=body.target,
        payload_version=payload.version,
        payload=payload.model_dump(mode="json"),
        visibility="user",
        scopes=["open"],
        allowed_origins=[],
        expires_in_minutes=15,
        max_uses=1,
    )
    return _created(row, settings)


@router.post("/shares", response_model=AnalyzerLinkCreated, dependencies=[Depends(require_trusted_origin)])
async def create_analyzer_share(
    body: AnalyzerShareCreateRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AnalyzerLinkCreated:
    await enforce_rate_limit(db, request, user, "analyzer_share_create", 20, 60, settings)
    session = _owned_session(body.analysis_id, user, request)
    payload = build_analyzer_handoff_payload(body.target, session.result)
    origins = [_origin(str(value)) for value in body.allowed_origins]
    row = await AnalyzerLinkRepository(db).create(
        user.id,
        kind="share",
        target=body.target,
        payload_version=payload.version,
        payload=payload.model_dump(mode="json"),
        visibility=body.visibility,
        scopes=body.scopes,
        allowed_origins=list(dict.fromkeys(origins)),
        expires_in_minutes=body.expires_in_minutes,
        max_uses=body.max_uses,
    )
    return _created(row, settings)


@router.post("/links/{short_id}/consume", response_model=AnalyzerLinkConsumed, dependencies=[Depends(require_trusted_origin)])
async def consume_analyzer_link(
    short_id: str,
    body: AnalyzerLinkConsumeRequest,
    request: Request,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AnalyzerLinkConsumed:
    if len(short_id) < 12 or len(short_id) > 64:
        raise _not_found()
    await enforce_rate_limit(db, request, user, "analyzer_link_consume", 60, 60, settings)
    repo = AnalyzerLinkRepository(db)
    current = await repo.find(short_id)
    if current is None or current["target"] != body.target or body.scope not in current["scopes"]:
        raise _not_found()
    if current["visibility"] == "user" and (user is None or user.id != current["owner_user_id"]):
        raise _not_found()
    if current["visibility"] == "public" and body.scope in {"api", "embed"}:
        source = request.headers.get("origin") or request.headers.get("referer") or ""
        if not source or not origin_allowed(source, current["allowed_origins"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nguồn yêu cầu không thuộc allowlist của share.")
    row = await repo.consume(short_id)
    if row is None:
        raise _not_found()
    return AnalyzerLinkConsumed(
        short_id=short_id,
        kind=row["kind"],
        target=row["target"],
        payload_version=row["payload_version"],
        payload=row["payload"],
        expires_at=str(row["expires_at"]),
    )


@router.delete("/links/{short_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_trusted_origin)])
async def revoke_analyzer_link(
    short_id: str,
    user: UserRecord = Depends(get_current_user),
    db: DatabaseClient = Depends(get_database),
) -> None:
    if not await AnalyzerLinkRepository(db).revoke(user.id, short_id):
        raise _not_found()


def _created(row: dict, settings: Settings) -> AnalyzerLinkCreated:
    query_key = "handoff" if row["kind"] == "handoff" else "share"
    path = _TARGET_PATHS[row["target"]]
    url = f"{settings.public_app_url.rstrip('/')}{path}?{query_key}={row['short_id']}"
    return AnalyzerLinkCreated(
        short_id=row["short_id"],
        kind=row["kind"],
        target=row["target"],
        url=url,
        expires_at=str(row["expires_at"]),
        visibility=row["visibility"],
        scopes=row["scopes"],
    )


def _origin(value: str) -> str:
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link analyzer không tồn tại hoặc không còn hiệu lực.")