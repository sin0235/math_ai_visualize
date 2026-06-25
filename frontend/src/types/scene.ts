export type Renderer = 'geogebra_2d' | 'geogebra_3d' | 'threejs_3d';
export type CoordinateAssignment = 'ai' | 'auto_origin' | 'prefer_o_origin';
export type ReasoningLayerMode = 'off' | 'auto' | 'force';
export type RenderStatus = 'verified' | 'partially_verified' | 'needs_confirmation' | 'fallback' | 'failed';
export type RenderSourceKind = 'ai' | 'byok' | 'mock' | 'scene_edit' | 'manual' | 'none';
export type VerificationStatus = 'verified' | 'failed' | 'unsupported' | 'unverifiable' | 'error';
export type ReportStatus = 'passed' | 'partial' | 'failed';
export type RepairStatus = 'none' | 'applied' | 'proposal' | 'rejected';
export type ObjectSource = 'given' | 'ai_inferred' | 'construction' | 'user_created' | 'user_edited';
export type RelationSource = 'given' | 'ai_inferred' | 'construction' | 'user_created';
export type RendererCompatibilityStatus = 'compatible' | 'incompatible' | 'requires_confirmation';

export interface AdvancedRenderSettings {
  coordinate_assignment: CoordinateAssignment;
  reasoning_layer: ReasoningLayerMode;
  show_coordinates?: boolean | null;
  auto_segments_from_faces: boolean;
  verify_scene: boolean;
  graph_intersections: boolean;
  show_axes?: boolean | null;
  show_grid?: boolean | null;
}

export interface MathScene {
  scene_id?: string | null;
  schema_version?: string;
  revision?: number;
  problem_text: string;
  grade: number | null;
  topic: string;
  renderer: Renderer;
  objects: SceneObject[];
  relations: Relation[];
  annotations: Annotation[];
  parameters?: Parameter[];
  view: SceneView;
  interpretation?: SceneInterpretation;
  construction_steps?: ConstructionStep[];
  audit?: SceneAudit;
  cas_issues?: CasIssue[];
}

export interface SceneObjectBase {
  id?: string | null;
  source?: ObjectSource;
  locked?: boolean;
  user_edited?: boolean;
  metadata?: Record<string, unknown>;
}

export interface Parameter {
  name: string;
  label?: string | null;
  min: number;
  max: number;
  default: number;
  step: number;
}

export type SceneObject =
  | Point2D
  | Point3D
  | Segment
  | Line2D
  | Vector2D
  | Vector3D
  | Line3D
  | Circle2D
  | FunctionGraph
  | Face
  | Sphere
  | Plane;

export interface Point2D extends SceneObjectBase {
  type: 'point_2d';
  name: string;
  x: number;
  y: number;
  x_expr?: string | null;
  y_expr?: string | null;
}

export interface Point3D extends SceneObjectBase {
  type: 'point_3d';
  name: string;
  x: number;
  y: number;
  z: number;
  x_expr?: string | null;
  y_expr?: string | null;
  z_expr?: string | null;
}

export interface Segment extends SceneObjectBase {
  type: 'segment';
  name?: string | null;
  points: [string, string];
  hidden: boolean;
  color?: string | null;
  line_width?: number | null;
  style?: 'solid' | 'dashed' | 'dotted' | null;
}

export interface Line2D extends SceneObjectBase {
  type: 'line_2d';
  name?: string | null;
  through: [string, string];
}

export interface Vector2D extends SceneObjectBase {
  type: 'vector_2d';
  name?: string | null;
  from_point: string;
  to_point: string;
}

export interface Vector3D extends SceneObjectBase {
  type: 'vector_3d';
  name?: string | null;
  from_point: string;
  to_point: string;
  color: string;
}

export interface Line3D extends SceneObjectBase {
  type: 'line_3d';
  name?: string | null;
  through: [string, string];
  color: string;
}

