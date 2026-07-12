from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas.render_projection_v3 import RenderProjectionV3
from app.schemas.scene_v3 import ConstraintResultV3, MathSceneV3, SceneObjectV3
from app.services.geometry_kernel import build_constraint_graph, build_geometry_index, verify_constraints
from app.services.relation_registry import validate_v3_relation_operands
from app.services.render_projection_v3 import ProjectionError, build_render_projection_v3


PipelineStage = Literal["structure", "topology", "derive", "verify", "repair", "project"]
PipelineErrorCode = Literal[
    "SCENE_SCHEMA_INVALID",
    "REFERENCE_NOT_FOUND",
    "REFERENCE_KIND_MISMATCH",
    "RELATION_CONTRACT_INVALID",
    "CONSTRAINT_FAILED",
    "CONSTRAINT_UNVERIFIABLE",
    "REPAIR_CONFIRMATION_REQUIRED",
    "RENDERER_UNSUPPORTED",
]
PipelineStatus = Literal["verified", "partially_verified", "needs_confirmation", "failed"]


@dataclass(frozen=True)
class PipelineIssueV3:
    stage: PipelineStage
    code: PipelineErrorCode
    message: str
    severity: Literal["info", "warning", "error"]
    target_id: str | None = None


@dataclass(frozen=True)
class ScenePipelineV3Result:
    status: PipelineStatus
    scene: MathSceneV3
    verification: tuple[ConstraintResultV3, ...]
    issues: tuple[PipelineIssueV3, ...]
    requires_user_confirmation: bool
    projection: RenderProjectionV3 | None = None

    @property
    def can_project(self) -> bool:
        return self.projection is not None and not any(issue.severity == "error" and issue.stage in {"structure", "topology", "project"} for issue in self.issues)


def run_scene_pipeline_v3(scene: MathSceneV3) -> ScenePipelineV3Result:
    topology_issues = validate_scene_topology(scene)
    if any(issue.severity == "error" for issue in topology_issues):
        return ScenePipelineV3Result(
            status="failed",
            scene=scene,
            verification=(),
            issues=topology_issues,
            requires_user_confirmation=True,
        )

    index = build_geometry_index(scene)
    verification = verify_constraints(scene, index)
    verification_issues = tuple(issue for result in verification if (issue := _verification_issue(result)) is not None)
    verified_scene = _attach_verification(scene, verification)
    issues = (*topology_issues, *verification_issues)
    status = _pipeline_status(verification)
    try:
        projection = build_render_projection_v3(verified_scene)
    except ProjectionError as error:
        projection_issue = PipelineIssueV3(
            stage="project",
            code="RENDERER_UNSUPPORTED",
            message=error.message,
            severity="error",
            target_id=error.unsupported_ids[0] if error.unsupported_ids else None,
        )
        return ScenePipelineV3Result(
            status="failed",
            scene=verified_scene,
            verification=verification,
            issues=(*issues, projection_issue),
            requires_user_confirmation=True,
        )
    return ScenePipelineV3Result(
        status=status,
        scene=verified_scene,
        verification=verification,
        issues=issues,
        requires_user_confirmation=status != "verified",
        projection=projection,
    )


def validate_scene_topology(scene: MathSceneV3) -> tuple[PipelineIssueV3, ...]:
    object_kinds = {obj.id: object_reference_kind(obj) for obj in scene.objects}
    issues: list[PipelineIssueV3] = []
    for relation in scene.relations:
        for operand in relation.operands:
            actual = object_kinds.get(operand.ref_id)
            if actual is None:
                issues.append(PipelineIssueV3(
                    stage="topology",
                    code="REFERENCE_NOT_FOUND",
                    message=f"Relation {relation.id} tham chiếu object không tồn tại.",
                    severity="error",
                    target_id=relation.id,
                ))
            elif operand.ref_kind != "object" and operand.ref_kind != actual:
                issues.append(PipelineIssueV3(
                    stage="topology",
                    code="REFERENCE_KIND_MISMATCH",
                    message=f"Operand {operand.role} khai báo {operand.ref_kind}, object thực tế là {actual}.",
                    severity="error",
                    target_id=relation.id,
                ))
        contract_errors = validate_v3_relation_operands(
            relation.type,
            [operand.ref_kind if operand.ref_kind != "object" else object_kinds.get(operand.ref_id, "object") for operand in relation.operands],
            scene.view.dimension,
        )
        issues.extend(
            PipelineIssueV3(
                stage="topology",
                code="RELATION_CONTRACT_INVALID",
                message=message,
                severity="error",
                target_id=relation.id,
            )
            for message in contract_errors
        )
    return tuple(issues)


def affected_relation_ids(scene: MathSceneV3, changed_object_ids: set[str]) -> frozenset[str]:
    return build_constraint_graph(scene).affected_relations(changed_object_ids)


def object_reference_kind(obj: SceneObjectV3) -> str:
    return {
        "point_2d": "point",
        "point_3d": "point",
        "segment": "segment",
        "line_2d": "line",
        "line_3d": "line",
        "vector_2d": "vector",
        "vector_3d": "vector",
        "circle_2d": "circle",
        "face": "face",
        "sphere": "sphere",
        "plane": "plane",
    }.get(obj.type, "object")


def _attach_verification(scene: MathSceneV3, results: tuple[ConstraintResultV3, ...]) -> MathSceneV3:
    by_id = {result.relation_id: result for result in results}
    relations = [
        relation.model_copy(update={"verification": by_id.get(relation.id)})
        for relation in scene.relations
    ]
    return scene.model_copy(update={"relations": relations})


def _verification_issue(result: ConstraintResultV3) -> PipelineIssueV3 | None:
    if result.status == "verified":
        return None
    if result.status == "failed":
        return PipelineIssueV3(
            stage="verify",
            code="CONSTRAINT_FAILED",
            message=result.message or f"Relation {result.relation_id} không thỏa ràng buộc.",
            severity="error",
            target_id=result.relation_id,
        )
    return PipelineIssueV3(
        stage="verify",
        code="CONSTRAINT_UNVERIFIABLE",
        message=result.message or f"Relation {result.relation_id} chưa thể kiểm chứng.",
        severity="warning",
        target_id=result.relation_id,
    )


def _pipeline_status(results: tuple[ConstraintResultV3, ...]) -> PipelineStatus:
    statuses = {result.status for result in results}
    if "failed" in statuses or "error" in statuses:
        return "partially_verified"
    if statuses.intersection({"unsupported", "unverifiable"}):
        return "needs_confirmation"
    return "verified"