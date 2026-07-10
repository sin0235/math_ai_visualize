import { ApiError, apiUrl, fetchWithRetry, networkApiError, parseApiError, requestJson } from './core';

export type AlgebraTopic = 'auto' | 'equation' | 'inequality' | 'exponential_log' | 'trigonometry' | 'complex' | 'sequence' | 'combinatorics_probability' | 'system' | 'parameter' | 'calculus_derivative' | 'calculus_limit' | 'calculus_integral';
export type AlgebraStatus = 'solved' | 'partial' | 'unsupported' | 'error';
export type AlgebraVerificationStatus = 'verified' | 'partially_verified' | 'failed' | 'skipped';
export type AlgebraInputFormat = 'auto' | 'plain' | 'latex' | 'structured';

export interface AlgebraSolveOptions {
  return_steps?: boolean;
  verify?: boolean;
  max_solutions?: number;
  prefer_exact?: boolean;
  grade_level?: 'C3';
  use_ai_extraction?: boolean;
  ai_explanation?: boolean;
}

export interface AlgebraInterval {
  variable?: string;
  start?: string | null;
  end?: string | null;
  closed_start?: boolean;
  closed_end?: boolean;
}

export type AlgebraAngleUnit = 'radian' | 'degree';
export type AlgebraDomainSource = 'default' | 'user';

export interface AlgebraSolveRequest {
  input: string;
  input_format?: AlgebraInputFormat;
  topic?: AlgebraTopic;
  variables?: string[];
  parameters?: string[];
  domain?: 'R' | 'C' | 'N' | 'Z';
  domain_source?: AlgebraDomainSource;
  angle_unit?: AlgebraAngleUnit;
  interval?: AlgebraInterval | null;
  options?: AlgebraSolveOptions;
  save_history?: boolean;
}

export interface AlgebraInputChip {
  kind: 'intent' | 'format' | 'topic' | 'domain' | 'variable' | 'expression' | 'relation' | 'system';
  label: string;
  value: string;
}

export interface AlgebraInputInterpretation {
  detected_format: 'plain' | 'latex' | 'natural_vi' | 'mixed' | 'structured';
  source: 'raw' | 'rule_based_vi' | 'latex_normalizer' | 'structured_ui';
  canonical_input: string;
  topic_hint: AlgebraTopic;
  variables: string[];
  domain: 'R' | 'C' | 'N' | 'Z';
  chips: AlgebraInputChip[];
  warnings: string[];
}

export interface AlgebraSolutionValue {
  text: string;
  latex?: string | null;
  approximate?: string | null;
}

export interface AlgebraSolutionSet {
  kind: 'finite' | 'set' | 'interval' | 'periodic' | 'conditions' | 'expression' | 'empty' | 'unknown';
  text: string;
  latex?: string | null;
  values: AlgebraSolutionValue[];
}

export interface AlgebraVerificationCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn' | 'skip';
  detail: string;
  latex?: string | null;
}

export interface AlgebraVerificationReport {
  status: AlgebraVerificationStatus;
  checks: AlgebraVerificationCheck[];
  method: string[];
}

export interface AlgebraSolveStep {
  index: number;
  title: string;
  explanation: string;
  short_explanation?: string | null;
  detail_level?: 'brief' | 'standard' | 'detailed';
  method?: string | null;
  goal?: string | null;
  why?: string | null;
  rule?: string | null;
  operation?: string | null;
  before_latex?: string | null;
  after_latex?: string | null;
  pitfall?: string | null;
  check?: string | null;
  expression?: string | null;
  expression_latex?: string | null;
  result?: string | null;
  result_latex?: string | null;
  kind?: 'normalize' | 'domain' | 'transform' | 'solve' | 'verify' | 'conclusion' | null;
  confidence?: 'verified' | 'symbolic' | 'numeric_checked' | 'unverified' | null;
  sub_steps?: AlgebraSolveStep[];
}

export interface AlgebraSolveResponse {
  input: string;
  normalized_input: string;
  input_interpretation?: AlgebraInputInterpretation | null;
  topic: string;
  problem_type: string;
  status: AlgebraStatus;
  answer: string;
  answer_latex?: string | null;
  solution_set: AlgebraSolutionSet;
  steps: AlgebraSolveStep[];
  verification: AlgebraVerificationReport;
  assumptions: string[];
  warnings: string[];
  errors: string[];
  request_id?: string | null;
  timings_ms?: Record<string, number>;
  history_id?: string | null;
  cost_score?: number | null;
}

export interface AlgebraHistoryItem {
  id: string;
  title?: string | null;
  problem_preview: string;
  topic: string;
  status: string;
  request_id?: string | null;
  is_favorite: boolean;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AlgebraHistoryDetail extends AlgebraHistoryItem {
  request_json: Record<string, unknown>;
  response?: AlgebraSolveResponse | null;
}

export async function solveAlgebra(
  payload: AlgebraSolveRequest,
  init?: { signal?: AbortSignal },
): Promise<AlgebraSolveResponse> {
  try {
    const response = await fetchWithRetry(apiUrl('/api/algebra/solve'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
      signal: init?.signal,
    });
    const body = await response.text();
    if (!body.trim()) throw new ApiError('Không thể giải bài đại số.');
    let parsed: unknown;
    try {
      parsed = JSON.parse(body);
    } catch {
      throw new ApiError('Không thể giải bài đại số.');
    }
    if (
      response.status === 504
      && parsed
      && typeof parsed === 'object'
      && 'status' in (parsed as object)
      && 'answer' in (parsed as object)
    ) {
      return parsed as AlgebraSolveResponse;
    }
    if (!response.ok) {
      throw await parseApiError(
        new Response(body, { status: response.status, headers: response.headers }),
        `Không thể giải bài đại số. HTTP ${response.status}`,
      );
    }
    return parsed as AlgebraSolveResponse;
  } catch (caught) {
    if (caught instanceof DOMException && caught.name === 'AbortError') {
      throw new ApiError('Đã hủy yêu cầu giải.');
    }
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, 'Không thể giải bài đại số.');
  }
}

export async function listAlgebraHistory(params?: {
  limit?: number;
  q?: string;
  topic?: string;
}): Promise<AlgebraHistoryItem[]> {
  const search = new URLSearchParams();
  if (params?.limit) search.set('limit', String(params.limit));
  if (params?.q) search.set('q', params.q);
  if (params?.topic) search.set('topic', params.topic);
  const qs = search.toString();
  return requestJson(
    `/api/algebra/history${qs ? `?${qs}` : ''}`,
    { method: 'GET', credentials: 'include' },
    'Không tải được lịch sử đại số.',
  );
}

export async function getAlgebraHistory(id: string): Promise<AlgebraHistoryDetail> {
  return requestJson(
    `/api/algebra/history/${encodeURIComponent(id)}`,
    { method: 'GET', credentials: 'include' },
    'Không tải được chi tiết lịch sử.',
  );
}

export async function deleteAlgebraHistory(id: string): Promise<void> {
  await requestJson(
    `/api/algebra/history/${encodeURIComponent(id)}`,
    { method: 'DELETE', credentials: 'include' },
    'Không xóa được lịch sử.',
  );
}

export async function downloadAlgebraPdf(response: AlgebraSolveResponse): Promise<void> {
  const res = await fetchWithRetry(apiUrl('/api/algebra/export/pdf'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ response }),
  });
  if (!res.ok) {
    throw await parseApiError(res, 'Không xuất được PDF.');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `algebra-solution-${(response.request_id || 'export').slice(0, 16)}.pdf`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}
