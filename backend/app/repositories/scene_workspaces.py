from __future__ import annotations

import json
from dataclasses import dataclass

from app.db.session import DatabaseClient
from app.schemas.scene_v3 import MathSceneV3, SceneCommand, SceneWorkspaceResponseV3
from app.services.scene_commands_v3 import AppliedSceneCommand
from app.services.scene_pipeline_v3 import ScenePipelineV3Result


@dataclass(frozen=True)
class SceneWorkspaceRecord:
    scene: MathSceneV3
    status: str
    verification_json: str
    issues_json: str
    history_item_id: str | None
    confirmed_revision: int | None


class SceneWorkspaceRepository:
    def __init__(self, db: DatabaseClient) -> None:
        self.db = db

    async def create(self, user_id: str, result: ScenePipelineV3Result, history_item_id: str | None = None) -> None:
        await self.db.execute(
            """
            INSERT INTO scene_workspaces (
              scene_id, user_id, history_item_id, revision, scene_json, status, verification_json, issues_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.scene.scene_id,
                user_id,
                history_item_id,
                result.scene.revision,
                result.scene.model_dump_json(),
                result.status,
                _verification_json(result),
                _issues_json(result),
            ],
        )

    async def find_for_user(self, user_id: str, scene_id: str) -> SceneWorkspaceRecord | None:
        row = await self.db.fetch_one(
            """
            SELECT sw.*, sc.revision AS confirmed_revision
            FROM scene_workspaces sw
            LEFT JOIN scene_confirmations sc
              ON sc.user_id = sw.user_id
             AND sc.scene_id = sw.scene_id
             AND sc.revision = sw.revision
            WHERE sw.scene_id = ? AND sw.user_id = ?
            """,
            [scene_id, user_id],
        )
        if row is None:
            return None
        return SceneWorkspaceRecord(
            scene=MathSceneV3.model_validate_json(str(row["scene_json"])),
            status=str(row["status"]),
            verification_json=str(row["verification_json"]),
            issues_json=str(row["issues_json"]),
            history_item_id=str(row["history_item_id"]) if row.get("history_item_id") else None,
            confirmed_revision=int(row["confirmed_revision"]) if row.get("confirmed_revision") is not None else None,
        )

    async def confirm_revision(self, user_id: str, scene_id: str, revision: int) -> None:
        snapshot = await self.db.fetch_one(
            """
            SELECT sr.id, sr.response_json
            FROM scene_revisions sr
            JOIN scene_workspaces sw ON sw.history_item_id = sr.history_item_id
            WHERE sw.user_id = ? AND sw.scene_id = ? AND sr.snapshot_revision = ?
            LIMIT 1
            """,
            [user_id, scene_id, revision],
        )
        statements = [(
            """
            INSERT INTO scene_confirmations (user_id, scene_id, revision)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, scene_id, revision) DO NOTHING
            """,
            [user_id, scene_id, revision],
        )]
        if snapshot is not None and snapshot.get("response_json"):
            response = SceneWorkspaceResponseV3.model_validate_json(str(snapshot["response_json"]))
            confirmed = response.model_copy(update={"confirmed_revision": revision, "trusted_for_downstream": True})
            statements.append((
                "UPDATE scene_revisions SET response_json = ? WHERE id = ?",
                [confirmed.model_dump_json(), snapshot["id"]],
            ))
        await self.db.execute_many(statements)

    async def restore_snapshot(
        self,
        user_id: str,
        history_item_id: str,
        workspace: SceneWorkspaceResponseV3,
    ) -> None:
        scene = workspace.scene
        statements = [
            ("DELETE FROM scene_commands WHERE scene_id = ? AND user_id = ?", [scene.scene_id, user_id]),
            ("DELETE FROM scene_confirmations WHERE scene_id = ? AND user_id = ?", [scene.scene_id, user_id]),
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
                  issues_json = excluded.issues_json,
                  updated_at = CURRENT_TIMESTAMP
                WHERE scene_workspaces.user_id = excluded.user_id
                """,
                [
                    scene.scene_id,
                    user_id,
                    history_item_id,
                    scene.revision,
                    scene.model_dump_json(),
                    workspace.status,
                    json.dumps([item.model_dump(mode="json") for item in workspace.verification], ensure_ascii=False),
                    json.dumps([item.model_dump(mode="json") for item in workspace.issues], ensure_ascii=False),
                ],
            ),
        ]
        if workspace.confirmed_revision == scene.revision:
            statements.append((
                "INSERT INTO scene_confirmations (user_id, scene_id, revision) VALUES (?, ?, ?)",
                [user_id, scene.scene_id, scene.revision],
            ))
        await self.db.execute_many(statements)

    async def commit_command(
        self,
        user_id: str,
        command: SceneCommand,
        applied: AppliedSceneCommand,
        result: ScenePipelineV3Result,
        history_item_id: str | None,
    ) -> None:
        previous_commands = await self.db.fetch_all(
            """
            SELECT command_json FROM scene_commands
            WHERE scene_id = ? AND user_id = ?
            ORDER BY result_revision ASC
            """,
            [command.scene_id, user_id],
        )
        command_log = [json.loads(str(row["command_json"])) for row in previous_commands]
        command_log.append(command.model_dump(mode="json"))
        workspace_json = _workspace_response_json(result, applied)
        statements = [
            (
                """
                INSERT INTO scene_commands (
                  id, scene_id, user_id, history_item_id, base_revision, result_revision,
                  command_type, command_json, inverse_command_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    command.command_id,
                    command.scene_id,
                    user_id,
                    history_item_id,
                    command.base_revision,
                    result.scene.revision,
                    command.type,
                    command.model_dump_json(),
                    applied.inverse.model_dump_json(),
                ],
            ),
            (
                """
                UPDATE scene_workspaces
                SET revision = ?, scene_json = ?, status = ?, verification_json = ?, issues_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE scene_id = ? AND user_id = ? AND revision = ?
                """,
                [
                    result.scene.revision,
                    result.scene.model_dump_json(),
                    result.status,
                    _verification_json(result),
                    _issues_json(result),
                    command.scene_id,
                    user_id,
                    command.base_revision,
                ],
            ),
        ]
        if history_item_id is not None:
            statements.extend([
                (
                    """
                    INSERT INTO scene_revisions (
                      id, history_item_id, render_job_id, revision_no, change_source, change_summary,
                      scene_json, response_json, schema_version, command_log_json, scene_id, snapshot_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '3.0', ?, ?, ?)
                    """,
                    [
                        f"{history_item_id}:r{result.scene.revision}",
                        history_item_id,
                        history_item_id,
                        result.scene.revision,
                        command.type,
                        f"Command {command.type}",
                        result.scene.model_dump_json(),
                        workspace_json,
                        json.dumps(command_log, ensure_ascii=False),
                        result.scene.scene_id,
                        result.scene.revision,
                    ],
                ),
                (
                    """
                    UPDATE render_jobs
                    SET scene_json = ?, payload_json = ?, response_json = ?, schema_version = '3.0', renderer = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    [
                        result.scene.model_dump_json(),
                        _payload_json(result),
                        workspace_json,
                        result.scene.renderer,
                        history_item_id,
                        user_id,
                    ],
                ),
                (
                    "UPDATE history_items SET updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    [history_item_id, user_id],
                ),
            ])
        await self.db.execute_many(statements)


