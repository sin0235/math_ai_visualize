from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Request

from app.api.deps import enforce_rate_limit, get_optional_current_user
from app.core.config import Settings, get_settings
from app.core.logging import get_request_id
from app.db.models import UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.errors import try_record_error_event

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class ClientErrorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    error_code: str | None = Field(default=None, max_length=80)
    stack: str | None = Field(default=None, max_length=4000)
    route: str | None = Field(default=None, max_length=300)
    component: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=80)
    metadata: dict | None = None


@router.post("/client-error")
async def report_client_error(
    body: ClientErrorRequest,
    request: Request,
    user: UserRecord | None = Depends(get_optional_current_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not settings.telemetry_client_enabled:
        return {"status": "disabled"}
    await enforce_rate_limit(db, request, user, "telemetry_client_error", 30 if user else 15, 60, settings)
    await try_record_error_event(
        db,
        message=body.message,
        source="client",
        request_id=body.request_id or get_request_id(),
        user_id=user.id if user else None,
        route=body.route or str(request.url.path),
        method="CLIENT",
        status_code=None,
        error_code=body.error_code or "CLIENT_ERROR",
        stack=body.stack,
        metadata={
            "component": body.component,
            "user_agent": (request.headers.get("user-agent") or "")[:200],
            **(body.metadata or {}),
        },
    )
    return {"status": "ok"}
