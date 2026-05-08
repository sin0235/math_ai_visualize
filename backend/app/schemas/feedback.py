from typing import Literal

from pydantic import BaseModel, Field, field_validator

FeedbackStatus = Literal["pending", "received", "accepted"]


class FeedbackCreateRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("subject", "message")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class FeedbackResponse(BaseModel):
    id: str
    subject: str
    message: str
    status: FeedbackStatus
    admin_note: str | None = None
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class FeedbackStatusResponse(BaseModel):
    can_submit: bool
    pending_feedback: FeedbackResponse | None = None
    latest_feedback: FeedbackResponse | None = None


class AdminFeedbackResponse(FeedbackResponse):
    user_id: str
    user_email: str | None = None
    resolved_by: str | None = None


class AdminFeedbackUpdateRequest(BaseModel):
    status: Literal["received", "accepted"]
    admin_note: str | None = Field(default=None, max_length=1000)

    @field_validator("admin_note")
    @classmethod
    def trim_admin_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None
