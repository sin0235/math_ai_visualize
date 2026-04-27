export type Renderer = 'geogebra_2d' | 'geogebra_3d' | 'threejs_3d';

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
  | Circle2D
  | FunctionGraph
  | Face;

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
  segments: Array<{ points: [string, string]; hidden: boolean; name?: string | null }>;
  faces: Array<{ points: string[]; name?: string | null; color: string; opacity: number }>;
  spheres?: Array<{ center: string; radius: number; name?: string | null; color: string; opacity: number }>;
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
