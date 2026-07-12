import type { MathScene } from '../types/scene';
import { apiUrl, fetchWithRetry, parseApiError, requestJson } from './core';
import { uploadOcrImage } from './render';

export interface ExactApproxValue {
  exact: string;
  latex: string;
  approx: number | null;
  precision: number | null;
  method: string;
}

export interface CriticalPoint {
  x: string;
  x_exact: string;
  x_value?: ExactApproxValue | null;
  y: string | null;
  y_exact?: string | null;
  y_value?: ExactApproxValue | null;
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
  open?: boolean | null;
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
  value?: ExactApproxValue;
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
  value_v2?: ExactApproxValue;
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

export interface ParameterAnalysisCase {
  condition_exact: string;
  condition_latex: string;
  sample_exact?: string;
  status: 'complete' | 'unknown' | string;
  verification: string;
  degree: number | null;
  domain_exact: string | null;
  stationary_root_count: number | null;
  extrema_count: number | null;
  root_count: number | null;
  vertical_asymptote_count: number | null;
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

export type AnalyzeLineMode =
  | 'intersect'
  | 'tangent_at'
  | 'tangent_at_point'
  | 'normal_at'
  | 'tangent_parallel'
  | 'tangent_perpendicular'
  | 'tangent_through_point';

export type AnalyzeTransformType =
  | 'vertical_shift'
  | 'horizontal_shift'
  | 'vertical_scale'
  | 'horizontal_scale'
  | 'reflect_x'
  | 'reflect_y'
  | 'absolute_all'
  | 'absolute_x';

export type ParameterConditionTarget = 'increasing_r' | 'decreasing_r' | 'extrema_count';

export interface AnalyzeOptions {
  parameters?: { m?: string | number };
  parameter_mode?: 'symbolic' | 'substitute';
  provenance?: FunctionOcrProvenance;
  curriculum_profile?: CurriculumProfile;
  interval?: { a: number; b: number; open_a?: boolean; open_b?: boolean };
  line?: { k?: number; b?: number; mode?: AnalyzeLineMode; x0?: number; y0?: number };
  parameter_conditions?: { targets: ParameterConditionTarget[]; extrema_count?: 0 | 1 | 2 };
  transform?: { type: AnalyzeTransformType; value?: number };
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
  left_window_clipped: boolean;
  right_window_clipped: boolean;
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

export interface VerificationCheck {
  name: string;
  status: 'pass' | 'warn' | 'fail' | 'unknown';
  method: 'symbolic' | 'numeric' | 'fallback' | 'unknown';
  detail?: string | null;
  error_bound?: number | null;
}

export interface AnalyzerCapabilityExample {
  category: string;
  label: string;
  expression: string;
  latex: string;
}

export interface AnalyzerCapabilityRegistry {
  version: string;
  parser: {
    functions: string[];
    constants: string[];
    variables: string[];
    operators: string[];
    aliases: Record<string, string>;
    limits: Record<string, number>;
  };
  derivative: { supported: boolean; limitations: string[] };
  piecewise_conditions: Record<string, unknown>;
  parameters: { supported: string[]; modes: string[]; ranges: Record<string, AnalyzeParameterRange> };
  tools: string[];
  renderers: string[];
  examples: AnalyzerCapabilityExample[];
}

export interface ExpressionCapabilities {
  registry_version: string;
  expression: { piecewise: boolean; parameters: string[]; parameter_mode: string | null };
  exactness: Record<string, string>;
  completeness: { roots: string; graph: string; truncated: boolean };
  numeric_fallback: { available: boolean; used: boolean };
  renderer: { geogebra: boolean; svg: boolean };
  tools: Record<string, boolean>;
  limitations: string[];
}

export interface VerificationReport {
  status: 'verified' | 'partially_verified' | 'unverified' | 'failed';
  checks: VerificationCheck[];
  truncated: boolean;
  possibly_incomplete: boolean;
}

export interface AnalysisStep {
  key: string;
  order: number;
  title: string;
  status: 'complete' | 'partial' | 'unknown' | 'skipped';
  formula_latex: string | null;
  evidence: string[];
  warnings: string[];
}

export interface CurriculumProfile {
  grade: 10 | 11 | 12;
  chapter: string;
  explanation_level: 'concise' | 'standard' | 'detailed';
}

export interface CurriculumPresentation {
  profile: CurriculumProfile;
  terminology: Record<string, string>;
  step_order: string[];
  common_mistakes: string[];
  predicted_questions: string[];
}

export interface AnalyzerHistoryItem {
  id: string;
  original_expression: string;
  canonical_expression: string;
  parameters: Record<string, unknown>;
  tags: string[];
  pinned: boolean;
  grade: number | null;
  chapter: string | null;
  explanation_level: string;
  engine_version: string;
  schema_version: string;
  parent_history_id?: string | null;
  created_at: string;
  updated_at: string;
  last_opened_at?: string | null;
}

export interface AnalyzerHistoryDetail extends AnalyzerHistoryItem {
  result: AnalyzerSessionResponse;
  window: Record<string, unknown>;
  tools: Record<string, unknown>;
  version_diff?: {
    engine_changed: boolean;
    schema_changed: boolean;
    verification_changed: boolean;
    warning_count_before: number;
    warning_count_after: number;
  } | null;
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
    cases: ParameterAnalysisCase[];
    warnings: string[];
  } | null;
  derivative: string | null;
  derivative_latex: string | null;
  second_derivative: string | null;
  second_derivative_latex: string | null;
  critical_points: CriticalPoint[];
  inflection_points: Array<{
    x: string;
    x_exact: string;
    x_value?: ExactApproxValue | null;
    y: string;
    y_exact?: string | null;
    y_value?: ExactApproxValue | null;
  }>;
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
    domain_components?: Array<{ start: string; start_exact: string; start_approx?: number | null; end: string; end_exact: string; end_approx?: number | null; left_open: boolean; right_open: boolean }>;
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
    graph_expression?: string | null;
    graph_expressions?: string[];
    tangents?: Array<{
      x0: string;
      x0_exact: string;
      y0: string;
      y0_exact: string;
      equation: string;
      equation_exact: string;
      equation_latex: string;
      graph_expression: string;
      verification: string;
    }>;
    tangent_count?: number | null;
    tangent_count_known?: number;
    condition_exact?: string;
    x0?: string;
    x0_exact?: string;
    y0?: string;
    y0_exact?: string;
    intersection_count?: number | null;
    intersection_count_status?: string;
    intersections?: Array<{ x: string; y: string; x_exact: string; x_latex?: string | null; y_exact?: string; y_latex?: string; residual?: number; error_bound?: number | null; verification?: string; multiplicity?: number | null; contact_kind?: 'crossing' | 'tangent' | 'unknown' | string }>;
    roots_v2?: RootAnalysisV2;
    relative_intervals?: { above: string[]; below: string[] };
    area_between_curves?: string | null;
    area_v2?: AreaAnalysisV2;
    conclusion?: string;
    warnings?: string[];
  } | null;
  parameter_conditions?: Array<{ label: string; condition_latex?: string; solution: string; solution_latex?: string; warnings?: string[] }>;
  transform_preview?: {
    type: AnalyzeTransformType;
    value: string;
    label: string;
    expression: string;
    expression_latex: string;
    convention: string;
    expression_template: string;
    requires_value: boolean;
    transformed_domain?: string | null;
    transformed_range?: string | null;
    invariants: string[];
    anchors: Array<{ source_x: number; source_y: number; target_x: number; target_y: number }>;
    pedagogical_steps?: string[];
  } | null;
  capabilities?: Record<string, unknown> | null;
  capabilities_v2?: ExpressionCapabilities | null;
  complexity_score?: number | null;
  stage_statuses?: Record<string, { status: string; error_code?: string }> | null;
  verification?: VerificationReport | null;
  analysis_steps?: AnalysisStep[];
  curriculum_presentation?: CurriculumPresentation | null;
  warnings: string[];
  error?: string | null;
  error_code?: string | null;
}

let analyzerCapabilitiesRequest: Promise<AnalyzerCapabilityRegistry> | null = null;

export function getAnalyzerCapabilities(): Promise<AnalyzerCapabilityRegistry> {
  if (analyzerCapabilitiesRequest) return analyzerCapabilitiesRequest;
  const request = requestJson<AnalyzerCapabilityRegistry>('/api/analyze/capabilities', {
    method: 'GET',
    credentials: 'include',
  }, 'Không thể tải khả năng của bộ phân tích.').catch((error) => {
    analyzerCapabilitiesRequest = null;
    throw error;
  });
  analyzerCapabilitiesRequest = request;
  return request;
}

export interface AnalyzerSessionResponse extends AnalyzeResponse {
  analysis_id: string;
  engine_version: string;
  expires_at: string;
}

export type AnalyzerToolName = 'interval-extrema' | 'line' | 'tangent' | 'transform' | 'parameter';

export interface AnalyzerToolResponse {
  analysis_id: string;
  engine_version: string;
  tool: AnalyzerToolName;
  interval_analysis?: AnalyzeResponse['interval_analysis'];
  line_analysis?: AnalyzeResponse['line_analysis'];
  transform_preview?: AnalyzeResponse['transform_preview'];
  parameter_conditions?: AnalyzeResponse['parameter_conditions'];
}

export async function createAnalyzerSession(
  expression: string,
  options?: Pick<AnalyzeOptions, 'parameters' | 'parameter_mode' | 'provenance' | 'curriculum_profile'>,
  signal?: AbortSignal,
): Promise<AnalyzerSessionResponse> {
  return requestJson('/api/analyzer/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
    body: JSON.stringify({ expression, ...options }),
  }, 'Không thể tạo phiên phân tích.');
}

