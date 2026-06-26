import json
from uuid import uuid4

from app.db.models import DbRow, RenderJobRecord
from app.db.session import DatabaseClient
from app.schemas.scene import RenderResponse


class RenderHistoryRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(
        self,
        user_id: str,
        problem_text: str,
        provider: str | None,
        model: str | None,
        response: RenderResponse,
        *,
        render_request_json: str | None = None,
        advanced_settings_json: str | None = None,
        runtime_settings_json: str | None = None,
        source_type: str = "problem",
        renderer: str | None = None,
    ) -> RenderJobRecord:
        job_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO render_jobs (
              id, user_id, problem_text, provider, model, scene_json, payload_json, warnings_json,
              render_request_json, advanced_settings_json, runtime_settings_json, source_type, renderer,
              degraded, fallback_source, ai_source, response_json, schema_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                job_id,
                user_id,
                problem_text,
                provider,
                model,
                response.scene.model_dump_json(),
                response.payload.model_dump_json(),
                json.dumps(response.warnings, ensure_ascii=False),
                render_request_json,
                advanced_settings_json,
                runtime_settings_json,
                source_type,
                renderer,
                1 if response.degraded else 0,
                response.fallback_source,
                response.ai_source,
                response.model_dump_json(),
                response.scene.schema_version,
            ],
        )
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        if row is None:
            raise RuntimeError("Không thể lưu lịch sử dựng hình.")
        return render_job_from_row(row)

    async def create_pending(
        self,
        user_id: str,
        problem_text: str,
        provider: str | None,
        model: str | None,
        *,
        render_request_json: str | None = None,
        advanced_settings_json: str | None = None,
        runtime_settings_json: str | None = None,
        source_type: str = "problem",
        renderer: str | None = None,
    ) -> RenderJobRecord:
        job_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO render_jobs (
              id, user_id, problem_text, provider, model, scene_json, payload_json, warnings_json,
              render_request_json, advanced_settings_json, runtime_settings_json, source_type, renderer, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                job_id,
                user_id,
                problem_text,
                provider,
                model,
                "{}",
                "{}",
                "[]",
                render_request_json,
                advanced_settings_json,
                runtime_settings_json,
                source_type,
                renderer,
                "queued",
            ],
        )
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        if row is None:
            raise RuntimeError("Không thể tạo render job.")
        return render_job_from_row(row)

    async def mark_running(self, job_id: str) -> None:
        await self.db.execute("UPDATE render_jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?", [job_id])

    async def mark_completed(self, job_id: str, response: RenderResponse, renderer: str | None) -> None:
        await self.db.execute(
            """
            UPDATE render_jobs
            SET status = 'completed', scene_json = ?, payload_json = ?, warnings_json = ?, renderer = ?,
                degraded = ?, fallback_source = ?, ai_source = ?, response_json = ?, schema_version = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [
                response.scene.model_dump_json(),
                response.payload.model_dump_json(),
                json.dumps(response.warnings, ensure_ascii=False),
                renderer,
                1 if response.degraded else 0,
                response.fallback_source,
                response.ai_source,
                response.model_dump_json(),
                response.scene.schema_version,
                job_id,
            ],
        )

    async def mark_failed(self, job_id: str, error: dict) -> None:
        await self.db.execute(
            """
            UPDATE render_jobs
            SET status = 'failed', error_json = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [json.dumps(error, ensure_ascii=False), job_id],
        )

    async def list_for_user(self, user_id: str, limit: int = 30) -> list[RenderJobRecord]:
        rows = await self.db.fetch_all(
            """
            SELECT id, user_id, problem_text, provider, model, warnings_json, created_at, source_type, renderer,
                   status, error_json, started_at, finished_at, degraded, fallback_source, ai_source, response_json, schema_version
            FROM render_jobs
            WHERE user_id = ? AND status = 'completed' AND response_json IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [user_id, limit],
        )
        return [render_job_from_row(row) for row in rows]

    async def find_for_user(self, user_id: str, job_id: str) -> RenderJobRecord | None:
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE user_id = ? AND id = ?", [user_id, job_id])
        return render_job_from_row(row) if row else None

    async def delete_for_user(self, user_id: str, job_id: str) -> None:
        await self.db.execute("DELETE FROM render_jobs WHERE user_id = ? AND id = ?", [user_id, job_id])


def render_job_from_row(row: DbRow) -> RenderJobRecord:
    return RenderJobRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]) if row.get("user_id") is not None else None,
        problem_text=str(row["problem_text"]),
        provider=str(row["provider"]) if row.get("provider") is not None else None,
        model=str(row["model"]) if row.get("model") is not None else None,
        scene_json=str(row.get("scene_json") or ""),
        payload_json=str(row.get("payload_json") or ""),
        warnings_json=str(row["warnings_json"]),
        created_at=str(row["created_at"]),
        render_request_json=str(row["render_request_json"]) if row.get("render_request_json") is not None else None,
        advanced_settings_json=str(row["advanced_settings_json"]) if row.get("advanced_settings_json") is not None else None,
        runtime_settings_json=str(row["runtime_settings_json"]) if row.get("runtime_settings_json") is not None else None,
        source_type=str(row.get("source_type") or "problem"),
        renderer=str(row["renderer"]) if row.get("renderer") is not None else None,
        status=str(row.get("status") or "completed"),
        error_json=str(row["error_json"]) if row.get("error_json") is not None else None,
        started_at=str(row["started_at"]) if row.get("started_at") is not None else None,
        finished_at=str(row["finished_at"]) if row.get("finished_at") is not None else None,
        degraded=bool(row.get("degraded") or 0),
        fallback_source=str(row.get("fallback_source") or "none"),
        ai_source=str(row.get("ai_source") or "none"),
        response_json=str(row["response_json"]) if row.get("response_json") is not None else None,
        schema_version=str(row.get("schema_version") or "1.0"),
    )