def _verification_json(result: ScenePipelineV3Result) -> str:
    return json.dumps([item.model_dump(mode="json") for item in result.verification], ensure_ascii=False)


def _issues_json(result: ScenePipelineV3Result) -> str:
    return json.dumps([
        {
            "stage": issue.stage,
            "code": issue.code,
            "message": issue.message,
            "severity": issue.severity,
            "target_id": issue.target_id,
        }
        for issue in result.issues
    ], ensure_ascii=False)


def _payload_json(result: ScenePipelineV3Result) -> str:
    from app.services.renderer_router import build_render_payload_v3

    if result.projection is None:
        raise ValueError("Scene v3 không có render projection.")
    return build_render_payload_v3(result.projection).model_dump_json()


def _workspace_response_json(result: ScenePipelineV3Result, applied: AppliedSceneCommand) -> str:
    from app.schemas.scene_v3 import SceneWorkspaceResponseV3
    from app.services.renderer_router import build_render_payload_v3

    if result.projection is None:
        raise ValueError("Scene v3 không có render projection.")
    return SceneWorkspaceResponseV3(
        status=result.status,
        scene=result.scene,
        projection=result.projection,
        payload=build_render_payload_v3(result.projection),
        verification=list(result.verification),
        issues=[
            {
                "stage": issue.stage,
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
                "target_id": issue.target_id,
            }
            for issue in result.issues
        ],
        requires_user_confirmation=result.requires_user_confirmation,
        trusted_for_downstream=result.status == "verified",
        inverse_command=applied.inverse,
        changed_object_ids=sorted(applied.changed_object_ids),
        affected_relation_ids=sorted(applied.affected_relation_ids),
    ).model_dump_json()