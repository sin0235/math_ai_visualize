from __future__ import annotations

import json
from dataclasses import dataclass

from app.db.session import DatabaseClient
from app.schemas.scene_v3 import MathSceneV3, SceneCommand
from app.services.scene_commands_v3 import AppliedSceneCommand
from app.services.scene_pipeline_v3 import ScenePipelineV3Result


@dataclass(frozen=True)
class SceneWorkspaceRecord:
    scene: MathSceneV3
    status: str
    verification_json: str
    issues_json: str
    history_item_id: str | None


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
            "SELECT * FROM scene_workspaces WHERE scene_id = ? AND user_id = ?",
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
        )

    async def commit_command(
        self,
        user_id: str,
        command: SceneCommand,
        applied: AppliedSceneCommand,
        result: ScenePipelineV3Result,
        history_item_id: str | None,
    ) -> None:
        await self.db.execute_many([
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
        ])


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