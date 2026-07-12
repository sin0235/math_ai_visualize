from __future__ import annotations

import asyncio
from pathlib import Path
from sqlite3 import IntegrityError
from typing import Any, Protocol

import aiosqlite
import httpx
from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.db.models import DbRow

_shared_client: DatabaseClient | None = None
_shared_client_key: str | None = None
_shared_lock = asyncio.Lock()


class DatabaseClient(Protocol):
    backend: str

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None: ...
    async def execute_many(self, statements: list[tuple[str, list[Any] | tuple[Any, ...] | None]]) -> None: ...
    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None: ...
    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]: ...

    async def close(self) -> None: ...

    def pool_stats(self) -> dict[str, Any]: ...


class SQLiteClient:
    backend = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = str(resolve_sqlite_path(path))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()

    async def _ensure_connection(self) -> aiosqlite.Connection:
        if self._db is not None:
            return self._db
        async with self._init_lock:
            if self._db is not None:
                return self._db
            db = await aiosqlite.connect(self.path)
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            db.row_factory = aiosqlite.Row
            self._db = db
            return db

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        await self.execute_many([(sql, params)])

    async def execute_many(self, statements: list[tuple[str, list[Any] | tuple[Any, ...] | None]]) -> None:
        # Long-lived connection: do not issue explicit BEGIN (aiosqlite already
        # opens a transaction on first execute; nested BEGIN fails).
        async with self._lock:
            db = await self._ensure_connection()
            try:
                for sql, params in statements:
                    await db.execute(sql, params or [])
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None:
        async with self._lock:
            db = await self._ensure_connection()
            cursor = await db.execute(sql, params or [])
            row = await cursor.fetchone()
            # End any implicit read transaction so writers are not blocked.
            await db.commit()
            return dict(row) if row else None

    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        async with self._lock:
            db = await self._ensure_connection()
            cursor = await db.execute(sql, params or [])
            rows = await cursor.fetchall()
            await db.commit()
            return [dict(row) for row in rows]

    async def close(self) -> None:
        async with self._init_lock:
            if self._db is not None:
                await self._db.close()
                self._db = None

    def pool_stats(self) -> dict[str, Any]:
        return {"backend": self.backend, "pooled": True, "mode": "single_connection_wal", "open": self._db is not None}


