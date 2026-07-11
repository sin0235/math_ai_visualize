import type { MathScene } from '../types/scene';
import { requestJson } from './core';
import { uploadOcrImage } from './render';

export interface CriticalPoint {
  x: string;
  x_exact: string;
  y: string | null;
  kind: string;
  kind_label: string;
}

export interface VariationRow {
  x: string;
  y: string | null;
  kind: string;
  arrow_to_next: string | null;
}

export interface VariationLimit {
  value: string | null;
  status: 'finite' | 'infinite' | 'dne' | 'unknown' | string;
}

export interface VariationNodeV2 {
  kind: 'boundary' | 'critical' | 'max' | 'min' | 'asymptote' | 'hole' | string;
  x: string;
  x_exact?: string | null;
  y?: string | null;
  y_exact?: string | null;
  label?: string | null;
  left_limit?: VariationLimit | null;
  right_limit?: VariationLimit | null;
}

export interface VariationSegmentV2 {
  left: string;
  right: string;
  direction: 'increasing' | 'decreasing' | 'constant' | 'unknown' | string;
  verification: 'exact' | 'sampled' | 'unknown' | string;
  derivative_sign: '+' | '-' | '0' | 'unknown' | string;
}

export interface VariationTableV2 {
  status: 'complete' | 'partial' | 'unknown' | string;
  warnings: string[];
  nodes: VariationNodeV2[];
  segments: VariationSegmentV2[];
}

export interface AnalysisSegmentV2 {
  left: string;
  right: string;
  left_exact?: string | null;
  right_exact?: string | null;
  sign?: string | null;
  direction?: string | null;
  kind?: string | null;
  verification: string;
  error_bound?: string | null;
  parameter?: string | null;
  parameter_domain?: string | null;
}

export interface AnalysisChartV2 {
  status: 'complete' | 'partial' | 'unknown' | string;
  method: string;
  segments: AnalysisSegmentV2[];
  warnings: string[];
  periodic?: boolean;
  period?: string | null;
  parameter?: string | null;
  parameter_domain?: string | null;
  base_interval?: Record<string, string> | null;
}

export interface AnalyzeAsymptotesV2 {
  vertical: Array<Record<string, unknown>>;
  horizontal: Array<Record<string, unknown>>;
  oblique: Array<Record<string, unknown>>;
  periodic_vertical_families: Array<Record<string, unknown>>;
}

export interface RootEvidenceV2 {
  x: string;
  x_exact: string | null;
  x_latex: string | null;
  x_approx: string;
  verification: 'symbolic_exact' | 'numeric_verified' | string;
  residual: number;
  error_bound: number | null;
}

export interface RootAnalysisV2 {
  status: 'complete' | 'partial' | 'unknown' | string;
  method: string;
  roots: RootEvidenceV2[];
  families: Array<{ set_exact: string; set_latex: string; parameter_domain: string | null }>;
  total_known: number | null;
  truncated: boolean;
  max_points: number;
  search_window: [number, number] | null;
  warnings: string[];
}

export interface ExtremeResultV2 {
  status: string;
  value: string;
  value_exact: string;
  value_latex: string;
  attained: boolean;
  attainment_set_exact: string | null;
  attainment_set_latex: string | null;
  points: Array<{ x: string; x_exact: string; x_latex: string; y: string; y_exact: string; y_latex: string }>;
}

export interface AreaAnalysisV2 {
  status: 'complete' | 'partial' | 'unavailable' | string;
  method: string;
  components: Array<{
    left: string;
    left_exact: string;
    left_latex: string;
    right: string;
    right_exact: string;
    right_latex: string;
    area: string;
    area_exact: string;
    area_latex: string;
    area_approx: string | null;
    verification: string;
  }>;
  total_exact: string | null;
  total_latex: string | null;
  total_approx: string | null;
  warnings: string[];
}

export interface AnalyzeParameterRange {
  min: number;
  max: number;
  step: number;
}

export interface AnalyzeParameters {
  detected: string[];
  active: Record<string, number>;
  active_exact?: Record<string, string>;
  provenance?: { mode: string; source: string; exact: boolean };
  ranges: Record<string, AnalyzeParameterRange>;
}

export interface FunctionOcrProvenance {
  source: 'ocr' | 'ocr_confirmed';
  provider: string;
  model: string;
  extraction_version: string;
}

export interface FunctionOcrAmbiguousToken {
  token: string;
  alternatives: string[];
  reason: string;
  start?: number | null;
  end?: number | null;
}

