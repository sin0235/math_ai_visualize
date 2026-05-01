from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.scene import MathScene, RenderPayload


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str


class AuthResponse(BaseModel):
    user: UserResponse


class RenderHistoryItem(BaseModel):
    id: str
    problem_text: str
    provider: str | None = None
    model: str | None = None
    created_at: str


class RenderHistoryDetail(RenderHistoryItem):
    scene: MathScene
    payload: RenderPayload
    warnings: list[str]


class UserSettingsResponse(BaseModel):
    settings: dict[str, Any] | None = None
    updated_at: str | None = None


class UserSettingsRequest(BaseModel):
    settings: dict[str, Any]
