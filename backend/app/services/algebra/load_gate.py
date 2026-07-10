"""In-process concurrency gate for algebra solves.

Each admitted request reserves one capacity slot from HTTP acquire until either:
- HTTP finishes and no SymPy worker is running, or
- an orphan worker finishes after HTTP already ended (timeout path).

Timed-out orphans therefore keep capacity booked and cannot pile up toward 2x limit.
Multiple sequential workers in one request (rule-based then post-AI) share the same slot.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class AlgebraSlot:
    """Capacity token held from admit until request capacity is fully released."""

    _gate: AlgebraLoadGate
    _worker_running: bool = False
    _http_done: bool = False
    _closed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def enter_worker(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._worker_running = True

    def leave_worker(self) -> None:
        """Mark worker finished; free reserved only if HTTP already ended (orphan)."""
        with self._lock:
            if self._closed:
                return
            self._worker_running = False
            if not self._http_done:
                # Keep capacity for further workers or until HTTP finally releases.
                return
            self._closed = True
        self._gate._release_reserved()

    def release_http(self) -> None:
        """HTTP finished: free immediately unless a worker is still running (orphan hold)."""
        with self._lock:
            if self._closed:
                return
            self._http_done = True
            if self._worker_running:
                return
            self._closed = True
        self._gate._release_reserved()


class AlgebraLoadGate:
    def __init__(self) -> None:
        self._async_lock = asyncio.Lock()
        self._reserved = 0
        self._worker_lock = threading.Lock()
        self._worker_inflight = 0

    def worker_count(self) -> int:
        with self._worker_lock:
            return self._worker_inflight

    def reserved_count(self) -> int:
        with self._worker_lock:
            return self._reserved

    def _release_reserved(self) -> None:
        with self._worker_lock:
            self._reserved = max(0, self._reserved - 1)

    async def try_acquire(self, limit: int) -> AlgebraSlot | None:
        """Atomically reserve one capacity slot. Returns None when saturated."""
        limit = max(1, int(limit))
        async with self._async_lock:
            with self._worker_lock:
                if self._reserved >= limit:
                    return None
                self._reserved += 1
            return AlgebraSlot(self)

    def enter_worker(self, slot: AlgebraSlot | None = None) -> None:
        """Mark SymPy worker start; capacity already reserved by try_acquire."""
        with self._worker_lock:
            self._worker_inflight += 1
        if slot is not None:
            slot.enter_worker()

    def leave_worker(self, slot: AlgebraSlot | None = None) -> None:
        with self._worker_lock:
            self._worker_inflight = max(0, self._worker_inflight - 1)
        if slot is not None:
            slot.leave_worker()
        else:
            # Legacy path without slot: free one reserved if any
            with self._worker_lock:
                self._reserved = max(0, self._reserved - 1)


algebra_load_gate = AlgebraLoadGate()
