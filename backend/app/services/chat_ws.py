from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.db.models import UserRecord

logger = logging.getLogger(__name__)

WS_CHANNEL = "chat_ws:events"


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

    async def create_async(self, user_id: str, ttl_seconds: int = 60) -> ChatWsTicket:
        ticket = self.create(user_id, ttl_seconds)
        try:
            from app.services.redis_client import get_redis

            redis = await get_redis()
            if redis is not None:
                await redis.setex(f"chat_ws_ticket:{ticket.value}", ttl_seconds, user_id)
        except Exception:
            logger.debug("Redis ticket store failed", exc_info=True)
        return ticket

    async def consume_async(self, value: str) -> ChatWsTicket | None:
        ticket = self.consume(value)
        if ticket is not None:
            return ticket
        try:
            from app.services.redis_client import get_redis

            redis = await get_redis()
            if redis is None:
                return None
            user_id = await redis.get(f"chat_ws_ticket:{value}")
            if not user_id:
                return None
            await redis.delete(f"chat_ws_ticket:{value}")
            return ChatWsTicket(value=value, user_id=str(user_id), expires_at=datetime.now(UTC) + timedelta(seconds=1))
        except Exception:
            logger.debug("Redis ticket consume failed", exc_info=True)
            return None

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        expired = [value for value, ticket in self._tickets.items() if ticket.expires_at <= now]
        for value in expired:
            self._tickets.pop(value, None)


class ChatWebSocketManager:
    def __init__(self) -> None:
        self._user_connections: dict[str, set[WebSocket]] = {}
        self._admin_connections: set[WebSocket] = set()
        self._subscriber_task: asyncio.Task | None = None
        self._instance_id = token_urlsafe(8)

    async def connect(self, user: UserRecord, websocket: WebSocket) -> None:
        await websocket.accept()
        self._user_connections.setdefault(user.id, set()).add(websocket)
        if user.role == "admin":
            self._admin_connections.add(websocket)
        await self._safe_send(websocket, {"type": "connected", "user_id": user.id, "role": user.role})
        await self.ensure_subscriber()

    def disconnect(self, user: UserRecord, websocket: WebSocket) -> None:
        user_connections = self._user_connections.get(user.id)
        if user_connections is not None:
            user_connections.discard(websocket)
            if not user_connections:
                self._user_connections.pop(user.id, None)
        self._admin_connections.discard(websocket)

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        await self._send_many(list(self._user_connections.get(user_id, set())), payload)
        await self._publish({"scope": "user", "user_id": user_id, "payload": payload})

    async def send_to_admins(self, payload: dict) -> None:
        await self._send_many(list(self._admin_connections), payload)
        await self._publish({"scope": "admins", "payload": payload})

    async def broadcast_conversation_event(self, user_id: str, payload: dict) -> None:
        await self._send_many(list(self._user_connections.get(user_id, set())), payload)
        await self._send_many(list(self._admin_connections), payload)
        await self._publish({"scope": "conversation", "user_id": user_id, "payload": payload})

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

    async def ensure_subscriber(self) -> None:
        if self._subscriber_task is not None and not self._subscriber_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._subscriber_task = loop.create_task(self._subscribe_loop())
        except RuntimeError:
            return

    async def _publish(self, message: dict) -> None:
        try:
            from app.services.redis_client import get_redis

            redis = await get_redis()
            if redis is None:
                return
            envelope = {**message, "origin": self._instance_id}
            await redis.publish(WS_CHANNEL, json.dumps(envelope, ensure_ascii=False))
        except Exception:
            logger.debug("WS redis publish skipped", exc_info=True)

    async def _subscribe_loop(self) -> None:
        try:
            from app.services.redis_client import get_redis

            redis = await get_redis()
            if redis is None:
                return
            pubsub = redis.pubsub()
            await pubsub.subscribe(WS_CHANNEL)
            async for item in pubsub.listen():
                if item is None or item.get("type") != "message":
                    continue
                raw = item.get("data")
                if not raw:
                    continue
                try:
                    message = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                except (json.JSONDecodeError, AttributeError):
                    continue
                if message.get("origin") == self._instance_id:
                    continue
                await self._deliver_remote(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("WS redis subscribe ended", exc_info=True)

    async def _deliver_remote(self, message: dict) -> None:
        scope = message.get("scope")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        if scope == "user":
            user_id = str(message.get("user_id") or "")
            await self._send_many(list(self._user_connections.get(user_id, set())), payload)
        elif scope == "admins":
            await self._send_many(list(self._admin_connections), payload)
        elif scope == "conversation":
            user_id = str(message.get("user_id") or "")
            await self._send_many(list(self._user_connections.get(user_id, set())), payload)
            await self._send_many(list(self._admin_connections), payload)

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
