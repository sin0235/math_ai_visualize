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

export interface AnalyzeParameterRange {
  min: number;
  max: number;
  step: number;
}

export interface AnalyzeParameters {
  detected: string[];
  active: Record<string, number>;
  ranges: Record<string, AnalyzeParameterRange>;
}

export interface AnalyzeOptions {
  parameters?: { m?: number };
  interval?: { a: number; b: number; open_a?: boolean; open_b?: boolean };
  line?: { k?: number; b?: number; mode?: string; x0?: number };
  parameter_conditions?: { targets: string[]; extrema_count?: number };
  transform?: { type: string; value: number };
}

export interface AnalyzeResponse {
  expression: string;
  expression_latex: string | null;
  evaluated_expression: string | null;
  evaluated_expression_latex: string | null;
  parameters: AnalyzeParameters | null;
  analysis_mode: 'symbolic' | 'numeric_substituted' | null;
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
  y_intercept: string | null;
  variation_table: VariationRow[];
  domain: string | null;
  domain_latex: string | null;
  range_val: string | null;
  range_latex: string | null;
  parity: 'even' | 'odd' | 'neither' | null;
  geogebra_commands: string[];
  graph_scene: MathScene | null;
  graph_points: Array<{ x: number; y: number }>;
  ocr_text: string | null;
  ocr_expression: string | null;
  interval_analysis?: {
    a: string;
    b: string;
    open_a?: boolean;
    open_b?: boolean;
    fa: string;
    fb: string;
    extrema_inside: Array<{ x: string; x_exact: string; y: string; label: string }>;
    max_point: { x: string; y: string; label: string };
    min_point: { x: string; y: string; label: string };
    conclusion: string;
  } | null;
  line_analysis?: {
    mode?: string;
    equation: string;
    intersection_count: number;
    intersections: Array<{ x: string; y: string; x_exact: string }>;
    relative_intervals: { above: string[]; below: string[] };
    area_between_curves?: string | null;
    conclusion?: string;
  } | null;
  parameter_conditions?: Array<{ label: string; condition_latex?: string; solution: string; solution_latex?: string; warnings?: string[] }>;
  transform_preview?: { type: string; value: string; label: string; expression: string; expression_latex: string; pedagogical_steps?: string[] } | null;
  capabilities?: Record<string, unknown> | null;
  warnings: string[];
  error?: string | null;
}

export async function analyzeFunction(expression: string, options?: AnalyzeOptions | { m?: number }): Promise<AnalyzeResponse> {
  const hasAnalyzeOptions = !!options && ('parameters' in options || 'interval' in options || 'line' in options || 'parameter_conditions' in options || 'transform' in options);
  const payloadOptions = hasAnalyzeOptions ? options as AnalyzeOptions : { parameters: options as { m?: number } | undefined };
  return requestJson('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ expression, ...payloadOptions }),
  }, 'Không thể phân tích hàm số.');
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