export function runAnalyzerIntervalTool(analysisId: string, interval: NonNullable<AnalyzeOptions['interval']>, signal?: AbortSignal): Promise<AnalyzerToolResponse> {
  return requestAnalyzerTool('interval-extrema', { analysis_id: analysisId, interval }, signal);
}

export function runAnalyzerLineTool(analysisId: string, line: NonNullable<AnalyzeOptions['line']>, signal?: AbortSignal): Promise<AnalyzerToolResponse> {
  return requestAnalyzerTool('line', { analysis_id: analysisId, line }, signal);
}

export function runAnalyzerTangentTool(analysisId: string, x0: number, signal?: AbortSignal): Promise<AnalyzerToolResponse> {
  return requestAnalyzerTool('tangent', { analysis_id: analysisId, x0 }, signal);
}

export function runAnalyzerTransformTool(analysisId: string, transform: NonNullable<AnalyzeOptions['transform']>, signal?: AbortSignal): Promise<AnalyzerToolResponse> {
  return requestAnalyzerTool('transform', { analysis_id: analysisId, transform }, signal);
}

export function runAnalyzerParameterTool(
  analysisId: string,
  request: NonNullable<AnalyzeOptions['parameter_conditions']>,
  signal?: AbortSignal,
): Promise<AnalyzerToolResponse> {
  return requestAnalyzerTool('parameter', { analysis_id: analysisId, ...request }, signal);
}

