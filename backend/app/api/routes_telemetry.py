from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import enforce_rate_limit, get_optional_current_user, origin_allowed, require_trusted_origin
from app.core.config import Settings, get_settings
from app.core.logging import get_request_id
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.activity import try_log_user_activity
from app.repositories.errors import try_record_error_event
from app.services.analytics_taxonomy import ALLOWED_CLIENT_EVENT_TYPES, FEATURE_KEYS, FEATURE_OPEN, PAGE_VIEW
from app.services.provider_logging import redact_sensitive

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

_ALLOWED_METADATA_KEYS = frozenset({
    "component",
    "title",
    "client_session_id",
    "pathname",
    "kind",
    "feature",
    "path",
    "referrer_path",
})


class ClientErrorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    error_code: str | None = Field(default=None, max_length=80)
    stack: str | None = Field(default=None, max_length=4000)
    route: str | None = Field(default=None, max_length=300)
    component: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=80)
    metadata: dict | None = None

    @field_validator("metadata")
    @classmethod
    def limit_metadata(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            return {}
        # Cap size: at most 12 keys, string values truncated.
        out: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 12:
                break
            key_text = str(key)[:80]
            if isinstance(item, (str, int, float, bool)) or item is None:
                out[key_text] = item if not isinstance(item, str) else item[:300]
            else:
                out[key_text] = str(item)[:300]
        return out


@router.post("/client-error", dependencies=[Depends(require_trusted_origin)])
async def report_client_error(
    body: ClientErrorRequest,
    request: Request,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not settings.telemetry_client_enabled:
        return {"status": "disabled"}
    # require_trusted_origin only enforces when a session cookie is present; also gate guests by Origin.
    origin = request.headers.get("origin")
    if origin and not origin_allowed(origin, settings.cors_origins):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nguồn yêu cầu không được phép.")
    await enforce_rate_limit(db, request, user, "telemetry_client_error", 30 if user else 15, 60, settings)

    safe_meta = _sanitize_client_metadata(body.metadata)
    if body.component:
        safe_meta["component"] = body.component[:120]
    ua = (request.headers.get("user-agent") or "")[:200]
    if ua:
        safe_meta["user_agent"] = ua

    message = redact_sensitive(body.message)[:1000]
    stack = redact_sensitive(body.stack)[:4000] if body.stack else None

    await try_record_error_event(
        db,
        message=message,
        source="client",
        request_id=body.request_id or get_request_id(),
        user_id=user.id if user else None,
        route=(body.route or str(request.url.path))[:300],
        method="CLIENT",
        status_code=None,
        error_code=body.error_code or "CLIENT_ERROR",
        stack=stack,
        metadata=safe_meta,
    )
    return {"status": "ok"}


def _sanitize_client_metadata(metadata: dict | None) -> dict[str, object]:
    if not metadata:
        return {}
    out: dict[str, object] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if key_text not in _ALLOWED_METADATA_KEYS and key_text != "href":
            continue
        if key_text == "href" and isinstance(value, str):
            out["pathname"] = _strip_url_query(value)[:300]
            continue
        if key_text in _ALLOWED_METADATA_KEYS:
            if isinstance(value, str):
                out[key_text] = value[:300]
            elif isinstance(value, (int, float, bool)) or value is None:
                out[key_text] = value
            else:
                out[key_text] = str(value)[:300]
    return out


def _strip_url_query(url: str) -> str:
    try:
        parts = urlsplit(url)
        # Drop query and fragment (tokens, email params, etc.)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url.split("?", 1)[0].split("#", 1)[0]


class ClientEventItem(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    path: str | None = Field(default=None, max_length=300)
    feature: str | None = Field(default=None, max_length=64)
    metadata: dict | None = None


class ClientEventsRequest(BaseModel):
    events: list[ClientEventItem] = Field(default_factory=list, max_length=40)
    client_session_id: str | None = Field(default=None, max_length=80)


@router.post("/events", dependencies=[Depends(require_trusted_origin)])
async def report_client_events(
    body: ClientEventsRequest,
    request: Request,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    if not settings.telemetry_client_enabled:
        return {"status": "disabled", "accepted": 0}
    origin = request.headers.get("origin")
    if origin and not origin_allowed(origin, settings.cors_origins):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nguồn yêu cầu không được phép.")
    await enforce_rate_limit(db, request, user, "telemetry_events", 60 if user else 30, 60, settings)

    # Anonymous page views are stored only when user is logged in (product analytics).
    if user is None:
        return {"status": "ok", "accepted": 0, "note": "login_required_for_activity"}

    accepted = 0
    for item in body.events[:40]:
        event_type = item.event_type.strip()
        if event_type not in ALLOWED_CLIENT_EVENT_TYPES:
            continue
        meta = _sanitize_client_metadata(item.metadata)
        if body.client_session_id:
            meta["client_session_id"] = body.client_session_id[:80]
        if item.path:
            meta["path"] = item.path[:300]
        if item.feature:
            feature = item.feature.strip()
            if feature not in FEATURE_KEYS:
                continue
            meta["feature"] = feature
        if event_type == FEATURE_OPEN and "feature" not in meta:
            continue
        if event_type == PAGE_VIEW and "path" not in meta and item.path:
            meta["path"] = item.path[:300]
        await try_log_user_activity(
            db,
            user.id,
            event_type,
            target_type="feature" if event_type == FEATURE_OPEN else "page",
            target_id=str(meta.get("feature") or meta.get("path") or "")[:120] or None,
            metadata=meta,
            session_id=body.client_session_id,
            source="client",
        )
        accepted += 1
    return {"status": "ok", "accepted": accepted}