class D1Client:
    backend = "d1"

    def __init__(self, account_id: str, database_id: str, api_token: str) -> None:
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query"
        self.headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
        self._client = httpx.AsyncClient(timeout=20)

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        await self._query(sql, params)

    async def execute_many(self, statements: list[tuple[str, list[Any] | tuple[Any, ...] | None]]) -> None:
        if not statements:
            return
        payload = [{"sql": sql, "params": list(params or [])} for sql, params in statements]
        response = await self._client.post(self.url, headers=self.headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RuntimeError(response.text) from error
        body = response.json()
        if not body.get("success", False):
            errors = body.get("errors") or []
            message = errors[0].get("message") if errors and isinstance(errors[0], dict) else "Cloudflare D1 batch query failed."
            raise RuntimeError(message)

    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None:
        rows = await self._query(sql, params)
        return rows[0] if rows else None

    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        return await self._query(sql, params)

    async def _query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        payload = {"sql": sql, "params": list(params or [])}
        response = await self._client.post(self.url, headers=self.headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RuntimeError(response.text) from error
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

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    def pool_stats(self) -> dict[str, Any]:
        return {"backend": self.backend, "pooled": True, "shared_http_client": not self._client.is_closed}


class PostgresClient:
    backend = "postgres"

    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self.database_url = database_url
        self.min_size = max(1, min_size)
        self.max_size = max(self.min_size, max_size)
        self._pool: Any | None = None
        self._init_lock = asyncio.Lock()

    async def _ensure_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._init_lock:
            if self._pool is not None:
                return self._pool
            asyncpg = import_asyncpg()
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.min_size,
                max_size=self.max_size,
            )
            return self._pool

    async def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        await self.execute_many([(sql, params)])

    async def execute_many(self, statements: list[tuple[str, list[Any] | tuple[Any, ...] | None]]) -> None:
        asyncpg = import_asyncpg()
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            try:
                async with connection.transaction():
                    for sql, params in statements:
                        await connection.execute(postgres_sql(sql), *(params or []))
            except asyncpg.UniqueViolationError as error:
                raise IntegrityError(str(error)) from error

    async def fetch_one(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> DbRow | None:
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def fetch_all(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[DbRow]:
        asyncpg = import_asyncpg()
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            try:
                rows = await connection.fetch(postgres_sql(sql), *(params or []))
            except asyncpg.UniqueViolationError as error:
                raise IntegrityError(str(error)) from error
        return [dict(row) for row in rows]

    async def close(self) -> None:
        async with self._init_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None

    def pool_stats(self) -> dict[str, Any]:
        pool = self._pool
        if pool is None:
            return {
                "backend": self.backend,
                "pooled": True,
                "initialized": False,
                "min_size": self.min_size,
                "max_size": self.max_size,
            }
        return {
            "backend": self.backend,
            "pooled": True,
            "initialized": True,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "size": pool.get_size(),
            "idle": pool.get_idle_size(),
            "free": getattr(pool, "get_idle_size", lambda: None)(),
        }


def import_asyncpg():
    try:
        import asyncpg
    except ImportError as error:
        raise RuntimeError("PostgreSQL backend requires asyncpg. Install backend requirements first.") from error
    return asyncpg


def postgres_sql(sql: str) -> str:
    output: list[str] = []
    index = 1
    in_single_quote = False
    in_double_quote = False
    escaped = False
    for char in sql:
        if char == "'" and not in_double_quote and not escaped:
            in_single_quote = not in_single_quote
            output.append(char)
        elif char == '"' and not in_single_quote and not escaped:
            in_double_quote = not in_double_quote
            output.append(char)
        elif char == "?" and not in_single_quote and not in_double_quote:
            output.append(f"${index}")
            index += 1
        else:
            output.append(char)
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return "".join(output).replace("CURRENT_TIMESTAMP", "(CURRENT_TIMESTAMP::text)")


def resolve_sqlite_path(path: str) -> Path:
    sqlite_path = Path(path)
    if sqlite_path.is_absolute():
        return sqlite_path
    return Path(__file__).resolve().parents[3] / sqlite_path


def sqlite_path_diagnostics(path: str) -> dict[str, Any]:
    resolved = resolve_sqlite_path(path)
    return {
        "configured_path": path,
        "resolved_path": str(resolved),
        "parent_exists": resolved.parent.exists(),
        "file_exists": resolved.exists(),
    }


def _client_key(settings: Settings) -> str:
    if settings.database_backend == "sqlite":
        return f"sqlite:{resolve_sqlite_path(settings.sqlite_path)}"
    if settings.database_backend == "d1":
        return f"d1:{settings.d1_account_id}:{settings.d1_database_id}"
    if settings.database_backend == "postgres":
        return f"postgres:{settings.database_url}:{settings.database_pool_min}:{settings.database_pool_max}"
    return f"unknown:{settings.database_backend}"


def create_database_client(settings: Settings) -> DatabaseClient:
    if settings.database_backend == "sqlite":
        return SQLiteClient(settings.sqlite_path)
    if settings.database_backend == "d1":
        if not settings.d1_account_id or not settings.d1_database_id or not settings.d1_api_token:
            raise RuntimeError("D1 is selected but D1_ACCOUNT_ID, D1_DATABASE_ID, or D1_API_TOKEN is missing.")
        return D1Client(settings.d1_account_id, settings.d1_database_id, settings.d1_api_token)
    if settings.database_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("PostgreSQL is selected but DATABASE_URL is missing.")
        return PostgresClient(
            settings.database_url,
            min_size=settings.database_pool_min,
            max_size=settings.database_pool_max,
        )
    raise RuntimeError(f"Unsupported database backend: {settings.database_backend}")


async def init_shared_database(settings: Settings | None = None) -> DatabaseClient:
    """Create or reuse the process-wide pooled database client."""
    global _shared_client, _shared_client_key
    current = settings or get_settings()
    key = _client_key(current)
    async with _shared_lock:
        if _shared_client is not None and _shared_client_key == key:
            return _shared_client
        if _shared_client is not None:
            await _shared_client.close()
        client = create_database_client(current)
        # Eager-init pools/connections so first request is warm.
        if isinstance(client, PostgresClient):
            await client._ensure_pool()
        elif isinstance(client, SQLiteClient):
            await client._ensure_connection()
        _shared_client = client
        _shared_client_key = key
        return client


async def close_shared_database() -> None:
    global _shared_client, _shared_client_key
    async with _shared_lock:
        if _shared_client is not None:
            await _shared_client.close()
        _shared_client = None
        _shared_client_key = None


def get_shared_database() -> DatabaseClient | None:
    return _shared_client


async def get_database(settings: Settings = Depends(get_settings)) -> DatabaseClient:
    try:
        if _shared_client is not None and _shared_client_key == _client_key(settings):
            return _shared_client
        return await init_shared_database(settings)
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
