from dataclasses import dataclass
from typing import Any


DbRow = dict[str, Any]


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    password_hash: str
    created_at: str
    updated_at: str
    role: str = "user"
    status: str = "active"
    display_name: str | None = None
    last_login_at: str | None = None
    plan: str = "free"
    email_verified_at: str | None = None
    password_changed_at: str | None = None
    failed_login_count: int = 0
    locked_until: str | None = None
    last_failed_login_at: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    token_hash: str
    expires_at: str
    created_at: str
    last_seen_at: str | None = None
    revoked_at: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class AuthTokenRecord:
    id: str
    user_id: str
    purpose: str
    token_hash: str
    expires_at: str
    consumed_at: str | None
    created_at: str
    created_ip: str | None = None
    user_agent: str | None = None
    otp_hash: str | None = None
    otp_attempts: int = 0
    max_otp_attempts: int = 5


@dataclass(frozen=True)
class LegalAcceptanceRecord:
    id: str
    user_id: str
    document_type: str
    document_version: str
    accepted_at: str
    accepted_ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class OAuthIdentityRecord:
    id: str
    user_id: str
    provider: str
    provider_subject: str
    email: str
    email_verified: bool
    created_at: str
    updated_at: str
    display_name: str | None = None
    picture_url: str | None = None


@dataclass(frozen=True)
class OAuthStateRecord:
    state_hash: str
    provider: str
    expires_at: str
    created_at: str
    redirect_after: str | None = None
    consumed_at: str | None = None
    created_ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class RenderJobRecord:
    id: str
    user_id: str | None
    problem_text: str
    provider: str | None
    model: str | None
    scene_json: str
    payload_json: str
    warnings_json: str
    created_at: str
    render_request_json: str | None = None
    advanced_settings_json: str | None = None
    runtime_settings_json: str | None = None
    source_type: str = "problem"
    renderer: str | None = None


@dataclass(frozen=True)
class UserSettingsRecord:
    user_id: str
    settings_json: str
    updated_at: str


@dataclass(frozen=True)
class SystemSettingsRecord:
    key: str
    value_json: str
    updated_by: str | None
    updated_at: str


@dataclass(frozen=True)
class AuditLogRecord:
    id: str
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str | None
    metadata_json: str
    created_at: str
