from typing import Literal

from pydantic import BaseModel, Field, field_validator

ChatStatus = Literal["open", "closed"]
ChatSenderRole = Literal["user", "admin", "system"]
ChatMessageType = Literal["text", "image"]


class ChatMessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def trim_body(cls, value: str) -> str:
        return value.strip()


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    sender_role: ChatSenderRole
    body: str
    created_at: str
    message_type: ChatMessageType = "text"
    image_url: str | None = None
    image_public_id: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    image_bytes: int | None = None
    image_format: str | None = None
    image_original_name: str | None = None


class ChatConversationResponse(BaseModel):
    id: str
    user_id: str
    status: ChatStatus
    assigned_admin_id: str | None = None
    last_message_at: str
    user_last_read_at: str | None = None
    admin_last_read_at: str | None = None
    created_at: str
    updated_at: str
    user_email: str | None = None
    user_display_name: str | None = None
    unread_count: int = 0
    latest_message: ChatMessageResponse | None = None


class ChatConversationDetailResponse(BaseModel):
    conversation: ChatConversationResponse
    messages: list[ChatMessageResponse]


class ChatWsTicketResponse(BaseModel):
    ticket: str
    expires_at: str
