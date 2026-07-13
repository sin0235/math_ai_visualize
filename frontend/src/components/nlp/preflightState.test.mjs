import assert from 'node:assert/strict';

import {
  candidateCanRun,
  initialPreflightState,
  resolvedPreflightState,
  selectPreflightCandidate,
  selectedPreflightCandidate,
  statusBlocksExecution,
} from './preflightState.ts';

const candidate = (overrides = {}) => ({
  candidate_id: 'candidate-1',
  intent: { domain: 'algebra', topic: 'equation', task: 'solve' },
  canonical_text: 'x^2=1',
  canonical_payload: { input: 'x^2=1' },
  entities: [],
  constraints: [],
  ambiguities: [],
  field_confidences: [],
  confidence: 0.9,
  assumptions: [],
  missing_fields: [],
  unsupported_reason: null,
  clarification_question: null,
  provenance: [],
  ...overrides,
});

const response = (status, candidates = [candidate()]) => ({
  target: 'algebra',
  status,
  normalized_text: 'x^2=1',
  candidates,
  selected_candidate_id: candidates[0]?.candidate_id ?? null,
  adapter_version: 'test',
});

assert.equal(initialPreflightState.phase, 'idle');

const accepted = resolvedPreflightState(response('accepted'));
assert.equal(accepted.phase, 'ready');
assert.equal(selectedPreflightCandidate(accepted)?.candidate_id, 'candidate-1');
assert.equal(candidateCanRun(selectedPreflightCandidate(accepted), accepted.response), true);

const alternatives = resolvedPreflightState(response('needs_confirmation', [
  candidate(),
  candidate({ candidate_id: 'candidate-2', canonical_text: 'x^2=-1' }),
]));
const selected = selectPreflightCandidate(alternatives, 'candidate-2');
assert.equal(selectedPreflightCandidate(selected)?.canonical_text, 'x^2=-1');
assert.equal(selectPreflightCandidate(selected, 'missing'), selected);

assert.equal(candidateCanRun(candidate({ missing_fields: ['relation'] }), response('needs_confirmation')), false);
assert.equal(candidateCanRun(candidate({ unsupported_reason: 'unsupported' }), response('unsupported')), false);
assert.equal(statusBlocksExecution('abstained'), true);
assert.equal(statusBlocksExecution('unsupported'), true);
assert.equal(statusBlocksExecution('needs_confirmation'), false);

console.log('preflight state tests passed');