from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import multiprocessing as mp
import queue
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import Request

from app.services.analyzer_errors import AnalyzerErrorCode, analyzer_error


ANALYZER_ENGINE_VERSION = "function-analyzer-v2"
ANALYZER_SCHEMA_VERSION = "analysis-response-v2"
ANALYZER_TIMEOUT_SECONDS = 12.0
ANALYZER_TOOL_TIMEOUT_SECONDS = 5.0
ANALYZER_CACHE_TTL_SECONDS = 15.0
ANALYZER_SESSION_TTL_SECONDS = 900.0
ANALYZER_CONCURRENCY_LIMIT = 2
ANALYZER_OVERLOAD_RETRY_SECONDS = 3
MAX_ANALYZER_SESSIONS = 128
MAX_ANALYZER_SESSION_CHARS = 200_000
MAX_ANALYZER_GEOGEBRA_COMMANDS = 300
MAX_ANALYZER_GRAPH_POINTS = 500
MAX_ANALYZER_RESPONSE_CHARS = 200_000
ANALYZER_OUTPUT_LIMIT = "ANALYZER_OUTPUT_LIMIT"

_ANALYZER_SEMAPHORE = threading.BoundedSemaphore(ANALYZER_CONCURRENCY_LIMIT)
_STATE_LOCK = threading.RLock()
_LOGGER = logging.getLogger(__name__)


@dataclass
class _InflightJob:
    key: str
    process: Any
    result_queue: Any
    task: asyncio.Task[dict[str, Any]]
    waiters: int = 0


@dataclass(frozen=True)
class _CacheEntry:
    expires_at: float
    result: dict[str, Any]


@dataclass(frozen=True)
class AnalysisSession:
    analysis_id: str
    scope: str
    engine_version: str
    schema_version: str
    expires_at: float
    result: dict[str, Any]


_ANALYZER_CACHE: dict[str, _CacheEntry] = {}
_ANALYZER_INFLIGHT: dict[str, _InflightJob] = {}
_ANALYZER_SESSIONS: dict[str, AnalysisSession] = {}


def analysis_scope(user_id: str | None, request: Request | None = None) -> str:
    if user_id:
        return f"user:{user_id}"
    host = request.client.host if request is not None and request.client is not None else "local"
    digest = hashlib.sha256(host.encode("utf-8")).hexdigest()[:24]
    return f"anonymous:{digest}"


async def run_cached_analysis(
    expression: str,
    parameters: dict[str, Any] | None = None,
    *,
    parameter_mode: str | None = None,
    interval: dict[str, Any] | None = None,
    line: dict[str, Any] | None = None,
    parameter_conditions: dict[str, Any] | None = None,
    transform: dict[str, Any] | None = None,
    scope: str = "legacy",
    request: Request | None = None,
) -> dict[str, Any]:
    payload = {
        "expression": expression,
        "parameters": parameters,
        "parameter_mode": parameter_mode,
        "interval": interval,
        "line": line,
        "parameter_conditions": parameter_conditions,
        "transform": transform,
    }
    key = _request_key(scope, payload)
    now = time.monotonic()
    with _STATE_LOCK:
        _prune_state(now)
        cached = _ANALYZER_CACHE.get(key)
        if cached is not None and cached.expires_at > now:
            _log_event("base", 0.0, reused=True)
            return copy.deepcopy(cached.result)
        job = _ANALYZER_INFLIGHT.get(key)
        if job is None:
            job = _start_job(key, _analysis_worker, payload, ANALYZER_TIMEOUT_SECONDS)
            _ANALYZER_INFLIGHT[key] = job
        else:
            _log_event("base", 0.0, reused=True)
        job.waiters += 1

    try:
        result = await _wait_for_job(job, request)
        if "error" not in result:
            with _STATE_LOCK:
                _ANALYZER_CACHE[key] = _CacheEntry(
                    expires_at=time.monotonic() + ANALYZER_CACHE_TTL_SECONDS,
                    result=copy.deepcopy(result),
                )
        return copy.deepcopy(result)
    finally:
        _release_waiter(job)