function requestAnalyzerTool(tool: AnalyzerToolName, payload: object, signal?: AbortSignal): Promise<AnalyzerToolResponse> {
  return requestJson(`/api/analyzer/tools/${tool}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
    body: JSON.stringify(payload),
  }, 'Không thể chạy công cụ phân tích.');
}

export async function analyzeFunction(expression: string, options?: AnalyzeOptions | { m?: number }, signal?: AbortSignal): Promise<AnalyzeResponse> {
  const hasAnalyzeOptions = !!options && ('parameters' in options || 'parameter_mode' in options || 'provenance' in options || 'interval' in options || 'line' in options || 'parameter_conditions' in options || 'transform' in options);
  const payloadOptions = hasAnalyzeOptions ? options as AnalyzeOptions : { parameters: options as { m?: number } | undefined };
  return requestJson('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
    body: JSON.stringify({ expression, ...payloadOptions }),
  }, 'Không thể phân tích hàm số.');
}

export async function sampleFunctionGraph(
  expression: string,
  window: { x_min: number; x_max: number },
  options?: { parameters?: Record<string, string | number>; max_points?: number },
  signal?: AbortSignal,
): Promise<{ graph_analysis_v2: GraphAnalysisV2 }> {
  return requestJson('/api/analyze/graph-samples', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
    body: JSON.stringify({ expression, window, ...options }),
  }, 'Không thể cập nhật mẫu đồ thị.');
}

export function listAnalyzerHistory(filters: { q?: string; tag?: string; pinned?: boolean } = {}): Promise<AnalyzerHistoryItem[]> {
  const search = new URLSearchParams();
  if (filters.q?.trim()) search.set('q', filters.q.trim());
  if (filters.tag?.trim()) search.set('tag', filters.tag.trim());
  if (filters.pinned !== undefined) search.set('pinned', String(filters.pinned));
  const query = search.toString();
  return requestJson(`/api/analyzer/history${query ? `?${query}` : ''}`, { method: 'GET', credentials: 'include' }, 'Không tải được lịch sử analyzer.');
}

export function saveAnalyzerHistory(
  analysisId: string,
  profile: CurriculumProfile,
  options: { tags?: string[]; pinned?: boolean; window?: { x_min: number; x_max: number }; tools?: AnalyzeOptions } = {},
): Promise<AnalyzerHistoryItem> {
  return requestJson('/api/analyzer/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ analysis_id: analysisId, curriculum_profile: profile, ...options }),
  }, 'Không lưu được lịch sử analyzer.');
}

export function openAnalyzerHistory(id: string): Promise<AnalyzerHistoryDetail> {
  return requestJson(`/api/analyzer/history/${encodeURIComponent(id)}`, { method: 'GET', credentials: 'include' }, 'Không mở được lịch sử analyzer.');
}

export function reanalyzeAnalyzerHistory(id: string, profile: CurriculumProfile): Promise<AnalyzerHistoryDetail> {
  return requestJson(`/api/analyzer/history/${encodeURIComponent(id)}/reanalyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ curriculum_profile: profile }),
  }, 'Không phân tích lại được lịch sử analyzer.');
}

