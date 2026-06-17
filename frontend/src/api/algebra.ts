import { requestJson } from './core';

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

export interface AlgebraSolveRequest {
  input: string;
  input_format?: AlgebraInputFormat;
  topic?: AlgebraTopic;
  variables?: string[];
  parameters?: string[];
  domain?: 'R' | 'C' | 'N' | 'Z';
  options?: AlgebraSolveOptions;
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
}

export async function solveAlgebra(payload: AlgebraSolveRequest): Promise<AlgebraSolveResponse> {
  return requestJson('/api/algebra/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể giải bài đại số.');
}