def run_analysis_sync(
    expression: str,
    parameters: dict[str, Any] | None,
    interval: dict[str, Any] | None,
    line: dict[str, Any] | None,
    parameter_conditions: dict[str, Any] | None,
    transform: dict[str, Any] | None,
    parameter_mode: str | None = None,
) -> dict[str, Any]:
    payload = {
        "expression": expression,
        "parameters": parameters,
        "parameter_mode": parameter_mode,
        "interval": interval,
        "line": line,
        "parameter_conditions": parameter_conditions,
        "transform": transform,
    }
    return _run_process_sync(_analysis_worker, payload, ANALYZER_TIMEOUT_SECONDS)


def create_analysis_session(scope: str, result: dict[str, Any]) -> AnalysisSession:
    serialized_size = len(json.dumps(result, ensure_ascii=False, default=str))
    if serialized_size > MAX_ANALYZER_SESSION_CHARS:
        raise ValueError("Kết quả phân tích quá lớn để tạo session.")
    now = time.monotonic()
    session = AnalysisSession(
        analysis_id=secrets.token_urlsafe(24),
        scope=scope,
        engine_version=ANALYZER_ENGINE_VERSION,
        schema_version=ANALYZER_SCHEMA_VERSION,
        expires_at=now + ANALYZER_SESSION_TTL_SECONDS,
        result=copy.deepcopy(result),
    )
    with _STATE_LOCK:
        _prune_state(now)
        _ANALYZER_SESSIONS[session.analysis_id] = session
        while len(_ANALYZER_SESSIONS) > MAX_ANALYZER_SESSIONS:
            _ANALYZER_SESSIONS.pop(next(iter(_ANALYZER_SESSIONS)))
    return session


