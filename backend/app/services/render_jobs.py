"""Async render job processing (DB queue + optional Redis notify)."""

from __future__ import annotations

import asyncio
import json
import logging

from app.core.config import Settings, get_settings
from app.db.models import RenderJobRecord
from app.db.session import DatabaseClient, get_shared_database, init_shared_database
from app.repositories.history import RenderHistoryRepository
from app.schemas.scene import RenderRequest
from app.services.load_gates import render_load_gate

logger = logging.getLogger(__name__)

RENDER_TIMEOUT_SECONDS = 310


async def enqueue_render_job(
    db: DatabaseClient,
    user_id: str,
    request: RenderRequest,
    *,
    notify: bool = True,
) -> str:
    repo = RenderHistoryRepository(db)
    job = await repo.create_pending(
        user_id,
        request.problem_text,
        None,
        None,
        render_request_json=json.dumps(
            {k: v for k, v in request.model_dump(mode="json").items() if k != "advanced_settings" or v is not None},
            ensure_ascii=False,
        ),
        advanced_settings_json=request.advanced_settings.model_dump_json(),
        runtime_settings_json=request.runtime_settings.model_dump_json(exclude_none=True) if request.runtime_settings is not None else None,
        source_type="problem",
        renderer=request.preferred_renderer,
    )
    if notify:
        await notify_render_job(job.id)
    return job.id


async def notify_render_job(job_id: str) -> None:
    try:
        from app.services.redis_client import get_redis

        redis = await get_redis()
        if redis is not None:
            await redis.lpush("render_jobs", job_id)
    except Exception:
        logger.debug("render job notify skipped", exc_info=True)


async def process_render_job(db: DatabaseClient, job_id: str, settings: Settings | None = None) -> None:
    """Claim a queued job by id (if still queued) and execute it."""
    settings = settings or get_settings()
    repo = RenderHistoryRepository(db)
    job = await repo.find_by_id(job_id)
    if job is None or job.status in {"completed", "failed"}:
        return
    if job.status != "queued":
        # Another worker already claimed/finished this id.
        return
    claimed_row = await db.fetch_one(
        """
        UPDATE render_jobs
        SET status = 'running', started_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'queued'
        RETURNING *
        """,
        [job_id],
    )
    if claimed_row is None:
        return
    from app.repositories.history import render_job_from_row

    await _execute_claimed_job(db, render_job_from_row(claimed_row), settings)


