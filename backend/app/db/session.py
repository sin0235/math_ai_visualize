from pathlib import Path
from typing import Any, Protocol

import aiosqlite
import httpx
from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.db.models import DbRow


class DatabaseClient(Protocol):
    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None: ...
    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None: ...
    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]: ...


class SQLiteClient:
    backend = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute(sql, params or [])
            await db.commit()

    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params or [])
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params or [])
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class D1Client:
    backend = "d1"

    def __init__(self, account_id: str, database_id: str, api_token: str) -> None:
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
        self.headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        await self._query(sql, params)

    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None:
        rows = await self._query(sql, params)
        return rows[0] if rows else None

    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        return await self._query(sql, params)

    async def _query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        payload = {"sql": sql, "params": list(params or [])}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.url, headers=self.headers, json=payload)
        response.raise_for_status()
        body = response.json()
        if not body.get("success", False):
            errors = body.get("errors") or []
            message = errors[0].get("message") if errors and isinstance(errors[0], dict) else "Cloudflare D1 query failed."
            raise RuntimeError(message)
        result = body.get("result") or []
        if not result:
            return []
        rows = result[0].get("results") or []
        return [dict(row) for row in rows]


def create_database_client(settings: Settings) -> DatabaseClient:
    if settings.database_backend == "sqlite":
        return SQLiteClient(settings.sqlite_path)
    if settings.database_backend == "d1":
        if not settings.d1_account_id or not settings.d1_database_id or not settings.d1_api_token:
            raise RuntimeError("D1 is selected but D1_ACCOUNT_ID, D1_DATABASE_ID, or D1_API_TOKEN is missing.")
        return D1Client(settings.d1_account_id, settings.d1_database_id, settings.d1_api_token)
    raise RuntimeError(f"Unsupported database backend: {settings.database_backend}")


async def get_database(settings: Settings = Depends(get_settings)) -> DatabaseClient:
    try:
        return create_database_client(settings)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