export async function exportAnalyzer(
  source: { analysis_id: string } | { history_id: string },
  format: 'markdown' | 'json' | 'latex' | 'pdf',
  template: 'full' | 'teacher_report' | 'student_worksheet',
  profile: CurriculumProfile,
): Promise<void> {
  const response = await fetchWithRetry(apiUrl('/api/analyzer/export'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ ...source, format, template, curriculum_profile: profile }),
  });
  if (!response.ok) throw await parseApiError(response, 'Không xuất được kết quả analyzer.');
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] || `function-analysis.${format === 'markdown' ? 'md' : format === 'latex' ? 'tex' : format}`;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export type AnalyzerHandoffTarget = 'algebra_solver' | 'simulation' | 'geogebra_lab' | 'render' | 'practice';
export type AnalyzerLinkScope = 'open' | 'embed' | 'api';

export interface AlgebraHandoffPayload {
  version: 'algebra-solver-v1';
  input: string;
  input_format: 'plain';
  topic: 'equation';
  domain: 'R';
}

export interface SimulationHandoffPayload {
  version: 'function-simulation-v1';
  simulation_id: 'g12.calc.derivative-survey';
  expression: string;
  x_min: number;
  x_max: number;
  verification_status: string;
}

export interface GeoGebraHandoffPayload {
  version: 'geogebra-commands-v1';
  mode: 'graphing';
  commands: string[];
}

