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


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    token_hash: str
    expires_at: str
    created_at: str


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


@dataclass(frozen=True)
class UserSettingsRecord:
    user_id: str
    settings_json: str
    updated_at: str
