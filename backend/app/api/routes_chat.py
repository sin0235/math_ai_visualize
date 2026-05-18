from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, status

from app.api.deps import enforce_rate_limit, origin_allowed, require_active_user, require_admin_user, require_trusted_origin
from app.core.config import Settings, get_settings
from app.db.models import ChatConversationRecord, ChatMessageRecord, UserRecord
from app.db.session import DatabaseClient, get_database
from app.repositories.admin import AdminRepository
from app.repositories.auth import UserRepository
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatConversationDetailResponse, ChatConversationResponse, ChatMessageCreateRequest, ChatMessageResponse, ChatWsTicketResponse
from app.services.chat_ws import chat_ws_manager, chat_ws_tickets
from app.services.cloudinary_uploads import CloudinaryUploadError, upload_chat_image

router = APIRouter(tags=["chat"])


@router.get("/api/chat/conversation", response_model=ChatConversationDetailResponse)
async def get_chat_conversation(user: UserRecord = Depends(require_active_user), db: DatabaseClient = Depends(get_database)) -> ChatConversationDetailResponse:
    repo = ChatRepository(db)
    conversation = await repo.get_or_create_open_conversation(user.id)
    messages = await repo.list_messages(conversation.id)
    return detail_response(conversation, messages)


@router.get("/api/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def get_chat_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    before: str | None = Query(default=None, max_length=64),
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> list[ChatMessageResponse]:
    repo = ChatRepository(db)
    conversation = await require_user_conversation(repo, conversation_id, user.id)
    messages = await repo.list_messages(conversation.id, limit, before)
    return [message_response(message) for message in messages]


@router.post("/api/chat/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, dependencies=[Depends(require_trusted_origin)])
async def send_chat_message(
    conversation_id: str,
    request: ChatMessageCreateRequest,
    raw_request: Request,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatMessageResponse:
    await enforce_rate_limit(db, raw_request, user, "chat_user_send", 20, 60)
    repo = ChatRepository(db)
    conversation = await require_user_conversation(repo, conversation_id, user.id)
    if conversation.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cuộc trò chuyện đã đóng.")
    message = await repo.create_message(conversation.id, user.id, "user", request.body)
    updated = await repo.find_conversation(conversation.id) or conversation
    payload = {"type": "message.created", "conversation_id": conversation.id, "message": message_response(message).model_dump(), "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.broadcast_conversation_event(conversation.user_id, payload)
    return message_response(message)


@router.post("/api/chat/conversations/{conversation_id}/messages/image", response_model=ChatMessageResponse, dependencies=[Depends(require_trusted_origin)])
async def send_chat_image_message(
    conversation_id: str,
    raw_request: Request,
    caption: str | None = Form(default=None, max_length=2000),
    file: UploadFile = File(...),
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ChatMessageResponse:
    await enforce_rate_limit(db, raw_request, user, "chat_user_image_send", 10, 60)
    repo = ChatRepository(db)
    conversation = await require_user_conversation(repo, conversation_id, user.id)
    if conversation.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cuộc trò chuyện đã đóng.")
    try:
        image = await upload_chat_image(file, settings, conversation.id)
    except CloudinaryUploadError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    message = await repo.create_image_message(conversation.id, user.id, "user", clean_caption(caption), image.secure_url, image.public_id, image.width, image.height, image.bytes, image.format, file.filename)
    updated = await repo.find_conversation(conversation.id) or conversation
    payload = {"type": "message.created", "conversation_id": conversation.id, "message": message_response(message).model_dump(), "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.broadcast_conversation_event(conversation.user_id, payload)
    return message_response(message)


@router.post("/api/chat/conversations/{conversation_id}/read", response_model=ChatConversationResponse, dependencies=[Depends(require_trusted_origin)])
async def mark_chat_read(
    conversation_id: str,
    user: UserRecord = Depends(require_active_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatConversationResponse:
    repo = ChatRepository(db)
    conversation = await require_user_conversation(repo, conversation_id, user.id)
    updated = await repo.mark_read_for_user(conversation.id, user.id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    payload = {"type": "conversation.read", "conversation_id": updated.id, "reader_role": "user", "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.send_to_admins(payload)
    return conversation_response(updated)


@router.post("/api/chat/ws-ticket", response_model=ChatWsTicketResponse, dependencies=[Depends(require_trusted_origin)])
async def create_chat_ws_ticket(user: UserRecord = Depends(require_active_user)) -> ChatWsTicketResponse:
    ticket = chat_ws_tickets.create(user.id)
    return ChatWsTicketResponse(ticket=ticket.value, expires_at=ticket.expires_at.isoformat())


@router.get("/api/admin/chat/conversations", response_model=list[ChatConversationResponse])
async def admin_chat_conversations(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    q: str | None = Query(default=None, max_length=256),
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> list[ChatConversationResponse]:
    if status_filter not in {None, "open", "closed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trạng thái chat không hợp lệ.")
    rows = await ChatRepository(db).list_admin_conversations(status_filter, q)
    return [conversation_response(conversation, email, display_name, unread_count, latest) for conversation, email, display_name, unread_count, latest in rows]


@router.get("/api/admin/chat/conversations/{conversation_id}", response_model=ChatConversationDetailResponse)
async def admin_chat_conversation(
    conversation_id: str,
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatConversationDetailResponse:
    repo = ChatRepository(db)
    conversation = await repo.find_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    messages = await repo.list_messages(conversation.id)
    return detail_response(conversation, messages)


@router.post("/api/admin/chat/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_send_chat_message(
    conversation_id: str,
    request: ChatMessageCreateRequest,
    raw_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatMessageResponse:
    await enforce_rate_limit(db, raw_request, admin, "admin_chat_send", 60, 60)
    repo = ChatRepository(db)
    conversation = await repo.find_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    if conversation.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cuộc trò chuyện đã đóng.")
    await repo.assign_admin_if_empty(conversation.id, admin.id)
    message = await repo.create_message(conversation.id, admin.id, "admin", request.body)
    updated = await repo.find_conversation(conversation.id) or conversation
    await AdminRepository(db).audit(admin.id, "admin.chat.reply", "chat_conversation", conversation.id, {"message_id": message.id, "body_length": len(request.body)})
    payload = {"type": "message.created", "conversation_id": conversation.id, "message": message_response(message).model_dump(), "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.broadcast_conversation_event(conversation.user_id, payload)
    return message_response(message)


@router.post("/api/admin/chat/conversations/{conversation_id}/messages/image", response_model=ChatMessageResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_send_chat_image_message(
    conversation_id: str,
    raw_request: Request,
    caption: str | None = Form(default=None, max_length=2000),
    file: UploadFile = File(...),
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> ChatMessageResponse:
    await enforce_rate_limit(db, raw_request, admin, "admin_chat_image_send", 20, 60)
    repo = ChatRepository(db)
    conversation = await repo.find_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    if conversation.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cuộc trò chuyện đã đóng.")
    try:
        image = await upload_chat_image(file, settings, conversation.id)
    except CloudinaryUploadError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    await repo.assign_admin_if_empty(conversation.id, admin.id)
    message = await repo.create_image_message(conversation.id, admin.id, "admin", clean_caption(caption), image.secure_url, image.public_id, image.width, image.height, image.bytes, image.format, file.filename)
    updated = await repo.find_conversation(conversation.id) or conversation
    await AdminRepository(db).audit(admin.id, "admin.chat.image", "chat_conversation", conversation.id, {"message_id": message.id, "image_public_id": image.public_id, "image_bytes": image.bytes})
    payload = {"type": "message.created", "conversation_id": conversation.id, "message": message_response(message).model_dump(), "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.broadcast_conversation_event(conversation.user_id, payload)
    return message_response(message)


@router.post("/api/admin/chat/conversations/{conversation_id}/read", response_model=ChatConversationResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_mark_chat_read(
    conversation_id: str,
    _: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatConversationResponse:
    updated = await ChatRepository(db).mark_read_for_admin(conversation_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    payload = {"type": "conversation.read", "conversation_id": updated.id, "reader_role": "admin", "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.send_to_user(updated.user_id, payload)
    return conversation_response(updated)


@router.post("/api/admin/chat/conversations/{conversation_id}/close", response_model=ChatConversationResponse, dependencies=[Depends(require_trusted_origin)])
async def admin_close_chat_conversation(
    conversation_id: str,
    raw_request: Request,
    admin: UserRecord = Depends(require_admin_user),
    db: DatabaseClient = Depends(get_database),
) -> ChatConversationResponse:
    await enforce_rate_limit(db, raw_request, admin, "admin_chat_close", 30, 60)
    repo = ChatRepository(db)
    updated = await repo.close_conversation(conversation_id, admin.id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    await AdminRepository(db).audit(admin.id, "admin.chat.close", "chat_conversation", conversation_id, {})
    payload = {"type": "conversation.updated", "conversation_id": updated.id, "conversation": conversation_response(updated).model_dump()}
    await chat_ws_manager.broadcast_conversation_event(updated.user_id, payload)
    return conversation_response(updated)


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket, db: DatabaseClient = Depends(get_database), settings: Settings = Depends(get_settings)) -> None:
    origin = websocket.headers.get("origin")
    if origin and not origin_allowed(origin, settings.cors_origins):
        await websocket.close(code=1008)
        return
    ticket_value = websocket.query_params.get("ticket")
    if not ticket_value:
        await websocket.close(code=1008)
        return
    ticket = chat_ws_tickets.consume(ticket_value)
    if ticket is None:
        await websocket.close(code=1008)
        return
    user = await UserRepository(db).find_by_id(ticket.user_id)
    if user is None or user.status != "active":
        await websocket.close(code=1008)
        return
    await chat_ws_manager.connect(user, websocket)
    await chat_ws_manager.keepalive(user, websocket)


async def require_user_conversation(repo: ChatRepository, conversation_id: str, user_id: str) -> ChatConversationRecord:
    conversation = await repo.find_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện.")
    if conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập cuộc trò chuyện này.")
    return conversation


def detail_response(conversation: ChatConversationRecord, messages: list[ChatMessageRecord]) -> ChatConversationDetailResponse:
    return ChatConversationDetailResponse(
        conversation=conversation_response(conversation),
        messages=[message_response(message) for message in messages],
    )


def conversation_response(
    conversation: ChatConversationRecord,
    user_email: str | None = None,
    user_display_name: str | None = None,
    unread_count: int = 0,
    latest_message: ChatMessageRecord | None = None,
) -> ChatConversationResponse:
    return ChatConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        status=conversation.status,  # type: ignore[arg-type]
        assigned_admin_id=conversation.assigned_admin_id,
        last_message_at=conversation.last_message_at,
        user_last_read_at=conversation.user_last_read_at,
        admin_last_read_at=conversation.admin_last_read_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        user_email=user_email,
        user_display_name=user_display_name,
        unread_count=unread_count,
        latest_message=message_response(latest_message) if latest_message else None,
    )


def message_response(message: ChatMessageRecord) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        sender_role=message.sender_role,  # type: ignore[arg-type]
        body=message.body,
        created_at=message.created_at,
        message_type=message.message_type,  # type: ignore[arg-type]
        image_url=message.image_url,
        image_public_id=message.image_public_id,
        image_width=message.image_width,
        image_height=message.image_height,
        image_bytes=message.image_bytes,
        image_format=message.image_format,
        image_original_name=message.image_original_name,
    )


def clean_caption(value: str | None) -> str:
    return (value or "").strip()[:2000]
