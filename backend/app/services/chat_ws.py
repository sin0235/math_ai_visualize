from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.db.models import UserRecord


@dataclass(frozen=True)
class ChatWsTicket:
    value: str
    user_id: str
    expires_at: datetime


class ChatWsTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, ChatWsTicket] = {}

    def create(self, user_id: str, ttl_seconds: int = 60) -> ChatWsTicket:
        self._cleanup()
        value = token_urlsafe(32)
        ticket = ChatWsTicket(value=value, user_id=user_id, expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds))
        self._tickets[value] = ticket
        return ticket

    def consume(self, value: str) -> ChatWsTicket | None:
        self._cleanup()
        ticket = self._tickets.pop(value, None)
        if ticket is None or ticket.expires_at <= datetime.now(UTC):
            return None
        return ticket

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        expired = [value for value, ticket in self._tickets.items() if ticket.expires_at <= now]
        for value in expired:
            self._tickets.pop(value, None)


class ChatWebSocketManager:
    def __init__(self) -> None:
        self._user_connections: dict[str, set[WebSocket]] = {}
        self._admin_connections: set[WebSocket] = set()

    async def connect(self, user: UserRecord, websocket: WebSocket) -> None:
        await websocket.accept()
        self._user_connections.setdefault(user.id, set()).add(websocket)
        if user.role == "admin":
            self._admin_connections.add(websocket)
        await self._safe_send(websocket, {"type": "connected", "user_id": user.id, "role": user.role})

    def disconnect(self, user: UserRecord, websocket: WebSocket) -> None:
        user_connections = self._user_connections.get(user.id)
        if user_connections is not None:
            user_connections.discard(websocket)
            if not user_connections:
                self._user_connections.pop(user.id, None)
        self._admin_connections.discard(websocket)

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        await self._send_many(list(self._user_connections.get(user_id, set())), payload)

    async def send_to_admins(self, payload: dict) -> None:
        await self._send_many(list(self._admin_connections), payload)

    async def broadcast_conversation_event(self, user_id: str, payload: dict) -> None:
        await self.send_to_user(user_id, payload)
        await self.send_to_admins(payload)

    async def keepalive(self, user: UserRecord, websocket: WebSocket) -> None:
        try:
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    continue
                if message.get("type") == "ping":
                    await self._safe_send(websocket, {"type": "pong"})
                if message.get("type") == "typing":
                    conversation_id = str(message.get("conversation_id") or "")
                    target_user_id = str(message.get("target_user_id") or "")
                    is_typing = bool(message.get("is_typing"))
                    if not conversation_id:
                        continue
                    payload = {"type": "typing", "conversation_id": conversation_id, "user_id": user.id, "role": user.role, "is_typing": is_typing}
                    if user.role == "admin" and target_user_id:
                        await self.send_to_user(target_user_id, payload)
                    elif user.role != "admin":
                        await self.send_to_admins(payload)
        except WebSocketDisconnect:
            self.disconnect(user, websocket)

    async def _send_many(self, websockets: list[WebSocket], payload: dict) -> None:
        for websocket in websockets:
            await self._safe_send(websocket, payload)

    async def _safe_send(self, websocket: WebSocket, payload: dict) -> None:
        try:
            await websocket.send_json(payload)
        except RuntimeError:
            self._drop(websocket)

    def _drop(self, websocket: WebSocket) -> None:
        for user_id, connections in list(self._user_connections.items()):
            connections.discard(websocket)
            if not connections:
                self._user_connections.pop(user_id, None)
        self._admin_connections.discard(websocket)


chat_ws_manager = ChatWebSocketManager()
chat_ws_tickets = ChatWsTicketStore()
