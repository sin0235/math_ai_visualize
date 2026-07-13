import json
from uuid import uuid4

from app.db.models import DbRow, RenderJobRecord, SceneRevisionRecord
from app.db.session import DatabaseClient
from app.schemas.scene import RenderResponse
from app.schemas.scene_v3 import SceneWorkspaceResponseV3


class RenderHistoryRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create_v3_workspace(
        self,
        user_id: str,
        response: SceneWorkspaceResponseV3,
        *,
        render_request_json: str | None = None,
    ) -> RenderJobRecord:
        job_id = str(uuid4())
        scene = response.scene
        provider = scene.audit.generator_provider
        model = scene.audit.generator_model
        workspace_json = response.model_dump_json()
        await self.db.execute_many([
            (
                """
                INSERT INTO render_jobs (
                  id, user_id, problem_text, provider, model, scene_json, payload_json, warnings_json,
                  render_request_json, source_type, renderer, status, degraded, fallback_source,
                  ai_source, response_json, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', 0, 'none', 'none', ?, '3.0')
                """,
                [
                    job_id,
                    user_id,
                    scene.problem_text,
                    provider,
                    model,
                    scene.model_dump_json(),
                    response.payload.model_dump_json(),
                    json.dumps([issue.message for issue in response.issues], ensure_ascii=False),
                    render_request_json,
                    "problem",
                    scene.renderer,
                    workspace_json,
                ],
            ),
            (
                """
                INSERT INTO history_items (
                  id, user_id, render_job_id, problem_preview, topic, grade, tier, renderer,
                  provider, model, source_type, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'problem', 'completed')
                """,
                [
                    job_id,
                    user_id,
                    job_id,
                    scene.problem_text[:240],
                    scene.topic,
                    str(scene.grade) if scene.grade is not None else None,
                    request_tier(render_request_json),
                    scene.renderer,
                    provider,
                    model,
                ],
            ),
            (
                """
                INSERT INTO scene_revisions (
                  id, history_item_id, render_job_id, revision_no, change_source, change_summary,
                  scene_json, response_json, schema_version, command_log_json, scene_id, snapshot_revision
                ) VALUES (?, ?, ?, ?, 'render_v3', 'Bản dựng v3 đầu tiên', ?, ?, '3.0', '[]', ?, ?)
                """,
                [
                    f"{job_id}:r{scene.revision}",
                    job_id,
                    job_id,
                    scene.revision,
                    scene.model_dump_json(),
                    workspace_json,
                    scene.scene_id,
                    scene.revision,
                ],
            ),
            (
                """
                INSERT INTO scene_workspaces (
                  scene_id, user_id, history_item_id, revision, scene_json, status, verification_json, issues_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    scene.scene_id,
                    user_id,
                    job_id,
                    scene.revision,
                    scene.model_dump_json(),
                    response.status,
                    json.dumps([item.model_dump(mode="json") for item in response.verification], ensure_ascii=False),
                    json.dumps([item.model_dump(mode="json") for item in response.issues], ensure_ascii=False),
                ],
            ),
        ])
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        if row is None:
            raise RuntimeError("Không thể lưu lịch sử dựng hình v3.")
        return render_job_from_row(row)

    async def complete_pending_as_v3(
        self,
        job_id: str,
        user_id: str,
        response: SceneWorkspaceResponseV3,
        *,
        render_request_json: str | None = None,
        duration_ms: int | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> RenderJobRecord:
        """Finish a queued/running job as Scene v3 workspace + history (async worker path)."""
        scene = response.scene
        provider = provider or scene.audit.generator_provider
        model = model or scene.audit.generator_model
        workspace_json = response.model_dump_json()

        # Fail closed on scene_id ownership collisions (same hash, different user).
        # Sync create_v3_workspace raises IntegrityError / 409; async must not overwrite.
        existing = await self.db.fetch_one(
            "SELECT user_id FROM scene_workspaces WHERE scene_id = ?",
            [scene.scene_id],
        )
        if existing is not None and str(existing.get("user_id") or "") not in {"", user_id}:
            raise RuntimeError(
                f"Scene workspace {scene.scene_id} đã thuộc user khác (SCENE_WORKSPACE_EXISTS)."
            )

        await self.db.execute_many([
            (
                """
                UPDATE render_jobs
                SET status = 'completed',
                    provider = ?, model = ?,
                    scene_json = ?, payload_json = ?, warnings_json = ?,
                    renderer = ?, degraded = 0, fallback_source = 'none', ai_source = 'none',
                    response_json = ?, schema_version = '3.0',
                    duration_ms = ?, finished_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [
                    provider,
                    model,
                    scene.model_dump_json(),
                    response.payload.model_dump_json(),
                    json.dumps([issue.message for issue in response.issues], ensure_ascii=False),
                    scene.renderer,
                    workspace_json,
                    duration_ms,
                    job_id,
                ],
            ),
            (
                """
                INSERT INTO history_items (
                  id, user_id, render_job_id, problem_preview, topic, grade, tier, renderer,
                  provider, model, source_type, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'problem', 'completed')
                ON CONFLICT(id) DO UPDATE SET
                  problem_preview = excluded.problem_preview,
                  topic = excluded.topic,
                  grade = excluded.grade,
                  tier = excluded.tier,
                  renderer = excluded.renderer,
                  provider = excluded.provider,
                  model = excluded.model,
                  status = 'completed',
                  updated_at = CURRENT_TIMESTAMP
                """,
                [
                    job_id,
                    user_id,
                    job_id,
                    scene.problem_text[:240],
                    scene.topic,
                    str(scene.grade) if scene.grade is not None else None,
                    request_tier(render_request_json),
                    scene.renderer,
                    provider,
                    model,
                ],
            ),
            (
                """
                INSERT INTO scene_revisions (
                  id, history_item_id, render_job_id, revision_no, change_source, change_summary,
                  scene_json, response_json, schema_version, command_log_json, scene_id, snapshot_revision
                ) VALUES (?, ?, ?, ?, 'render_v3_async', 'Bản dựng v3 (async)', ?, ?, '3.0', '[]', ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                [
                    f"{job_id}:r{scene.revision}",
                    job_id,
                    job_id,
                    scene.revision,
                    scene.model_dump_json(),
                    workspace_json,
                    scene.scene_id,
                    scene.revision,
                ],
            ),
            (
                """
                INSERT INTO scene_workspaces (
                  scene_id, user_id, history_item_id, revision, scene_json, status, verification_json, issues_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scene_id) DO UPDATE SET
                  history_item_id = excluded.history_item_id,
                  revision = excluded.revision,
                  scene_json = excluded.scene_json,
                  status = excluded.status,
                  verification_json = excluded.verification_json,
                  issues_json = excluded.issues_json
                WHERE scene_workspaces.user_id = excluded.user_id
                """,
                [
                    scene.scene_id,
                    user_id,
                    job_id,
                    scene.revision,
                    scene.model_dump_json(),
                    response.status,
                    json.dumps([item.model_dump(mode="json") for item in response.verification], ensure_ascii=False),
                    json.dumps([item.model_dump(mode="json") for item in response.issues], ensure_ascii=False),
                ],
            ),
        ])
        # If ON CONFLICT WHERE blocked the update (other owner), fail closed.
        # Only assert ownership — not history_item_id — so concurrent same-user
        # re-renders of the same scene_id do not false-fail after a later write.
        workspace_row = await self.db.fetch_one(
            "SELECT user_id FROM scene_workspaces WHERE scene_id = ?",
            [scene.scene_id],
        )
        if workspace_row is None or str(workspace_row.get("user_id") or "") != user_id:
            raise RuntimeError(
                f"Không ghi được scene_workspaces cho {scene.scene_id} (ownership conflict)."
            )

        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        if row is None:
            raise RuntimeError("Không thể hoàn tất job render v3.")
        return render_job_from_row(row)

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
        job = render_job_from_row(row)
        await self.ensure_history_item(job, response=response, tier=request_tier(render_request_json))
        return job

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

    async def claim_next_queued(self) -> RenderJobRecord | None:
        """Atomically claim the oldest queued render job (best-effort across backends)."""
        row = await self.db.fetch_one(
            """
            SELECT id FROM render_jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        if row is None:
            return None
        job_id = str(row["id"])
        claimed = await self.db.fetch_one(
            """
            UPDATE render_jobs
            SET status = 'running', started_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'queued'
            RETURNING *
            """,
            [job_id],
        )
        return render_job_from_row(claimed) if claimed else None

    async def find_by_id(self, job_id: str) -> RenderJobRecord | None:
        row = await self.db.fetch_one("SELECT * FROM render_jobs WHERE id = ?", [job_id])
        return render_job_from_row(row) if row else None

    async def mark_completed(
        self,
        job_id: str,
        response: RenderResponse,
        renderer: str | None,
        *,
        duration_ms: int | None = None,
    ) -> None:
        await self.db.execute(
            """
            UPDATE render_jobs
            SET status = 'completed', scene_json = ?, payload_json = ?, warnings_json = ?, renderer = ?,
                degraded = ?, fallback_source = ?, ai_source = ?, response_json = ?, schema_version = ?,
                duration_ms = ?, finished_at = CURRENT_TIMESTAMP
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
                duration_ms,
                job_id,
            ],
        )

    async def mark_failed(self, job_id: str, error: dict, *, duration_ms: int | None = None) -> None:
        await self.db.execute(
            """
            UPDATE render_jobs
            SET status = 'failed', error_json = ?, duration_ms = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [json.dumps(error, ensure_ascii=False), duration_ms, job_id],
        )

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 30,
        *,
        q: str | None = None,
        renderer: str | None = None,
        topic: str | None = None,
        favorite: bool | None = None,
        archived: bool | None = None,
    ) -> list[RenderJobRecord]:
        clauses = ["r.user_id = ?", "r.status = 'completed'", "r.response_json IS NOT NULL"]
        params: list[object] = [user_id]
        if q:
            clauses.append("(lower(r.problem_text) LIKE ? OR lower(COALESCE(h.title, '')) LIKE ? OR r.id LIKE ?)")
            params.extend([f"%{q.lower()}%", f"%{q.lower()}%", f"%{q}%"])
        if renderer:
            clauses.append("COALESCE(h.renderer, r.renderer) = ?")
            params.append(renderer)
        if topic:
            clauses.append("COALESCE(h.topic, 'unknown') = ?")
            params.append(topic)
        if favorite is not None:
            clauses.append("COALESCE(h.is_favorite, 0) = ?")
            params.append(1 if favorite else 0)
        if archived is False:
            clauses.append("h.archived_at IS NULL")
        elif archived is True:
            clauses.append("h.archived_at IS NOT NULL")
        params.append(min(max(limit, 1), 100))
        rows = await self.db.fetch_all(
            f"""
            SELECT r.id, r.user_id, r.problem_text, r.provider, r.model, r.warnings_json, r.created_at, r.source_type, r.renderer,
                   r.status, r.error_json, r.started_at, r.finished_at, r.degraded, r.fallback_source, r.ai_source, r.schema_version,
                   h.id AS history_item_id, h.title, h.problem_preview, h.topic, h.grade, h.tier, h.is_favorite, h.archived_at,
                   h.last_opened_at, h.updated_at AS history_updated_at
            FROM render_jobs r
            LEFT JOIN history_items h ON h.render_job_id = r.id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(h.updated_at, r.created_at) DESC
            LIMIT ?
            """,
            params,
        )
        return [render_job_from_row(row) for row in rows]

    async def find_for_user(self, user_id: str, job_id: str) -> RenderJobRecord | None:
        row = await self.db.fetch_one(
            """
            SELECT r.*, h.id AS history_item_id, h.title, h.problem_preview, h.topic, h.grade, h.tier, h.is_favorite,
                   h.archived_at, h.last_opened_at, h.updated_at AS history_updated_at
            FROM render_jobs r
            LEFT JOIN history_items h ON h.render_job_id = r.id
            WHERE r.user_id = ? AND r.id = ?
            """,
            [user_id, job_id],
        )
        if row:
            await self.db.execute("UPDATE history_items SET last_opened_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE render_job_id = ? AND user_id = ?", [job_id, user_id])
        return render_job_from_row(row) if row else None

    async def delete_for_user(self, user_id: str, job_id: str) -> None:
        await self.db.execute("DELETE FROM render_jobs WHERE user_id = ? AND id = ?", [user_id, job_id])

    async def ensure_history_item(self, job: RenderJobRecord, *, response: RenderResponse | None = None, tier: str | None = None) -> None:
        if job.user_id is None:
            return
        topic = response.scene.topic if response else "unknown"
        grade = str(response.scene.grade) if response and response.scene.grade is not None else None
        await self.db.execute(
            """
            INSERT INTO history_items (
              id, user_id, render_job_id, problem_preview, topic, grade, tier, renderer, provider, model,
              source_type, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(render_job_id) DO UPDATE SET
              problem_preview = excluded.problem_preview,
              topic = excluded.topic,
              grade = excluded.grade,
              tier = COALESCE(excluded.tier, history_items.tier),
              renderer = excluded.renderer,
              provider = excluded.provider,
              model = excluded.model,
              source_type = excluded.source_type,
              status = excluded.status,
              updated_at = CURRENT_TIMESTAMP
            """,
            [
                job.id,
                job.user_id,
                job.id,
                job.problem_text[:240],
                topic,
                grade,
                tier,
                job.renderer,
                job.provider,
                job.model,
                job.source_type,
                job.status,
                job.created_at,
            ],
        )
        await self.db.execute(
            """
            INSERT INTO scene_revisions (
              id, history_item_id, render_job_id, revision_no, change_source, change_summary, scene_json, response_json, created_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(history_item_id, revision_no) DO NOTHING
            """,
            [f"{job.id}:r1", job.id, job.id, job.source_type, "Bản dựng đầu tiên", job.scene_json, job.response_json, job.created_at],
        )

    async def patch_item(self, user_id: str, job_id: str, patch: dict) -> RenderJobRecord | None:
        job = await self.find_for_user(user_id, job_id)
        if job is None:
            return None
        await self.ensure_history_item(job)
        assignments: list[str] = []
        params: list[object] = []
        for field in ("title", "project_id", "is_favorite"):
            if field in patch:
                assignments.append(f"{field} = ?")
                value = patch[field]
                params.append(1 if field == "is_favorite" and value else 0 if field == "is_favorite" else value)
        if "archived" in patch:
            assignments.append("archived_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END")
            params.append(1 if patch["archived"] else 0)
        if assignments:
            params.extend([job_id, user_id])
            await self.db.execute(
                f"UPDATE history_items SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE render_job_id = ? AND user_id = ?",
                params,
            )
        if "tags" in patch:
            await self.replace_tags(user_id, job_id, patch["tags"] or [])
        return await self.find_for_user(user_id, job_id)

    async def replace_tags(self, user_id: str, job_id: str, tags: list[str]) -> None:
        item = await self.db.fetch_one("SELECT id FROM history_items WHERE user_id = ? AND render_job_id = ?", [user_id, job_id])
        if item is None:
            return
        history_item_id = str(item["id"])
        await self.db.execute("DELETE FROM history_item_tags WHERE history_item_id = ?", [history_item_id])
        for label in tags:
            tag_id = f"{user_id}:{label.lower()}"
            await self.db.execute(
                """
                INSERT INTO history_tags (id, user_id, label, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, label) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                [tag_id, user_id, label],
            )
            row = await self.db.fetch_one("SELECT id FROM history_tags WHERE user_id = ? AND label = ?", [user_id, label])
            if row:
                await self.db.execute(
                    "INSERT INTO history_item_tags (history_item_id, tag_id) VALUES (?, ?) ON CONFLICT(history_item_id, tag_id) DO NOTHING",
                    [history_item_id, row["id"]],
                )

    async def tags_for_item(self, history_item_id: str | None) -> list[str]:
        if not history_item_id:
            return []
        rows = await self.db.fetch_all(
            """
            SELECT t.label
            FROM history_item_tags it
            JOIN history_tags t ON t.id = it.tag_id
            WHERE it.history_item_id = ?
            ORDER BY t.label ASC
            """,
            [history_item_id],
        )
        return [str(row["label"]) for row in rows]

    async def list_revisions_for_user(self, user_id: str, job_id: str) -> list[SceneRevisionRecord]:
        rows = await self.db.fetch_all(
            """
            SELECT sr.*
            FROM scene_revisions sr
            JOIN history_items h ON h.id = sr.history_item_id
            WHERE h.user_id = ? AND h.render_job_id = ?
            ORDER BY sr.revision_no DESC
            """,
            [user_id, job_id],
        )
        return [scene_revision_from_row(row) for row in rows]

    async def find_v3_snapshot_for_user(
        self,
        user_id: str,
        job_id: str,
        snapshot_revision: int | None = None,
    ) -> SceneRevisionRecord | None:
        revision_clause = "AND sr.snapshot_revision = ?" if snapshot_revision is not None else ""
        params: list[object] = [user_id, job_id]
        if snapshot_revision is not None:
            params.append(snapshot_revision)
        row = await self.db.fetch_one(
            f"""
            SELECT sr.*
            FROM scene_revisions sr
            JOIN history_items h ON h.id = sr.history_item_id
            WHERE h.user_id = ? AND h.render_job_id = ? AND sr.schema_version = '3.0'
              {revision_clause}
            ORDER BY sr.snapshot_revision DESC
            LIMIT 1
            """,
            params,
        )
        return scene_revision_from_row(row) if row else None


def request_tier(render_request_json: str | None) -> str | None:
    if not render_request_json:
        return None
    try:
        parsed = json.loads(render_request_json)
    except json.JSONDecodeError:
        return None
    tier = parsed.get("tier") if isinstance(parsed, dict) else None
    return str(tier) if tier else None


def scene_revision_from_row(row: DbRow) -> SceneRevisionRecord:
    return SceneRevisionRecord(
        id=str(row["id"]),
        history_item_id=str(row["history_item_id"]),
        render_job_id=str(row["render_job_id"]) if row.get("render_job_id") is not None else None,
        revision_no=int(row["revision_no"]),
        change_source=str(row.get("change_source") or "render"),
        change_summary=str(row["change_summary"]) if row.get("change_summary") is not None else None,
        scene_json=str(row["scene_json"]),
        response_json=str(row["response_json"]) if row.get("response_json") is not None else None,
        created_at=str(row["created_at"]),
        schema_version=str(row.get("schema_version") or "2.0"),
        command_log_json=str(row.get("command_log_json") or "[]"),
        scene_id=str(row["scene_id"]) if row.get("scene_id") is not None else None,
        snapshot_revision=int(row["snapshot_revision"]) if row.get("snapshot_revision") is not None else None,
    )


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
        history_item_id=str(row["history_item_id"]) if row.get("history_item_id") is not None else None,
        title=str(row["title"]) if row.get("title") is not None else None,
        problem_preview=str(row["problem_preview"]) if row.get("problem_preview") is not None else None,
        topic=str(row.get("topic") or "unknown"),
        grade=str(row["grade"]) if row.get("grade") is not None else None,
        tier=str(row["tier"]) if row.get("tier") is not None else None,
        is_favorite=bool(row.get("is_favorite") or 0),
        archived_at=str(row["archived_at"]) if row.get("archived_at") is not None else None,
        last_opened_at=str(row["last_opened_at"]) if row.get("last_opened_at") is not None else None,
        history_updated_at=str(row["history_updated_at"]) if row.get("history_updated_at") is not None else None,
        duration_ms=int(row["duration_ms"]) if row.get("duration_ms") is not None else None,
    )