export interface Circle2D extends SceneObjectBase {
  type: 'circle_2d';
  name?: string | null;
  center: string;
  through?: string | null;
  radius?: number | null;
  radius_expr?: string | null;
}

export interface FunctionGraph extends SceneObjectBase {
  type: 'function_graph';
  name: string;
  expression: string;
  domain?: [number | string, number | string] | null;
}

export interface Face extends SceneObjectBase {
  type: 'face';
  name?: string | null;
  points: string[];
  color: string;
  opacity: number;
}

export interface Sphere extends SceneObjectBase {
  type: 'sphere';
  name?: string | null;
  center: string;
  radius: number;
  radius_expr?: string | null;
  color: string;
  opacity: number;
}

export interface Plane extends SceneObjectBase {
  type: 'plane';
  name?: string | null;
  points: string[];
  color: string;
  opacity: number;
  show_normal: boolean;
}

export type LineLineStatus = 'intersect' | 'parallel' | 'coincident' | 'skew' | 'degenerate';
export type LinePlaneStatus = 'intersect' | 'parallel' | 'line_in_plane' | 'degenerate';

export type ComputedIntersection =
  | {
      type: 'line_line';
      object_1: string;
      object_2: string;
      status: LineLineStatus;
      point?: { x: number; y: number; z: number } | null;
      parameters?: { t: number; u: number } | null;
      distance?: number | null;
    }
  | {
      type: 'line_plane';
      line: string;
      plane: string;
      status: LinePlaneStatus;
      point?: { x: number; y: number; z: number } | null;
      parameter?: number | null;
    };

export interface ComputedVector {
  name?: string | null;
  from: { x: number; y: number; z: number };
  to: { x: number; y: number; z: number };
  color: string;
  kind: 'normal' | 'vector';
  target?: string | null;
}

export interface ComputedMeasurement {
  type: 'sphere_plane_distance';
  sphere: string;
  plane: string;
  status: 'separate' | 'tangent' | 'intersect' | 'degenerate';
  center_distance?: number | null;
  signed_center_distance?: number | null;
  minimum_distance?: number | null;
  radius: number;
  plane_foot?: { x: number; y: number; z: number } | null;
  nearest_sphere_point?: { x: number; y: number; z: number } | null;
}