export interface FunctionOcrExtraction {
  expression: string;
  variable: 'x';
  parameters: Array<'m'>;
  confidence: number;
  warnings: string[];
  ambiguous_tokens: FunctionOcrAmbiguousToken[];
  needs_confirmation: boolean;
  ocr_text: string;
  provenance: FunctionOcrProvenance;
}

export interface AnalyzeOptions {
  parameters?: { m?: string | number };
  parameter_mode?: 'symbolic' | 'substitute';
  provenance?: FunctionOcrProvenance;
  interval?: { a: number; b: number; open_a?: boolean; open_b?: boolean };
  line?: { k?: number; b?: number; mode?: string; x0?: number };
  parameter_conditions?: { targets: string[]; extrema_count?: number };
  transform?: { type: string; value: number };
}

export interface GraphBoundV2 {
  exact: string;
  latex: string;
  approx: number | null;
}

export interface GraphEndpointV2 extends GraphBoundV2 {
  open: boolean;
  attained: boolean;
  y: number | null;
}

export interface GraphSegmentV2 {
  component_id: string;
  expression_exact: string;
  expression_latex: string;
  start: GraphBoundV2;
  end: GraphBoundV2;
  left_open: boolean;
  right_open: boolean;
  left_endpoint: GraphEndpointV2;
  right_endpoint: GraphEndpointV2;
  points: Array<{ x: number; y: number }>;
  sample_count: number;
  verification: string;
}

export interface GraphAnalysisV2 {
  status: 'complete' | 'partial' | 'unknown' | string;
  method: string;
  window: { x_min: number; x_max: number };
  max_points: number;
  point_count: number;
  segments: GraphSegmentV2[];
  singularities: Array<{ exact: string; latex: string; approx: number | null }>;
  features?: Array<{ exact: string; latex: string; approx: number | null }>;
  warnings: string[];
}

export interface AnalyzeResponse {
  expression: string;
  expression_latex: string | null;
  evaluated_expression: string | null;
  evaluated_expression_latex: string | null;
  parameters: AnalyzeParameters | null;
  analysis_mode: 'symbolic' | 'numeric_substituted' | 'safe_symbolic' | 'requires_parameter_confirmation' | null;
  parameter_mode?: 'symbolic' | 'substitute' | null;
  requires_parameter_confirmation?: boolean;
  requires_substitution_for_graph?: boolean;
  parameter_analysis_v2?: {
    status: string;
    parameter: string;
    boundaries: Array<{ exact: string; latex: string; approx: number }>;
    cases: Array<Record<string, unknown>>;
    warnings: string[];
  } | null;
  derivative: string | null;
  derivative_latex: string | null;
  second_derivative: string | null;
  second_derivative_latex: string | null;
  critical_points: CriticalPoint[];
  inflection_points: Array<{ x: string; x_exact: string; y: string }>;
  intervals_increasing: string[];
  intervals_decreasing: string[];
  concave_up_intervals: string[];
  concave_down_intervals: string[];
  horizontal_asymptotes: Array<{ direction: string; value: string }>;
  vertical_asymptotes: Array<{ x: string; lim_right: string; lim_left: string }>;
  oblique_asymptote: string | null;
  x_intercepts: string[];
  x_intercepts_v2?: RootAnalysisV2 | null;
  y_intercept: string | null;
  variation_table: VariationRow[];
  variation_table_v2?: VariationTableV2 | null;
  domain_partition_v2?: Record<string, unknown> | null;
  periodicity?: Record<string, unknown> | null;
  monotonicity_v2?: AnalysisChartV2 | null;
  concavity_v2?: AnalysisChartV2 | null;
  critical_points_v2?: Array<Record<string, unknown>>;
  inflection_points_v2?: Array<Record<string, unknown>>;
  asymptotes_v2?: AnalyzeAsymptotesV2 | null;
  domain: string | null;
  domain_latex: string | null;
  range_val: string | null;
  range_latex: string | null;
  parity: 'even' | 'odd' | 'neither' | null;
  geogebra_commands: string[];
  graph_scene: MathScene | null;
  graph_points: Array<{ x: number; y: number }>;
  graph_analysis_v2?: GraphAnalysisV2 | null;
  ocr_text: string | null;
  ocr_expression: string | null;
  provenance?: FunctionOcrProvenance | null;
  interval_analysis?: {
    a: string;
    b: string;
    open_a?: boolean;
    open_b?: boolean;
    fa: string;
    fb: string;
    status?: string;
    method?: string;
    warnings?: string[];
    domain_intersection_exact?: string;
    domain_components?: Array<{ start: string; start_exact: string; end: string; end_exact: string; left_open: boolean; right_open: boolean }>;
    range_exact?: string;
    range_latex?: string;
    boundary_evidence?: Array<{
      component: number;
      x: string;
      x_exact: string;
      side: string;
      kind: string;
      attained: boolean;
      value: { status: string; value: string | null; value_exact: string | null; value_latex: string | null; approx: string | null };
    }>;
    extrema_inside: Array<{ x: string; x_exact: string; y: string; label: string }>;
    supremum?: ExtremeResultV2;
    infimum?: ExtremeResultV2;
    max_point: { x: string; y: string; label: string };
    min_point: { x: string; y: string; label: string };
    conclusion: string;
  } | null;
  line_analysis?: {
    mode?: string;
    status?: string;
    kind?: string;
    equation: string;
    equation_exact?: string | null;
    equation_latex?: string | null;
    intersection_count?: number | null;
    intersection_count_status?: string;
    intersections?: Array<{ x: string; y: string; x_exact: string; x_latex?: string | null; y_exact?: string; y_latex?: string; residual?: number; error_bound?: number | null; verification?: string }>;
    roots_v2?: RootAnalysisV2;
    relative_intervals?: { above: string[]; below: string[] };
    area_between_curves?: string | null;
    area_v2?: AreaAnalysisV2;
    conclusion?: string;
    warnings?: string[];
  } | null;
  parameter_conditions?: Array<{ label: string; condition_latex?: string; solution: string; solution_latex?: string; warnings?: string[] }>;
  transform_preview?: { type: string; value: string; label: string; expression: string; expression_latex: string; pedagogical_steps?: string[] } | null;
  capabilities?: Record<string, unknown> | null;
  complexity_score?: number | null;
  stage_statuses?: Record<string, { status: string; error_code?: string }> | null;
  warnings: string[];
  error?: string | null;
  error_code?: string | null;
}