async def _execute_claimed_job(db: DatabaseClient, job: RenderJobRecord, settings: Settings) -> None:
    import time

    from app.api.routes_render import build_problem_render_response, render_error_payload
    from app.repositories.activity import try_log_user_activity
    from app.repositories.auth import UserRepository
    from app.repositories.errors import try_record_error_event

    job_id = job.id
    repo = RenderHistoryRepository(db)
    slot = await render_load_gate.try_acquire(settings.render_max_concurrent)
    if slot is None:
        await db.execute(
            "UPDATE render_jobs SET status = 'queued', started_at = NULL WHERE id = ? AND status = 'running'",
            [job_id],
        )
        await notify_render_job(job_id)
        return

    started = time.perf_counter()
    try:
        if not job.render_request_json:
            error = {"code": "RENDER_FAILED", "message": "Thiếu payload render."}
            duration_ms = int((time.perf_counter() - started) * 1000)
            await repo.mark_failed(job_id, error, duration_ms=duration_ms)
            if job.user_id:
                await try_log_user_activity(
                    db,
                    job.user_id,
                    "render.failed",
                    target_type="render_job",
                    target_id=job_id,
                    metadata={"code": error["code"], "duration_ms": duration_ms, "async": True},
                )
            await try_record_error_event(
                db,
                message=error["message"],
                source="worker",
                user_id=job.user_id,
                route="/worker/render",
                error_code=error["code"],
                metadata={"job_id": job_id, "duration_ms": duration_ms},
            )
            return
        request = RenderRequest.model_validate_json(job.render_request_json)
        user = await UserRepository(db).find_by_id(job.user_id) if job.user_id else None
        if user is None:
            error = {"code": "RENDER_FAILED", "message": "User không tồn tại."}
            duration_ms = int((time.perf_counter() - started) * 1000)
            await repo.mark_failed(job_id, error, duration_ms=duration_ms)
            await try_record_error_event(
                db,
                message=error["message"],
                source="worker",
                user_id=job.user_id,
                route="/worker/render",
                error_code=error["code"],
                metadata={"job_id": job_id},
            )
            return
        try:
            response = await asyncio.wait_for(
                build_problem_render_response(request, db, user),
                timeout=RENDER_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            duration_ms = int((time.perf_counter() - started) * 1000)
            error = {"code": "TIMEOUT", "message": f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s."}
            await repo.mark_failed(job_id, error, duration_ms=duration_ms)
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                target_id=job_id,
                metadata={"code": "TIMEOUT", "duration_ms": duration_ms, "async": True, "tier": request.tier},
            )
            await try_record_error_event(
                db,
                message=error["message"],
                source="worker",
                user_id=user.id,
                route="/worker/render",
                error_code="TIMEOUT",
                metadata={"job_id": job_id, "duration_ms": duration_ms},
            )
            return
        except (RuntimeError, ValueError, KeyError) as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            payload = render_error_payload(error)
            await repo.mark_failed(job_id, payload, duration_ms=duration_ms)
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                target_id=job_id,
                metadata={"code": payload.get("code"), "duration_ms": duration_ms, "async": True, "tier": request.tier},
            )
            await try_record_error_event(
                db,
                message=str(payload.get("debug_message") or payload.get("message") or error),
                source="worker",
                user_id=user.id,
                route="/worker/render",
                error_code=str(payload.get("code") or "RENDER_FAILED"),
                metadata={"job_id": job_id, "duration_ms": duration_ms},
            )
            return
        duration_ms = int((time.perf_counter() - started) * 1000)
        await repo.mark_completed(job_id, response, response.scene.renderer, duration_ms=duration_ms)
        completed = await repo.find_by_id(job_id)
        if completed is not None:
            await repo.ensure_history_item(completed, response=response, tier=request.tier)
        await try_log_user_activity(
            db,
            user.id,
            "render.completed",
            target_type="render_job",
            target_id=job_id,
            metadata={
                "tier": request.tier,
                "renderer": response.scene.renderer,
                "provider": response.source.provider,
                "model": response.source.model,
                "duration_ms": duration_ms,
                "async": True,
                "degraded": response.degraded,
            },
        )
    finally:
        slot.release()


async def process_one_queued_job(db: DatabaseClient, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    repo = RenderHistoryRepository(db)
    job = await repo.claim_next_queued()
    if job is None:
        return False
    await _execute_claimed_job(db, job, settings)
    return True


async def run_worker_loop(poll_seconds: float = 1.0, stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    db = await init_shared_database(settings)
    stop = stop_event or asyncio.Event()
    logger.info("Render worker started (poll=%.2fs async=%s)", poll_seconds, settings.render_async_enabled)
    while not stop.is_set():
        try:
            worked = await process_one_queued_job(db, settings)
            if worked:
                continue
            await _wait_for_job_or_timeout(poll_seconds)
        except Exception:
            logger.exception("Render worker loop error")
            await asyncio.sleep(min(5.0, poll_seconds * 2))
    logger.info("Render worker stopped")


async def _wait_for_job_or_timeout(poll_seconds: float) -> bool:
    try:
        from app.services.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            await asyncio.sleep(poll_seconds)
            return False
        result = await redis.brpop("render_jobs", timeout=max(1, int(poll_seconds)))
        return result is not None
    except Exception:
        await asyncio.sleep(poll_seconds)
        return False


def spawn_inline_job(db: DatabaseClient, job_id: str) -> None:
    """Fire-and-forget in API process when no external worker is required."""

    async def _run() -> None:
        try:
            shared = get_shared_database() or db
            await process_render_job(shared, job_id)
        except Exception:
            logger.exception("Inline render job failed job_id=%s", job_id)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
