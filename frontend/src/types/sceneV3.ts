import type { ObjectSource, RelationSource, Renderer, SceneView } from './scene';

export type SchemaVersionV3 = '3.0';
export type ReferenceKind = 'point' | 'segment' | 'line' | 'vector' | 'circle' | 'face' | 'sphere' | 'plane' | 'object';
export type VerificationStatusV3 = 'verified' | 'failed' | 'unsupported' | 'unverifiable' | 'error';
export type DerivedFactKind = 'intersection' | 'measurement' | 'annotation' | 'display_edge' | 'normal_vector';
export type DerivedFactProvenance = 'given' | 'verified' | 'computed' | 'render_only';

export interface SceneObjectBaseV3 {
  id: string;
  label?: string | null;
  source: ObjectSource;
  locked: boolean;
  user_edited: boolean;
  metadata: Record<string, unknown>;
}

export interface Point2DV3 extends SceneObjectBaseV3 {
  type: 'point_2d';
  x: number;
  y: number;
  x_expr?: string | null;
  y_expr?: string | null;
}

export interface Point3DV3 extends SceneObjectBaseV3 {
  type: 'point_3d';
  x: number;
  y: number;
  z: number;
  x_expr?: string | null;
  y_expr?: string | null;
  z_expr?: string | null;
}

export interface SegmentV3 extends SceneObjectBaseV3 {
  type: 'segment';
  point_ids: [string, string];
  hidden: boolean;
  color?: string | null;
  line_width?: number | null;
  style?: 'solid' | 'dashed' | 'dotted' | null;
}

export interface LineV3 extends SceneObjectBaseV3 {
  type: 'line_2d' | 'line_3d';
  point_ids: [string, string];
  color?: string;
}

export interface VectorV3 extends SceneObjectBaseV3 {
  type: 'vector_2d' | 'vector_3d';
  from_point_id: string;
  to_point_id: string;
  color?: string;
}

export interface Circle2DV3 extends SceneObjectBaseV3 {
  type: 'circle_2d';
  center_point_id: string;
  through_point_id?: string | null;
  radius?: number | null;
  radius_expr?: string | null;
}

export interface FunctionGraphV3 extends SceneObjectBaseV3 {
  type: 'function_graph';
  expression: string;
  domain?: [number | string, number | string] | null;
  left_open: boolean;
  right_open: boolean;
  component_id?: string | null;
}

export interface FaceV3 extends SceneObjectBaseV3 {
  type: 'face';
  point_ids: string[];
  color: string;
  opacity: number;
}

export interface SphereV3 extends SceneObjectBaseV3 {
  type: 'sphere';
  center_point_id: string;
  radius: number;
  radius_expr?: string | null;
  color: string;
  opacity: number;
}

export interface PlaneV3 extends SceneObjectBaseV3 {
  type: 'plane';
  point_ids: string[];
  color: string;
  opacity: number;
  show_normal: boolean;
}

export type SceneObjectV3 = Point2DV3 | Point3DV3 | SegmentV3 | LineV3 | VectorV3 | Circle2DV3 | FunctionGraphV3 | FaceV3 | SphereV3 | PlaneV3;

export interface RelationOperandV3 {
  role: string;
  ref_id: string;
  ref_kind: ReferenceKind;
}

export interface ConstraintResultV3 {
  relation_id: string;
  status: VerificationStatusV3;
  verifier: string;
  tolerance?: number | null;
  residual?: number | null;
  evidence: Record<string, unknown>;
  message?: string | null;
}

export interface RelationV3 {
  id: string;
  type: string;
  operands: RelationOperandV3[];
  args: Record<string, unknown>;
  source: RelationSource;
  verification?: ConstraintResultV3 | null;
  metadata: Record<string, unknown>;
}

export interface AnnotationV3 {
  id: string;
  type: string;
  target_ids: string[];
  label?: string | null;
  color?: string | null;
  provenance: DerivedFactProvenance;
  relation_id?: string | null;
  metadata: Record<string, unknown>;
}

export interface DerivedFactV3 {
  id: string;
  kind: DerivedFactKind;
  source_ids: string[];
  value: Record<string, unknown>;
  provenance: DerivedFactProvenance;
  relation_id?: string | null;
}

export interface ParameterV3 {
  id: string;
  name: string;
  label?: string | null;
  min: number;
  max: number;
  default: number;
  step: number;
}

export interface ConstructionStepV3 {
  id: string;
  description: string;
  object_ids: string[];
  relation_ids: string[];
}