export interface ValidationItem {
  code: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
  path?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ValidationReport {
  status: ReportStatus;
  items: ValidationItem[];
}

export interface RelationVerification {
  relation_id: string;
  status: VerificationStatus;
  method?: string | null;
  tolerance?: number | null;
  evidence?: string | null;
  message?: string | null;
  verifier_version: string;
  metadata?: Record<string, unknown>;
}

export interface VerificationReport {
  status: ReportStatus;
  relations: RelationVerification[];
  summary: {
    verified: number;
    failed: number;
    unsupported: number;
    unverifiable: number;
    error: number;
  };
}

export interface RepairReport {
  status: RepairStatus;
  changes: Array<{
    target_id?: string | null;
    target_name?: string | null;
    field: string;
    before?: unknown;
    after?: unknown;
    reason?: string | null;
  }>;
  requires_confirmation: boolean;
  warnings: string[];
}

export interface RendererCompatibilityReport {
  status: RendererCompatibilityStatus;
  renderer?: Renderer | null;
  dimension?: '2d' | '3d' | null;
  messages: string[];
  unsupported_objects: string[];
  unsupported_relations: string[];
}

export interface CandidateAttempt {
  provider?: string | null;
  model?: string | null;
  stage: string;
  success: boolean;
  message?: string | null;
}

export interface RenderSource {
  kind: RenderSourceKind;
  provider?: string | null;
  model?: string | null;
  fallback_used: boolean;
  fallback_reason?: string | null;
  candidate_attempts: CandidateAttempt[];
}

export interface Relation {
  id?: string | null;
  type: string;
  object_1: string;
  object_2?: string | null;
  args?: Record<string, unknown>;
  source?: RelationSource;
  verification?: RelationVerification | null;
  metadata: Record<string, unknown>;
}

export interface Annotation {
  id?: string | null;
  source?: ObjectSource;
  type: string;       // 'length' | 'angle' | 'right_angle' | 'equal_marks' | 'coordinate_label'
  target: string;     // point name or "A-B" edge key
  label?: string | null;
  color?: string | null;
  metadata: Record<string, unknown>;
}

export interface SceneView {
  dimension: '2d' | '3d';
  show_axes: boolean;
  show_grid: boolean;
  show_coordinates: boolean;
}

export interface SceneInterpretation {
  objects: Array<Record<string, unknown>>;
  relations: Array<Record<string, unknown>>;
  values: Array<Record<string, unknown>>;
  missing_data: string[];
  assumptions: string[];
}

export interface ConstructionStep {
  id?: string | null;
  description: string;
  object_ids: string[];
  relation_ids: string[];
}

export interface SceneAudit {
  created_by: RenderSourceKind;
  generator_provider?: string | null;
  generator_model?: string | null;
  generator_prompt_version?: string | null;
  updated_at?: string | null;
}

export interface ThreeScene {
  points: Record<string, { x: number; y: number; z: number }>;
  segments: Array<{ points: [string, string]; hidden: boolean; name?: string | null; color?: string | null; line_width?: number | null; style?: 'solid' | 'dashed' | 'dotted' | null }>;
  faces: Array<{ points: string[]; name?: string | null; color: string; opacity: number }>;
  spheres?: Array<{ center: string; radius: number; name?: string | null; color: string; opacity: number }>;
  lines?: Array<{ through: [string, string]; name?: string | null; color: string }>;
  vectors?: Array<{ from_point: string; to_point: string; name?: string | null; color: string }>;
  planes?: Array<{ points: string[]; name?: string | null; color: string; opacity: number; show_normal: boolean }>;
  computed?: {
    intersections?: ComputedIntersection[];
    vectors?: ComputedVector[];
    measurements?: ComputedMeasurement[];
    warnings?: string[];
  };
  annotations: Annotation[];
  relations: Relation[];
  view: SceneView;
}

export interface RenderPayload {
  renderer: Renderer;
  geogebra_commands: string[];
  three_scene?: ThreeScene | null;
}

export interface CasIssue {
  relation_type: string;
  description: string;
  severity: string;
  auto_fixed: boolean;
  metadata?: Record<string, unknown> | null;
}

export interface ProblemClassification {
  domain: string;
  topic: string;
  task_type?: string | null;
  sub_type?: string | null;
  confidence: number;
  source: 'rules' | 'existing_metadata' | 'hybrid_rules' | string;
  signals: string[];
  supported_by_current_solver?: boolean | null;
}

export interface AdvisoryFactor {
  code: string;
  severity: 'info' | 'warning' | 'risk' | 'critical' | string;
  message: string;
  weight: number;
}

export interface QualityRiskAdvisory {
  classification: ProblemClassification;
  quality_score: number;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | string;
  factors: AdvisoryFactor[];
  recommendations: string[];
}

export type RenderFallbackSource = 'none' | 'mock' | 'provider_fallback';
export type RenderAiSource = 'admin' | 'byok' | 'none';

export interface RenderResponse {
  status: RenderStatus;
  source: RenderSource;
  scene: MathScene;
  payload: RenderPayload;
  warnings: string[];
  validation_report: ValidationReport;
  verification_report: VerificationReport;
  repair_report: RepairReport;
  renderer_compatibility: RendererCompatibilityReport;
  requires_user_confirmation: boolean;
  user_confirmed?: boolean;
  cas_issues?: CasIssue[];
  advisory?: QualityRiskAdvisory | null;
  degraded?: boolean;
  fallback_source?: RenderFallbackSource;
  ai_source?: RenderAiSource;
}
