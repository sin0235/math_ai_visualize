from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.render_projection_v3 import RenderPayloadV3, RenderProjectionV3
from app.schemas.scene import ExportViewCapture, ObjectSource, RelationSource, Renderer, SceneView, Topic


SchemaVersion = Literal["3.0"]
Dimension = Literal["2d", "3d"]
ReferenceKind = Literal["point", "segment", "line", "vector", "circle", "face", "sphere", "plane", "object"]
VerificationStatusV3 = Literal["verified", "failed", "unsupported", "unverifiable", "error"]
DerivedFactKind = Literal["intersection", "measurement", "annotation", "display_edge", "normal_vector"]
DerivedFactProvenance = Literal["given", "verified", "computed", "render_only"]
CommandKind = Literal[
    "move_point",
    "add_point",
    "delete_object",
    "restore_object",
    "remove_generated",
    "restore_generated",
    "connect_points",
    "project_point",
    "intersect_objects",
    "set_parameter",
    "set_visibility",
]


class V3Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SceneObjectBaseV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    label: str | None = Field(default=None, max_length=128)
    source: ObjectSource = "ai_inferred"
    locked: bool = False
    user_edited: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Point2DV3(SceneObjectBaseV3):
    type: Literal["point_2d"] = "point_2d"
    x: float
    y: float
    x_expr: str | None = None
    y_expr: str | None = None


class Point3DV3(SceneObjectBaseV3):
    type: Literal["point_3d"] = "point_3d"
    x: float
    y: float
    z: float
    x_expr: str | None = None
    y_expr: str | None = None
    z_expr: str | None = None


class SegmentV3(SceneObjectBaseV3):
    type: Literal["segment"] = "segment"
    point_ids: tuple[str, str]
    hidden: bool = False
    color: str | None = None
    line_width: float | None = None
    style: Literal["solid", "dashed", "dotted"] | None = None


class Line2DV3(SceneObjectBaseV3):
    type: Literal["line_2d"] = "line_2d"
    point_ids: tuple[str, str]


class Line3DV3(SceneObjectBaseV3):
    type: Literal["line_3d"] = "line_3d"
    point_ids: tuple[str, str]
    color: str = "#1d3557"


class Vector2DV3(SceneObjectBaseV3):
    type: Literal["vector_2d"] = "vector_2d"
    from_point_id: str
    to_point_id: str


class Vector3DV3(SceneObjectBaseV3):
    type: Literal["vector_3d"] = "vector_3d"
    from_point_id: str
    to_point_id: str
    color: str = "#7c3aed"


class Circle2DV3(SceneObjectBaseV3):
    type: Literal["circle_2d"] = "circle_2d"
    center_point_id: str
    through_point_id: str | None = None
    radius: float | None = None
    radius_expr: str | None = None


class FunctionGraphV3(SceneObjectBaseV3):
    type: Literal["function_graph"] = "function_graph"
    expression: str
    domain: tuple[float | str, float | str] | None = None
    left_open: bool = False
    right_open: bool = False
    component_id: str | None = None


class FaceV3(SceneObjectBaseV3):
    type: Literal["face"] = "face"
    point_ids: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = Field(default=0.22, ge=0, le=1)


class SphereV3(SceneObjectBaseV3):
    type: Literal["sphere"] = "sphere"
    center_point_id: str
    radius: float = Field(gt=0)
    radius_expr: str | None = None
    color: str = "#5da9ff"
    opacity: float = Field(default=0.18, ge=0, le=1)


class PlaneV3(SceneObjectBaseV3):
    type: Literal["plane"] = "plane"
    point_ids: list[str] = Field(min_length=3)
    color: str = "#4f8cff"
    opacity: float = Field(default=0.16, ge=0, le=1)
    show_normal: bool = True


SceneObjectV3 = Annotated[
    Point2DV3
    | Point3DV3
    | SegmentV3
    | Line2DV3
    | Line3DV3
    | Vector2DV3
    | Vector3DV3
    | Circle2DV3
    | FunctionGraphV3
    | FaceV3
    | SphereV3
    | PlaneV3,
    Field(discriminator="type"),
]


class RelationOperandV3(V3Model):
    role: str = Field(min_length=1, max_length=64)
    ref_id: str = Field(min_length=1, max_length=128)
    ref_kind: ReferenceKind


