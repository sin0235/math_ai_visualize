import { requestJson } from './core';

export type NlpTarget = 'auto' | 'render' | 'geometry_solve' | 'algebra' | 'analyzer' | 'ocr';
export type NlpInputMode = 'natural' | 'math' | 'mixed';
export type NlpInputFormat = 'auto' | 'plain' | 'latex' | 'structured';
export type InterpretationStatus = 'accepted' | 'needs_confirmation' | 'abstained' | 'unsupported';

export interface NlpProvenance {
  source: 'raw' | 'normalized' | 'rule' | 'existing_metadata' | 'ocr' | 'user_confirmed' | 'deterministic_engine' | 'language_model';
  adapter?: string | null;
  version?: string | null;
  spans?: Array<{ start: number; end: number }>;
  provider?: string | null;
  model?: string | null;
}

export interface InterpretationEntity {
  kind: string;
  name: string;
  value?: string | number | boolean | null;
  unit?: string | null;
  confidence: number;
  provenance: NlpProvenance[];
}

export interface InterpretationConstraint {
  kind: string;
  arguments: string[];
  value?: string | number | boolean | null;
  confidence: number;
  provenance: NlpProvenance[];
}

export interface NlpFact {
  kind: string;
  name?: string | null;
  arguments: string[];
  value?: string | number | boolean | null;
  confidence: number;
  evidence: Array<{ start: number; end: number }>;
  provenance: NlpProvenance[];
}

export interface InterpretationValidation {
  state: 'unchecked' | 'validated' | 'rejected' | 'needs_review';
  codes: string[];
  prompt_version?: string | null;
  contract_version: string;
}

export interface InterpretationAmbiguity {
  code: string;
  message: string;
  field?: string | null;
  alternatives: string[];
  provenance: NlpProvenance[];
}

export interface InterpretationCandidate {
  candidate_id: string;
  intent: { domain: string; topic: string; task: string; subtype?: string | null };
  canonical_text?: string | null;
  canonical_payload?: Record<string, unknown> | null;
  entities: InterpretationEntity[];
  constraints: InterpretationConstraint[];
  givens?: NlpFact[];
  goals?: NlpFact[];
  unknowns?: string[];
  ambiguities: InterpretationAmbiguity[];
  clarification_options?: string[];
  field_confidences: Array<{ field: string; confidence: number; calibrated: boolean }>;
  confidence: number;
  assumptions: string[];
  missing_fields: string[];
  unsupported_reason?: string | null;
  clarification_question?: string | null;
  provenance: NlpProvenance[];
  validation?: InterpretationValidation;
}

export interface InterpretationResponse {
  target: Exclude<NlpTarget, 'auto'>;
  status: InterpretationStatus;
  normalized_text: string;
  candidates: InterpretationCandidate[];
  selected_candidate_id?: string | null;
  adapter_version: string;
}

export interface InterpretInput {
  text: string;
  target: NlpTarget;
  input_mode?: NlpInputMode;
  input_format?: NlpInputFormat;
  context?: Record<string, unknown>;
  provenance?: NlpProvenance[];
}

export function interpretMathInput(payload: InterpretInput, signal?: AbortSignal) {
  return requestJson<InterpretationResponse>(
    '/api/nlp/interpret',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
      signal,
    },
    'Không thể kiểm tra cách hiểu đề.',
  );
}