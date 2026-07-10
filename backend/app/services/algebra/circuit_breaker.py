"""In-process circuit breaker for algebra timeouts."""

from __future__ import annotations

import threading
import time


class AlgebraCircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 8,
        window_seconds: float = 120.0,
        open_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.window_seconds = max(10.0, window_seconds)
        self.open_seconds = max(5.0, open_seconds)
        self._lock = threading.Lock()
        self._failures: list[float] = []
        self._opened_until = 0.0

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now < self._opened_until:
                return False
            self._prune(now)
            return True

    def record_success(self) -> None:
        with self._lock:
            if self._failures:
                self._failures.pop(0)

    def record_timeout(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._failures.append(now)
            self._prune(now)
            if len(self._failures) >= self.failure_threshold:
                self._opened_until = now + self.open_seconds
                self._failures.clear()

    def is_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._opened_until

    def stats(self) -> dict[str, float | int | bool]:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return {
                "open": now < self._opened_until,
                "failures_in_window": len(self._failures),
                "open_remaining_s": max(0.0, self._opened_until - now),
            }

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self._failures = [t for t in self._failures if t >= cutoff]

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._opened_until = 0.0

    def configure(
        self,
        *,
        failure_threshold: int | None = None,
        window_seconds: float | None = None,
        open_seconds: float | None = None,
    ) -> None:
        with self._lock:
            if failure_threshold is not None:
                self.failure_threshold = max(1, int(failure_threshold))
            if window_seconds is not None:
                self.window_seconds = max(10.0, float(window_seconds))
            if open_seconds is not None:
                self.open_seconds = max(5.0, float(open_seconds))


algebra_circuit_breaker = AlgebraCircuitBreaker()