class ConstraintResultV3(V3Model):
    relation_id: str
    status: VerificationStatusV3
    verifier: str
    tolerance: float | None = Field(default=None, ge=0)
    residual: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class RelationV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=64)
    operands: list[RelationOperandV3] = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    source: RelationSource = "ai_inferred"
    verification: ConstraintResultV3 | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def verification_matches_relation(self) -> "RelationV3":
        if self.verification is not None and self.verification.relation_id != self.id:
            raise ValueError("verification.relation_id phải khớp relation.id")
        return self


class AnnotationV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=64)
    target_ids: list[str] = Field(min_length=1)
    label: str | None = None
    color: str | None = None
    provenance: DerivedFactProvenance = "render_only"
    relation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DerivedFactV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    kind: DerivedFactKind
    source_ids: list[str] = Field(default_factory=list)
    value: dict[str, Any] = Field(default_factory=dict)
    provenance: DerivedFactProvenance
    relation_id: str | None = None


class ParameterV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=64)
    label: str | None = None
    min: float
    max: float
    default: float
    step: float = Field(default=0.1, gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> "ParameterV3":
        if self.min > self.max or not self.min <= self.default <= self.max:
            raise ValueError("Khoảng hoặc giá trị mặc định của parameter không hợp lệ")
        return self


class ConstructionStepV3(V3Model):
    id: str = Field(min_length=1, max_length=128)
    description: str
    object_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)


class SceneAuditV3(V3Model):
    created_by: str
    generator_provider: str | None = None
    generator_model: str | None = None
    generator_prompt_version: str | None = None
    migrated_from: str | None = None
    updated_at: str | None = None


class SceneInterpretationV3(V3Model):
    object_ids: list[str] = Field(default_factory=list)
    relation_ids: list[str] = Field(default_factory=list)
    values: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class MathSceneV3(V3Model):
    scene_id: str = Field(min_length=1, max_length=128)
    schema_version: SchemaVersion = "3.0"
    revision: int = Field(default=1, ge=1)
    problem_text: str = Field(max_length=20_000)
    grade: int | None = Field(default=None, ge=10, le=12)
    topic: Topic = "unknown"
    renderer: Renderer
    objects: list[SceneObjectV3] = Field(default_factory=list)
    relations: list[RelationV3] = Field(default_factory=list)
    annotations: list[AnnotationV3] = Field(default_factory=list)
    derived_facts: list[DerivedFactV3] = Field(default_factory=list)
    parameters: list[ParameterV3] = Field(default_factory=list)
    view: SceneView
    interpretation: SceneInterpretationV3 = Field(default_factory=SceneInterpretationV3)
    construction_steps: list[ConstructionStepV3] = Field(default_factory=list)
    audit: SceneAuditV3

    @model_validator(mode="after")
    def references_exist_and_are_unique(self) -> "MathSceneV3":
        object_ids = [obj.id for obj in self.objects]
        relation_ids = [relation.id for relation in self.relations]
        all_ids = [*object_ids, *relation_ids, *(annotation.id for annotation in self.annotations), *(fact.id for fact in self.derived_facts)]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("ID trong scene phải duy nhất")

        object_id_set = set(object_ids)
        relation_id_set = set(relation_ids)
        for obj in self.objects:
            missing = set(object_reference_ids(obj)) - object_id_set
            if missing:
                raise ValueError(f"Object {obj.id} tham chiếu ID không tồn tại: {sorted(missing)}")
        for relation in self.relations:
            missing = {operand.ref_id for operand in relation.operands} - object_id_set
            if missing:
                raise ValueError(f"Relation {relation.id} tham chiếu ID không tồn tại: {sorted(missing)}")
        for annotation in self.annotations:
            missing = set(annotation.target_ids) - object_id_set
            if missing:
                raise ValueError(f"Annotation {annotation.id} tham chiếu ID không tồn tại: {sorted(missing)}")
            if annotation.relation_id and annotation.relation_id not in relation_id_set:
                raise ValueError(f"Annotation {annotation.id} tham chiếu relation không tồn tại")
        return self


def object_reference_ids(obj: SceneObjectV3) -> tuple[str, ...]:
    if isinstance(obj, (SegmentV3, Line2DV3, Line3DV3, FaceV3, PlaneV3)):
        return tuple(obj.point_ids)
    if isinstance(obj, (Vector2DV3, Vector3DV3)):
        return obj.from_point_id, obj.to_point_id
    if isinstance(obj, Circle2DV3):
        return tuple(ref for ref in (obj.center_point_id, obj.through_point_id) if ref)
    if isinstance(obj, SphereV3):
        return (obj.center_point_id,)
    return ()


