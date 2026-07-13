import type { InterpretationCandidate, InterpretationResponse, InterpretationStatus } from '../../api/nlp';

export type PreflightPhase = 'idle' | 'loading' | 'ready' | 'error';

export interface PreflightState {
  phase: PreflightPhase;
  response: InterpretationResponse | null;
  selectedCandidateId: string | null;
  error: string | null;
}

export const initialPreflightState: PreflightState = {
  phase: 'idle',
  response: null,
  selectedCandidateId: null,
  error: null,
};

export function loadingPreflightState(): PreflightState {
  return { phase: 'loading', response: null, selectedCandidateId: null, error: null };
}

export function resolvedPreflightState(response: InterpretationResponse): PreflightState {
  return {
    phase: 'ready',
    response,
    selectedCandidateId: response.selected_candidate_id ?? response.candidates[0]?.candidate_id ?? null,
    error: null,
  };
}

export function failedPreflightState(message: string): PreflightState {
  return { phase: 'error', response: null, selectedCandidateId: null, error: message };
}

export function selectPreflightCandidate(state: PreflightState, candidateId: string): PreflightState {
  if (!state.response?.candidates.some((candidate) => candidate.candidate_id === candidateId)) return state;
  return { ...state, selectedCandidateId: candidateId };
}

export function selectedPreflightCandidate(state: PreflightState): InterpretationCandidate | null {
  return state.response?.candidates.find((candidate) => candidate.candidate_id === state.selectedCandidateId) ?? null;
}

export function candidateCanonicalText(candidate: InterpretationCandidate, response: InterpretationResponse): string {
  return candidate.canonical_text?.trim() || response.normalized_text.trim();
}

export function candidateCanRun(candidate: InterpretationCandidate, response: InterpretationResponse): boolean {
  return !candidate.unsupported_reason
    && candidate.missing_fields.length === 0
    && candidateCanonicalText(candidate, response).length > 0;
}

export function statusBlocksExecution(status: InterpretationStatus): boolean {
  return status === 'abstained' || status === 'unsupported';
}