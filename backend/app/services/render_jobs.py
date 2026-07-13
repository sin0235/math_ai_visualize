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
    import json
    import time

    from pydantic import ValidationError

    from app.api.routes_render import (
        _run_render_nlp,
        build_problem_render_result_v3,
        sanitize_request_dump,
        workspace_response_v3,
    )
    from app.repositories.activity import try_log_user_activity
    from app.repositories.auth import UserRepository
    from app.repositories.errors import try_record_error_event
    from app.services.ai_resolution import resolve_byok_ai_config
    from app.services.prompt_security import enforce_prompt_injection_gate
    from app.services.user_ai_settings import UserAiSettingsError

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
    user = None
    request = None
    try:
        if not job.render_request_json:
            raise RuntimeError("Thiếu payload render.")

        try:
            request = RenderRequest.model_validate_json(job.render_request_json)
        except ValidationError as error:
            raise RuntimeError(f"Payload render không hợp lệ: {error}") from error

        user = await UserRepository(db).find_by_id(job.user_id) if job.user_id else None
        if user is None:
            raise RuntimeError("User không tồn tại.")

        enforce_prompt_injection_gate(request.problem_text, mode=settings.prompt_injection_gate_mode)
        request, nlp_hints = await _run_render_nlp(request, db, user, preserve_problem_text=True)

        try:
            byok = await resolve_byok_ai_config(db, user, "render", settings)
        except UserAiSettingsError as error:
            raise RuntimeError(f"Cấu hình BYOK không hợp lệ: {error}") from error

        result = await asyncio.wait_for(
            build_problem_render_result_v3(request, db, user, byok=byok, nlp_hints=nlp_hints),
            timeout=RENDER_TIMEOUT_SECONDS,
        )
        if not result.can_project:
            error_issues = [issue for issue in result.issues if issue.severity == "error"]
            code = next((issue.code for issue in error_issues), "SCENE_SCHEMA_INVALID")
            detail = "; ".join(f"[{issue.code}] {issue.message}" for issue in error_issues[:4])
            raise RuntimeError(detail or f"Scene v3 không vượt qua pipeline ({code}).")

        response = workspace_response_v3(result, trusted_for_downstream=result.status == "verified")
        duration_ms = int((time.perf_counter() - started) * 1000)
        try:
            await repo.complete_pending_as_v3(
                job_id,
                user.id,
                response,
                render_request_json=json.dumps(sanitize_request_dump(request), ensure_ascii=False),
                duration_ms=duration_ms,
                provider=response.scene.audit.generator_provider,
                model=response.scene.audit.generator_model,
            )
        except Exception as error:
            logger.exception("Failed to persist async render job %s", job_id)
            await repo.mark_failed(
                job_id,
                {
                    "code": "HISTORY_PERSIST_FAILED",
                    "message": f"Không lưu được lịch sử Scene v3: {error}",
                },
                duration_ms=duration_ms,
            )
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                target_id=job_id,
                metadata={"code": "HISTORY_PERSIST_FAILED", "duration_ms": duration_ms, "async": True},
            )
            return

        await try_log_user_activity(
            db,
            user.id,
            "render.completed",
            target_type="render_job",
            target_id=job_id,
            metadata={
                "tier": request.tier,
                "renderer": response.scene.renderer,
                "provider": response.scene.audit.generator_provider,
                "model": response.scene.audit.generator_model,
                "duration_ms": duration_ms,
                "async": True,
                "schema_version": "3.0",
                "status": response.status,
            },
        )
    except TimeoutError:
        duration_ms = int((time.perf_counter() - started) * 1000)
        error = {"code": "TIMEOUT", "message": f"Render vượt quá {RENDER_TIMEOUT_SECONDS}s."}
        await repo.mark_failed(job_id, error, duration_ms=duration_ms)
        if user is not None:
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                target_id=job_id,
                metadata={
                    "code": "TIMEOUT",
                    "duration_ms": duration_ms,
                    "async": True,
                    "tier": getattr(request, "tier", None),
                },
            )
        await try_record_error_event(
            db,
            message=error["message"],
            source="worker",
            user_id=job.user_id,
            route="worker/render",
            error_code="TIMEOUT",
            metadata={"job_id": job_id, "duration_ms": duration_ms},
        )
    except Exception as error:
        duration_ms = int((time.perf_counter() - started) * 1000)
        message = str(error) or error.__class__.__name__
        code = (
            "AI_PROVIDER_FAILED"
            if "provider" in message.lower() or "thất bại" in message.lower()
            else "RENDER_FAILED"
        )
        payload = {"code": code, "message": message}
        await repo.mark_failed(job_id, payload, duration_ms=duration_ms)
        if user is not None:
            await try_log_user_activity(
                db,
                user.id,
                "render.failed",
                target_type="render_job",
                target_id=job_id,
                metadata={
                    "code": code,
                    "duration_ms": duration_ms,
                    "async": True,
                    "tier": getattr(request, "tier", None),
                },
            )
        await try_record_error_event(
            db,
            message=message,
            source="worker",
            user_id=job.user_id,
            route="worker/render",
            error_code=code,
            metadata={"job_id": job_id, "duration_ms": duration_ms},
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
    last_alert_check = 0.0
    last_retention = 0.0
    while not stop.is_set():
        try:
            worked = await process_one_queued_job(db, settings)
            now = asyncio.get_running_loop().time()
            # Hourly alert checks
            if now - last_alert_check > 3600:
                last_alert_check = now
                try:
                    from app.services.alerts import run_alert_checks

                    await run_alert_checks(db, settings)
                except Exception:
                    logger.exception("Alert checks failed")
            # Daily retention cleanup (dry_run=False, limited batch)
            if now - last_retention > 86400:
                last_retention = now
                try:
                    await _run_analytics_retention(db, settings)
                except Exception:
                    logger.exception("Analytics retention failed")
            if worked:
                continue
            await _wait_for_job_or_timeout(poll_seconds)
        except Exception:
            logger.exception("Render worker loop error")
            await asyncio.sleep(min(5.0, poll_seconds * 2))
    logger.info("Render worker stopped")


async def _run_analytics_retention(db: DatabaseClient, settings: Settings) -> None:
    from datetime import UTC, datetime, timedelta

    cuts = {
        "error_events": (datetime.now(UTC) - timedelta(days=settings.analytics_retention_errors_days)).strftime("%Y-%m-%d %H:%M:%S"),
        "user_activity_events": (datetime.now(UTC) - timedelta(days=settings.analytics_retention_activity_days)).strftime("%Y-%m-%d %H:%M:%S"),
        "ai_call_metrics": (datetime.now(UTC) - timedelta(days=settings.analytics_retention_ai_metrics_days)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    for table, cutoff in cuts.items():
        try:
            await db.execute(f"DELETE FROM {table} WHERE created_at < ?", [cutoff])
            logger.info("Retention deleted old rows table=%s before=%s", table, cutoff)
        except Exception:
            logger.warning("Retention skip table=%s", table, exc_info=True)


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
