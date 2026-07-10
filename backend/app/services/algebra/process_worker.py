"""Killable process isolation for deterministic algebra solves.

asyncio.wait_for + to_thread cannot stop a runaway SymPy thread. This module
runs solve_algebra_deterministic in a child process and terminates it on timeout.

IPC uses length-free JSON over Connection.send_bytes/recv_bytes (no pickle of
response objects) so the parent never unpickles untrusted child object graphs.
"""

from __future__ import annotations

import json
import multiprocessing as mp
from typing import Any

from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse

_MAX_IPC_BYTES = 8_000_000


def _child_entry(conn: Any, request_data: dict[str, Any]) -> None:
    try:
        from app.services.algebra.service import solve_algebra_deterministic

        request = AlgebraSolveRequest.model_validate(request_data)
        response = solve_algebra_deterministic(request)
        payload = {"status": "ok", "data": response.model_dump(mode="json")}
    except Exception as exc:  # pragma: no cover - surfaced to parent
        payload = {"status": "err", "data": f"{type(exc).__name__}: {exc}"}
    try:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > _MAX_IPC_BYTES:
            raw = json.dumps(
                {"status": "err", "data": "ALGEBRA_WORKER_IPC: response too large"},
                ensure_ascii=False,
            ).encode("utf-8")
        conn.send_bytes(raw)
    except Exception:
        pass
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
        if not parent_conn.poll(timeout):
            _terminate_process(proc)
            raise TimeoutError("ALGEBRA_TIMEOUT: deterministic solve exceeded time limit")
        try:
            raw = parent_conn.recv_bytes()
        except (EOFError, OSError, BrokenPipeError) as exc:
            _terminate_process(proc)
            raise RuntimeError(f"ALGEBRA_WORKER_IPC: worker closed pipe early ({exc})") from exc
        if len(raw) > _MAX_IPC_BYTES:
            _terminate_process(proc)
            raise RuntimeError("ALGEBRA_WORKER_IPC: response too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _terminate_process(proc)
            raise RuntimeError(f"ALGEBRA_WORKER_IPC: invalid JSON payload ({exc})") from exc
        if not isinstance(payload, dict) or "status" not in payload:
            raise RuntimeError("ALGEBRA_WORKER_IPC: malformed payload")
        if payload.get("status") == "ok":
            return AlgebraSolveResponse.model_validate(payload.get("data"))
        raise RuntimeError(str(payload.get("data") or "worker error"))
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