class SceneCommandBase(V3Model):
    command_id: str = Field(min_length=1, max_length=128)
    scene_id: str = Field(min_length=1, max_length=128)
    base_revision: int = Field(ge=1)


class MovePointCommand(SceneCommandBase):
    type: Literal["move_point"] = "move_point"
    point_id: str
    position: tuple[float, float, float]


class AddPointCommand(SceneCommandBase):
    type: Literal["add_point"] = "add_point"
    point: Point2DV3 | Point3DV3


class DeleteObjectCommand(SceneCommandBase):
    type: Literal["delete_object"] = "delete_object"
    object_id: str


class RestoreObjectCommand(SceneCommandBase):
    type: Literal["restore_object"] = "restore_object"
    object: SceneObjectV3


class RemoveGeneratedCommand(SceneCommandBase):
    type: Literal["remove_generated"] = "remove_generated"
    object_ids: list[str] = Field(min_length=1)
    relation_ids: list[str] = Field(default_factory=list)


class RestoreGeneratedCommand(SceneCommandBase):
    type: Literal["restore_generated"] = "restore_generated"
    objects: list[SceneObjectV3] = Field(min_length=1)
    relations: list[RelationV3] = Field(default_factory=list)


class ConnectPointsCommand(SceneCommandBase):
    type: Literal["connect_points"] = "connect_points"
    object_id: str
    start_point_id: str
    end_point_id: str
    connection: Literal["segment", "line"] = "segment"


class ProjectPointCommand(SceneCommandBase):
    type: Literal["project_point"] = "project_point"
    source_point_id: str
    target_id: str
    target_kind: Literal["line", "segment", "plane"]
    result_point_id: str


class IntersectObjectsCommand(SceneCommandBase):
    type: Literal["intersect_objects"] = "intersect_objects"
    object_ids: tuple[str, str]
    result_object_id: str


class SetParameterCommand(SceneCommandBase):
    type: Literal["set_parameter"] = "set_parameter"
    parameter_id: str
    value: float


class SetVisibilityCommand(SceneCommandBase):
    type: Literal["set_visibility"] = "set_visibility"
    object_id: str
    visible: bool


SceneCommand = Annotated[
    MovePointCommand
    | AddPointCommand
    | DeleteObjectCommand
    | RestoreObjectCommand
    | RemoveGeneratedCommand
    | RestoreGeneratedCommand
    | ConnectPointsCommand
    | ProjectPointCommand
    | IntersectObjectsCommand
    | SetParameterCommand
    | SetVisibilityCommand,
    Field(discriminator="type"),
]


class SceneCommandRequest(V3Model):
    command: SceneCommand


class SceneWorkspaceCreateRequest(V3Model):
    scene: MathSceneV3


class CommittedSceneRefV3(V3Model):
    scene_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)


class SceneConfirmationRequestV3(V3Model):
    revision: int = Field(ge=1)


class SceneExportRequestV3(V3Model):
    scene_ref: CommittedSceneRefV3
    view_capture: ExportViewCapture | None = None


class PipelineIssueResponseV3(V3Model):
    stage: Literal["structure", "topology", "derive", "verify", "repair", "project"]
    code: str
    message: str
    severity: Literal["info", "warning", "error"]
    target_id: str | None = None


class SceneWorkspaceResponseV3(V3Model):
    status: Literal["verified", "partially_verified", "needs_confirmation", "failed"]
    scene: MathSceneV3
    projection: RenderProjectionV3
    payload: RenderPayloadV3
    verification: list[ConstraintResultV3] = Field(default_factory=list)
    issues: list[PipelineIssueResponseV3] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    confirmed_revision: int | None = None
    trusted_for_downstream: bool = False
    inverse_command: SceneCommand | None = None
    changed_object_ids: list[str] = Field(default_factory=list)
    affected_relation_ids: list[str] = Field(default_factory=list)


class SceneRevisionV3(V3Model):
    scene_id: str
    revision: int = Field(ge=1)
    parent_revision: int | None = Field(default=None, ge=1)
    command_id: str | None = None
    command_type: CommandKind | None = None
    changed_object_ids: list[str] = Field(default_factory=list)
    affected_relation_ids: list[str] = Field(default_factory=list)