export interface MathSceneV3 {
  scene_id: string;
  schema_version: SchemaVersionV3;
  revision: number;
  problem_text: string;
  grade: number | null;
  topic: 'coordinate_2d' | 'function_graph' | 'conic' | 'vector_2d' | 'solid_geometry' | 'coordinate_3d' | 'unknown';
  renderer: Renderer;
  objects: SceneObjectV3[];
  relations: RelationV3[];
  annotations: AnnotationV3[];
  derived_facts: DerivedFactV3[];
  parameters: ParameterV3[];
  view: SceneView;
  interpretation: {
    object_ids: string[];
    relation_ids: string[];
    values: Array<Record<string, unknown>>;
    missing_data: string[];
    assumptions: string[];
  };
  construction_steps: ConstructionStepV3[];
  audit: {
    created_by: string;
    generator_provider?: string | null;
    generator_model?: string | null;
    generator_prompt_version?: string | null;
    migrated_from?: string | null;
    updated_at?: string | null;
  };
}

interface SceneCommandBase {
  command_id: string;
  scene_id: string;
  base_revision: number;
}

export type SceneCommand =
  | (SceneCommandBase & { type: 'move_point'; point_id: string; position: [number, number, number] })
  | (SceneCommandBase & { type: 'add_point'; point: Point2DV3 | Point3DV3 })
  | (SceneCommandBase & { type: 'delete_object'; object_id: string })
  | (SceneCommandBase & { type: 'restore_object'; object: SceneObjectV3 })
  | (SceneCommandBase & { type: 'remove_generated'; object_ids: string[]; relation_ids: string[] })
  | (SceneCommandBase & { type: 'restore_generated'; objects: SceneObjectV3[]; relations: RelationV3[] })
  | (SceneCommandBase & { type: 'connect_points'; object_id: string; start_point_id: string; end_point_id: string; connection: 'segment' | 'line' })
  | (SceneCommandBase & { type: 'project_point'; source_point_id: string; target_id: string; target_kind: 'line' | 'segment' | 'plane'; result_point_id: string })
  | (SceneCommandBase & { type: 'intersect_objects'; object_ids: [string, string]; result_object_id: string })
  | (SceneCommandBase & { type: 'set_parameter'; parameter_id: string; value: number })
  | (SceneCommandBase & { type: 'set_visibility'; object_id: string; visible: boolean });

export interface SceneRevisionV3 {
  scene_id: string;
  revision: number;
  parent_revision?: number | null;
  command_id?: string | null;
  command_type?: SceneCommand['type'] | null;
  changed_object_ids: string[];
  affected_relation_ids: string[];
}

export interface PipelineIssueV3 {
  stage: 'structure' | 'topology' | 'derive' | 'verify' | 'repair' | 'project';
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'error';
  target_id?: string | null;
}

export interface ProjectionBoundsV3 {
  minimum: [number, number, number];
  maximum: [number, number, number];
  center: [number, number, number];
  radius: number;
}

export interface RenderProjectionV3 {
  scene_id: string;
  revision: number;
  renderer: Renderer;
  dimension: '2d' | '3d';
  object_names: Record<string, string>;
  points: Array<{
    object_id: string;
    name: string;
    label?: string | null;
    position: [number, number, number];
    visible: boolean;
  }>;
  linear: Array<{
    object_id: string;
    name: string;
    kind: 'segment' | 'line' | 'vector';
    point_ids: [string, string];
    positions: [[number, number, number], [number, number, number]];
    visible: boolean;
    color?: string | null;
    line_width?: number | null;
    style?: 'solid' | 'dashed' | 'dotted' | null;
    extent?: number | null;
  }>;
  circles: Array<{
    object_id: string;
    name: string;
    center_point_id: string;
    center: [number, number, number];
    radius: number;
    visible: boolean;
  }>;
  functions: Array<{
    object_id: string;
    name: string;
    expression: string;
    domain?: [number | string, number | string] | null;
    visible: boolean;
  }>;
  surfaces: Array<{
    object_id: string;
    name: string;
    kind: 'face' | 'plane';
    point_ids: string[];
    positions: Array<[number, number, number]>;
    color: string;
    opacity: number;
    visible: boolean;
    extent?: number | null;
    show_normal: boolean;
  }>;
  spheres: Array<{
    object_id: string;
    name: string;
    center_point_id: string;
    center: [number, number, number];
    radius: number;
    color: string;
    opacity: number;
    visible: boolean;
  }>;
  annotations: Array<{
    annotation_id: string;
    type: string;
    target_ids: string[];
    label?: string | null;
    color?: string | null;
    provenance: DerivedFactProvenance;
    relation_id?: string | null;
    metadata: Record<string, unknown>;
  }>;
  bounds: ProjectionBoundsV3;
  view: SceneView;
}

export interface RenderPayloadV3 {
  renderer: Renderer;
  geogebra_commands?: string[] | null;
  three_scene?: Record<string, unknown> | null;
}

export interface SceneWorkspaceResponseV3 {
  status: 'verified' | 'partially_verified' | 'needs_confirmation' | 'failed';
  scene: MathSceneV3;
  projection: RenderProjectionV3;
  payload: RenderPayloadV3;
  verification: ConstraintResultV3[];
  issues: PipelineIssueV3[];
  requires_user_confirmation: boolean;
  inverse_command?: SceneCommand | null;
  changed_object_ids: string[];
  affected_relation_ids: string[];
}