"""Shared httpx.AsyncClient pool - tránh tạo client mới mỗi request LLM.

Mỗi base_url (provider) được map tới 1 AsyncClient dùng chung connection pool.
Client tự tạo khi cần, dùng lại cho mọi request cùng provider.
Khi app shutdown gọi close_all() để giải phóng tài nguyên.
"""

from __future__ import annotations

import httpx

_CONNECT_TIMEOUT = 8.0
_DEFAULT_READ_TIMEOUT = 55.0
_DEFAULT_WRITE_TIMEOUT = 15.0
_POOL_TIMEOUT = 5.0

TIMEOUT_SCENE = httpx.Timeout(
    connect=_CONNECT_TIMEOUT,
    read=55.0,
    write=_DEFAULT_WRITE_TIMEOUT,
    pool=_POOL_TIMEOUT,
)
TIMEOUT_REASONING = httpx.Timeout(
    connect=_CONNECT_TIMEOUT,
    read=80.0,
    write=_DEFAULT_WRITE_TIMEOUT,
    pool=_POOL_TIMEOUT,
)
TIMEOUT_OCR = httpx.Timeout(
    connect=_CONNECT_TIMEOUT,
    read=80.0,
    write=30.0,
    pool=_POOL_TIMEOUT,
)
TIMEOUT_FAST = httpx.Timeout(
    connect=_CONNECT_TIMEOUT,
    read=30.0,
    write=_DEFAULT_WRITE_TIMEOUT,
    pool=_POOL_TIMEOUT,
)
TIMEOUT_MODELS = httpx.Timeout(
    connect=_CONNECT_TIMEOUT,
    read=20.0,
    write=_DEFAULT_WRITE_TIMEOUT,
    pool=_POOL_TIMEOUT,
)

_pool: dict[str, httpx.AsyncClient] = {}


def get_client(base_url: str, timeout: httpx.Timeout | None = None) -> httpx.AsyncClient:
    key = base_url.rstrip("/")
    client = _pool.get(key)
    if client is not None and not client.is_closed:
        return client
    effective_timeout = timeout or httpx.Timeout(
        connect=_CONNECT_TIMEOUT,
        read=_DEFAULT_READ_TIMEOUT,
        write=_DEFAULT_WRITE_TIMEOUT,
        pool=_POOL_TIMEOUT,
    )
    client = httpx.AsyncClient(
        timeout=effective_timeout,
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=120,
        ),
        http2=True,
    )
    _pool[key] = client
    return client


async def close_all() -> None:
    for client in _pool.values():
        if not client.is_closed:
            await client.close()
    _pool.clear()
