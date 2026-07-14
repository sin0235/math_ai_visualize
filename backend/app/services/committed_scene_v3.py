from __future__ import annotations

from dataclasses import dataclass

from app.db.session import DatabaseClient
from app.repositories.scene_workspaces import SceneWorkspaceRecord, SceneWorkspaceRepository
from app.schemas.scene_v3 import CommittedSceneRefV3
from app.services.scene_pipeline_v3 import ScenePipelineV3Result, run_scene_pipeline_v3


class CommittedSceneError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class CommittedSceneV3:
    workspace: SceneWorkspaceRecord
    result: ScenePipelineV3Result
    trusted_for_downstream: bool


async def load_committed_scene_v3(
    db: DatabaseClient,
    user_id: str,
    reference: CommittedSceneRefV3,
    *,
    require_trusted: bool = True,
) -> CommittedSceneV3:
    workspace = await SceneWorkspaceRepository(db).find_for_user(user_id, reference.scene_id)
    if workspace is None:
        raise CommittedSceneError("SCENE_WORKSPACE_NOT_FOUND", "Không tìm thấy scene workspace.", 404)
    if workspace.scene.revision != reference.revision:
        raise CommittedSceneError(
            "SCENE_EDIT_STALE",
            f"Revision không còn hiện hành: cần {workspace.scene.revision}, nhận {reference.revision}.",
            409,
        )

    result = run_scene_pipeline_v3(workspace.scene)
    trusted = result.status == "verified" or (
        result.status == "needs_confirmation" and workspace.confirmed_revision == reference.revision
    )
    if require_trusted and not trusted:
        if result.status == "needs_confirmation":
            raise CommittedSceneError(
                "SCENE_TRUST_REQUIRED",
                "Scene cần được người dùng xác nhận trước khi dùng cho chức năng downstream.",
                409,
            )
        if result.status in {"failed", "partially_verified"}:
            raise CommittedSceneError(
                "CONSTRAINT_FAILED",
                "Scene có ràng buộc chưa đạt kiểm chứng.",
                422,
            )
        issue = next((item for item in result.issues if item.severity == "error"), None)
        raise CommittedSceneError(
            issue.code if issue is not None else "SCENE_SCHEMA_INVALID",
            issue.message if issue is not None else "Scene không vượt qua pipeline v3.",
            422,
        )
    return CommittedSceneV3(workspace=workspace, result=result, trusted_for_downstream=trusted)


async def confirm_committed_scene_v3(
    db: DatabaseClient,
    user_id: str,
    reference: CommittedSceneRefV3,
) -> CommittedSceneV3:
    committed = await load_committed_scene_v3(db, user_id, reference, require_trusted=False)
    if committed.result.status not in {"verified", "needs_confirmation"}:
        raise CommittedSceneError(
            "CONSTRAINT_FAILED",
            "Không thể xác nhận scene có constraint failed hoặc unverifiable một phần.",
            422,
        )
    if committed.result.status == "needs_confirmation":
        await SceneWorkspaceRepository(db).confirm_revision(user_id, reference.scene_id, reference.revision)
        workspace = await SceneWorkspaceRepository(db).find_for_user(user_id, reference.scene_id)
        if workspace is None:
            raise CommittedSceneError("SCENE_WORKSPACE_NOT_FOUND", "Không tìm thấy scene workspace.", 404)
        return CommittedSceneV3(workspace=workspace, result=committed.result, trusted_for_downstream=True)
    return CommittedSceneV3(
        workspace=committed.workspace,
        result=committed.result,
        trusted_for_downstream=True,
    )