export async function analyzeFunction(expression: string, options?: AnalyzeOptions | { m?: number }): Promise<AnalyzeResponse> {
  const hasAnalyzeOptions = !!options && ('parameters' in options || 'parameter_mode' in options || 'provenance' in options || 'interval' in options || 'line' in options || 'parameter_conditions' in options || 'transform' in options);
  const payloadOptions = hasAnalyzeOptions ? options as AnalyzeOptions : { parameters: options as { m?: number } | undefined };
  return requestJson('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ expression, ...payloadOptions }),
  }, 'Không thể phân tích hàm số.');
}

export async function sampleFunctionGraph(
  expression: string,
  window: { x_min: number; x_max: number },
  options?: { parameters?: Record<string, string | number>; max_points?: number },
): Promise<{ graph_analysis_v2: GraphAnalysisV2 }> {
  return requestJson('/api/analyze/graph-samples', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ expression, window, ...options }),
  }, 'Không thể cập nhật mẫu đồ thị.');
}

export async function extractFunctionImage(imageDataUrl: string): Promise<FunctionOcrExtraction> {
  return extractFunctionImageByPayload({ image_data_url: imageDataUrl });
}

export async function extractFunctionImageFile(file: File): Promise<FunctionOcrExtraction> {
  const uploaded = await uploadOcrImage(file);
  return extractFunctionImageByPayload({ upload_id: uploaded.file_id });
}

function extractFunctionImageByPayload(payload: { image_data_url: string } | { upload_id: string }): Promise<FunctionOcrExtraction> {
  return requestJson('/api/analyze/ocr/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể đọc hàm số từ ảnh.');
}

export async function analyzeFunctionImage(imageDataUrl: string): Promise<AnalyzeResponse> {
  return analyzeFunctionImageByPayload({ image_data_url: imageDataUrl });
}

export async function analyzeFunctionImageFile(file: File): Promise<AnalyzeResponse> {
  const uploaded = await uploadOcrImage(file);
  return analyzeFunctionImageByUploadId(uploaded.file_id);
}

export async function analyzeFunctionImageByUploadId(uploadId: string): Promise<AnalyzeResponse> {
  return analyzeFunctionImageByPayload({ upload_id: uploadId });
}

function analyzeFunctionImageByPayload(payload: { image_data_url: string } | { upload_id: string }): Promise<AnalyzeResponse> {
  return requestJson('/api/analyze/ocr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể phân tích hàm số từ ảnh.');
}
