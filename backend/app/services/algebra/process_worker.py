"""Killable process isolation for deterministic algebra solves.

asyncio.wait_for + to_thread cannot stop a runaway SymPy thread. This module
runs solve_algebra_deterministic in a child process and terminates it on timeout.
"""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse


def _child_entry(conn: Any, request_data: dict[str, Any]) -> None:
    try:
        from app.services.algebra.service import solve_algebra_deterministic

        request = AlgebraSolveRequest.model_validate(request_data)
        response = solve_algebra_deterministic(request)
        conn.send(("ok", response.model_dump(mode="json")))
    except Exception as exc:  # pragma: no cover - surfaced to parent
        conn.send(("err", f"{type(exc).__name__}: {exc}"))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def solve_algebra_in_process(request: AlgebraSolveRequest, timeout: float) -> AlgebraSolveResponse:
    """Run deterministic solve in a spawned process; kill hard on timeout."""
    timeout = max(0.5, float(timeout))
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_child_entry,
        args=(child_conn, request.model_dump(mode="json")),
        daemon=True,
        name="algebra-solve-worker",
    )
    proc.start()
    child_conn.close()
    try:
        if parent_conn.poll(timeout):
            status, payload = parent_conn.recv()
            if status == "ok":
                return AlgebraSolveResponse.model_validate(payload)
            raise RuntimeError(str(payload))
        # Timeout: hard-kill child so capacity can be released immediately.
        _terminate_process(proc)
        raise TimeoutError("ALGEBRA_TIMEOUT: deterministic solve exceeded time limit")
    finally:
        try:
            parent_conn.close()
        except Exception:
            pass
        if proc.is_alive():
            _terminate_process(proc)


def _terminate_process(proc: mp.Process) -> None:
    proc.terminate()
    proc.join(2.0)
    if proc.is_alive():
        proc.kill()
        proc.join(1.0)