export interface RenderHandoffPayload {
  version: 'render-problem-v1';
  problem_text: string;
  preferred_renderer: 'geogebra';
}

export interface PracticeHandoffPayload {
  version: 'practice-prompt-v1';
  problem_text: string;
  source_verification: string;
}

export type AnalyzerHandoffPayload = AlgebraHandoffPayload | SimulationHandoffPayload | GeoGebraHandoffPayload | RenderHandoffPayload | PracticeHandoffPayload;

export interface AnalyzerLinkCreated {
  short_id: string;
  kind: 'handoff' | 'share';
  target: AnalyzerHandoffTarget;
  url: string;
  expires_at: string;
  visibility: 'user' | 'public';
  scopes: AnalyzerLinkScope[];
}

export interface AnalyzerLinkConsumed {
  short_id: string;
  kind: 'handoff' | 'share';
  target: AnalyzerHandoffTarget;
  payload_version: string;
  payload: AnalyzerHandoffPayload;
  expires_at: string;
}

export function createAnalyzerHandoff(analysisId: string, target: AnalyzerHandoffTarget): Promise<AnalyzerLinkCreated> {
  return requestJson('/api/analyzer/handoffs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ analysis_id: analysisId, target }),
  }, 'Không tạo được handoff analyzer.');
}

export function createAnalyzerShare(
  analysisId: string,
  target: AnalyzerHandoffTarget,
  options: { visibility: 'user' | 'public'; expires_in_minutes: number; scopes?: AnalyzerLinkScope[]; allowed_origins?: string[]; max_uses?: number },
): Promise<AnalyzerLinkCreated> {
  return requestJson('/api/analyzer/shares', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ analysis_id: analysisId, target, ...options }),
  }, 'Không tạo được link chia sẻ analyzer.');
}

export function consumeAnalyzerLink(
  shortId: string,
  target: AnalyzerHandoffTarget,
  scope: AnalyzerLinkScope = 'open',
): Promise<AnalyzerLinkConsumed> {
  return requestJson(`/api/analyzer/links/${encodeURIComponent(shortId)}/consume`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
    body: JSON.stringify({ target, scope }),
  }, 'Link analyzer không tồn tại hoặc đã hết hiệu lực.');
}

export function revokeAnalyzerLink(shortId: string): Promise<void> {
  return requestJson(`/api/analyzer/links/${encodeURIComponent(shortId)}`, {
    method: 'DELETE', credentials: 'include',
  }, 'Không thu hồi được link analyzer.');
}

export async function consumeAnalyzerLinkFromLocation<T extends AnalyzerHandoffPayload>(
  target: AnalyzerHandoffTarget,
): Promise<T | null> {
  const search = new URLSearchParams(window.location.search);
  const shortId = search.get('handoff') || search.get('share');
  if (!shortId) return null;
  const consumed = await consumeAnalyzerLink(shortId, target);
  search.delete('handoff');
  search.delete('share');
  const query = search.toString();
  window.history.replaceState({}, document.title, `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
  return consumed.payload as T;
}

export async function extractFunctionImage(imageDataUrl: string): Promise<FunctionOcrExtraction> {
  return extractFunctionImageByPayload({ image_data_url: imageDataUrl });
}

export async function extractFunctionImageFile(file: File, signal?: AbortSignal): Promise<FunctionOcrExtraction> {
  const uploaded = await uploadOcrImage(file, signal);
  return extractFunctionImageByPayload({ upload_id: uploaded.file_id }, signal);
}

function extractFunctionImageByPayload(payload: { image_data_url: string } | { upload_id: string }, signal?: AbortSignal): Promise<FunctionOcrExtraction> {
  return requestJson('/api/analyze/ocr/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal,
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
