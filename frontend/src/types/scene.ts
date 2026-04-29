export type Renderer = 'geogebra_2d' | 'geogebra_3d' | 'threejs_3d';
export type CoordinateAssignment = 'ai' | 'auto_origin' | 'prefer_o_origin';
export type ReasoningLayerMode = 'off' | 'auto' | 'force';

export interface AdvancedRenderSettings {
  coordinate_assignment: CoordinateAssignment;
  reasoning_layer: ReasoningLayerMode;
  show_coordinates?: boolean | null;
  auto_segments_from_faces: boolean;
  graph_intersections: boolean;
  show_axes?: boolean | null;
  show_grid?: boolean | null;
}

export interface MathScene {
  problem_text: string;
  grade: number | null;
  topic: string;
  renderer: Renderer;
  objects: SceneObject[];
  relations: Relation[];
  annotations: Annotation[];
  view: SceneView;
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

export interface Point2D {
  type: 'point_2d';
  name: string;
  x: number;
  y: number;
}

export interface Point3D {
  type: 'point_3d';
  name: string;
  x: number;
  y: number;
  z: number;
}

export interface Segment {
  type: 'segment';
  name?: string | null;
  points: [string, string];
  hidden: boolean;
  color?: string | null;
  line_width?: number | null;
  style?: 'solid' | 'dashed' | 'dotted' | null;
}

export interface Line2D {
  type: 'line_2d';
  name?: string | null;
  through: [string, string];
}

export interface Vector2D {
  type: 'vector_2d';
  name?: string | null;
  from_point: string;
  to_point: string;
}

export interface Vector3D {
  type: 'vector_3d';
  name?: string | null;
  from_point: string;
  to_point: string;
  color: string;
}

export interface Line3D {
  type: 'line_3d';
  name?: string | null;
  through: [string, string];
  color: string;
}

export interface Circle2D {
  type: 'circle_2d';
  name?: string | null;
  center: string;
  through?: string | null;
  radius?: number | null;
}

export interface FunctionGraph {
  type: 'function_graph';
  name: string;
  expression: string;
}

export interface Face {
  type: 'face';
  name?: string | null;
  points: string[];
  color: string;
  opacity: number;
}

export interface Sphere {
  type: 'sphere';
  name?: string | null;
  center: string;
  radius: number;
  color: string;
  opacity: number;
}

export interface Plane {
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

export interface Relation {
  type: string;
  object_1: string;
  object_2?: string | null;
  metadata: Record<string, unknown>;
}

export interface Annotation {
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

export interface RenderResponse {
  scene: MathScene;
  payload: RenderPayload;
  warnings: string[];
}