def session_expiry_iso(session: AnalysisSession) -> str:
    remaining = max(0.0, session.expires_at - time.monotonic())
    return (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat()


def get_analysis_session(analysis_id: str, scope: str) -> AnalysisSession:
    now = time.monotonic()
    with _STATE_LOCK:
        _prune_state(now)
        session = _ANALYZER_SESSIONS.get(analysis_id)
        if session is None or session.scope != scope:
            raise KeyError("Analysis session không tồn tại hoặc đã hết hạn.")
        if session.engine_version != ANALYZER_ENGINE_VERSION or session.schema_version != ANALYZER_SCHEMA_VERSION:
            _ANALYZER_SESSIONS.pop(analysis_id, None)
            raise KeyError("Analysis session không còn tương thích với engine hiện tại.")
        return session


async def run_session_tool(
    analysis_id: str,
    scope: str,
    tool: str,
    payload: dict[str, Any],
    request: Request | None = None,
) -> dict[str, Any]:
    session = get_analysis_session(analysis_id, scope)
    worker_payload = {
        "base_result": session.result,
        "tool": tool,
        "payload": payload,
    }
    key = f"tool:{analysis_id}:{tool}:{_payload_digest(payload)}"
    with _STATE_LOCK:
        job = _start_job(key, _tool_worker, worker_payload, ANALYZER_TOOL_TIMEOUT_SECONDS)
        job.waiters = 1
    try:
        result = await _wait_for_job(job, request)
    finally:
        _release_waiter(job)
    if result.get("error"):
        raise ValueError("Không chạy được công cụ analyzer.")
    return result


def clear_runtime_state() -> None:
    with _STATE_LOCK:
        for job in list(_ANALYZER_INFLIGHT.values()):
            _terminate_process(job.process)
        _ANALYZER_INFLIGHT.clear()
        _ANALYZER_CACHE.clear()
        _ANALYZER_SESSIONS.clear()


def _start_job(key: str, target: Callable[..., None], payload: dict[str, Any], timeout: float) -> _InflightJob:
    if not _ANALYZER_SEMAPHORE.acquire(blocking=False):
        raise analyzer_error(
            AnalyzerErrorCode.RATE_LIMITED,
            stage="queue",
            headers={"Retry-After": str(ANALYZER_OVERLOAD_RETRY_SECONDS)},
        )
    try:
        ctx = _multiprocessing_context()
        result_queue = ctx.Queue(maxsize=1)
        process = ctx.Process(target=target, args=(result_queue, payload))
        process.start()
        placeholder: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        job = _InflightJob(key=key, process=process, result_queue=result_queue, task=placeholder)  # type: ignore[arg-type]
        job.task = asyncio.create_task(_monitor_job(job, timeout))
        return job
    except Exception:
        _ANALYZER_SEMAPHORE.release()
        raise


async def _monitor_job(job: _InflightJob, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        while job.process.is_alive():
            if time.monotonic() - started >= timeout:
                _terminate_process(job.process)
                _log_event("process", time.monotonic() - started, timed_out=True)
                return _error_payload("Analyzer vượt giới hạn thời gian xử lý.", AnalyzerErrorCode.TIMEOUT.value)
            await asyncio.sleep(0.025)
        job.process.join(0.2)
        try:
            status, payload = job.result_queue.get_nowait()
        except queue.Empty:
            return _error_payload("Analyzer không trả kết quả.", "ANALYZE_FAILED")
        if status == "ok":
            _log_event("process", time.monotonic() - started)
            return payload
        _log_event("process", time.monotonic() - started, failed=True)
        return _error_payload("Analyzer gặp lỗi nội bộ.", "ANALYZE_FAILED")
    finally:
        _ANALYZER_SEMAPHORE.release()


async def _wait_for_job(job: _InflightJob, request: Request | None) -> dict[str, Any]:
    while not job.task.done():
        if request is not None and await request.is_disconnected():
            raise asyncio.CancelledError
        await asyncio.sleep(0.025)
    return await asyncio.shield(job.task)


def _release_waiter(job: _InflightJob) -> None:
    with _STATE_LOCK:
        job.waiters = max(0, job.waiters - 1)
        if job.waiters == 0:
            if not job.task.done():
                _terminate_process(job.process)
                _log_event("process", 0.0, cancelled=True)
            if _ANALYZER_INFLIGHT.get(job.key) is job:
                _ANALYZER_INFLIGHT.pop(job.key, None)


def _run_process_sync(target: Callable[..., None], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    ctx = _multiprocessing_context()
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(target=target, args=(result_queue, payload))
    process.start()
    process.join(timeout)
    if process.is_alive():
        _terminate_process(process)
        return _error_payload("Analyzer vượt giới hạn thời gian xử lý.", AnalyzerErrorCode.TIMEOUT.value)
    try:
        status, result = result_queue.get_nowait()
    except queue.Empty:
        return _error_payload("Analyzer không trả kết quả.", "ANALYZE_FAILED")
    return result if status == "ok" else _error_payload("Analyzer gặp lỗi nội bộ.", "ANALYZE_FAILED")


def _analysis_worker(result_queue: Any, payload: dict[str, Any]) -> None:
    try:
        from app.services.function_analyzer import AnalyzerStageTimeout, analyze_function, analyzer_stage_timeout
        from app.services.function_graph_builder import build_function_graph

        data = analyze_function(
            payload["expression"],
            payload.get("parameters"),
            parameter_mode=payload.get("parameter_mode"),
            interval=payload.get("interval"),
            line=payload.get("line"),
            parameter_conditions=payload.get("parameter_conditions"),
            transform=payload.get("transform"),
        )
        if "error" not in data and not data.get("_skip_graph"):
            try:
                with analyzer_stage_timeout("graph", 2.0):
                    scene, data["geogebra_commands"], data["graph_points"] = build_function_graph(data)
                    data["graph_scene"] = scene.model_dump(mode="json")
                data.setdefault("stage_statuses", {})["graph"] = {"status": "ok"}
            except AnalyzerStageTimeout as error:
                data.setdefault("stage_statuses", {})[error.stage] = {"status": "timeout", "error_code": error.code}
                data.setdefault("warnings", []).append(str(error))
        elif data.get("_skip_graph"):
            data.setdefault("stage_statuses", {})["graph"] = {"status": "skipped"}
        _attach_verification(data)
        _drop_runtime_objects(data)
        result_queue.put(("ok", apply_output_limits(data)))
    except Exception:
        result_queue.put(("error", None))


def _tool_worker(result_queue: Any, payload: dict[str, Any]) -> None:
    try:
        from app.services.function_analyzer import analyze_function_tool_from_evidence

        result = analyze_function_tool_from_evidence(
            payload["base_result"],
            payload["tool"],
            payload["payload"],
        )
        result_queue.put(("ok", result))
    except Exception:
        result_queue.put(("error", None))


def _attach_verification(data: dict[str, Any]) -> None:
    try:
        from app.services.function_analysis_capabilities import expression_capabilities
        from app.services.function_analysis_verification import build_verification_report

        analyzed_expr = data.get("_evaluated_expr") or data.get("_parsed_expr")
        if analyzed_expr is not None:
            capabilities = expression_capabilities(analyzed_expr, data)
            data["capabilities"] = capabilities
            data["capabilities_v2"] = capabilities
        data["verification"] = build_verification_report(data)
        data.setdefault("stage_statuses", {})["verification"] = {"status": "ok"}
    except Exception:
        data["verification"] = {
            "status": "unverified",
            "checks": [],
            "truncated": False,
            "possibly_incomplete": True,
        }
        data.setdefault("stage_statuses", {})["verification"] = {"status": "failed"}
        data.setdefault("warnings", []).append("Không tạo được verification report.")


def _drop_runtime_objects(data: dict[str, Any]) -> None:
    for key in ("_parsed_expr", "_evaluated_expr", "_domain_set", "_domain_info", "_graph_expr", "_skip_graph"):
        data.pop(key, None)


def apply_output_limits(data: dict[str, Any]) -> dict[str, Any]:
    if len(data.get("geogebra_commands") or []) > MAX_ANALYZER_GEOGEBRA_COMMANDS:
        return _error_payload("Analyzer tạo quá nhiều lệnh GeoGebra.", ANALYZER_OUTPUT_LIMIT)
    if len(data.get("graph_points") or []) > MAX_ANALYZER_GRAPH_POINTS:
        return _error_payload("Analyzer tạo quá nhiều điểm đồ thị.", ANALYZER_OUTPUT_LIMIT)
    if len(json.dumps(data, ensure_ascii=False, default=str)) > MAX_ANALYZER_RESPONSE_CHARS:
        return _error_payload("Analyzer tạo phản hồi quá lớn.", ANALYZER_OUTPUT_LIMIT)
    return data


def _request_key(scope: str, payload: dict[str, Any]) -> str:
    return f"{scope}:{ANALYZER_ENGINE_VERSION}:{ANALYZER_SCHEMA_VERSION}:{_payload_digest(payload)}"


def _payload_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _prune_state(now: float) -> None:
    for key in [key for key, entry in _ANALYZER_CACHE.items() if entry.expires_at <= now]:
        _ANALYZER_CACHE.pop(key, None)
    for key in [key for key, session in _ANALYZER_SESSIONS.items() if session.expires_at <= now]:
        _ANALYZER_SESSIONS.pop(key, None)
    while len(_ANALYZER_CACHE) > 128:
        _ANALYZER_CACHE.pop(next(iter(_ANALYZER_CACHE)))


def _terminate_process(process: Any) -> None:
    if process.is_alive():
        process.terminate()
    process.join(1.0)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(1.0)


def _multiprocessing_context():
    try:
        return mp.get_context("fork")
    except ValueError:  # pragma: no cover
        return mp.get_context()


def _log_event(stage: str, duration: float, **flags: bool) -> None:
    _LOGGER.info(
        "analyzer_runtime",
        extra={"stage": stage, "duration_ms": round(duration * 1000), **flags},
    )


def _error_payload(message: str, code: str) -> dict[str, Any]:
    return {"error": message, "error_code": code, "warnings": [message]}