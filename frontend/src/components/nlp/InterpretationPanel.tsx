import { useEffect, useId, useRef, useState } from 'react';
import { trackNlpEvent, type NlpTelemetryCode } from '../../utils/telemetry';
import { KatexSpan } from '../KatexSpan';
import {
  interpretMathInput,
  type InterpretationCandidate,
  type InterpretationResponse,
  type InterpretInput,
  type NlpFact,
  type NlpTarget,
} from '../../api/nlp';
import {
  candidateCanonicalText,
  candidateCanRun,
  failedPreflightState,
  initialPreflightState,
  loadingPreflightState,
  resolvedPreflightState,
  selectPreflightCandidate,
  selectedPreflightCandidate,
  statusBlocksExecution,
  type PreflightState,
} from './preflightState';

interface ConfirmedInterpretation {
  candidate: InterpretationCandidate;
  response: InterpretationResponse;
}

export interface InterpretationPreflightController {
  state: PreflightState;
  check: (input: Omit<InterpretInput, 'provenance'>) => Promise<ConfirmedInterpretation | null>;
  confirm: (editedText: string) => Promise<ConfirmedInterpretation | null>;
  selectCandidate: (candidateId: string) => void;
  reset: () => void;
}

interface PendingInterpretation {
  text: string;
  target: NlpTarget;
  context?: Record<string, unknown>;
}

export function useInterpretationPreflight(): InterpretationPreflightController {
  const [state, setState] = useState<PreflightState>(initialPreflightState);
  const pendingRef = useRef<PendingInterpretation | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function request(input: InterpretInput, failureCode?: NlpTelemetryCode): Promise<InterpretationResponse | null> {
    const requestId = ++requestIdRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState(loadingPreflightState());
    try {
      const response = await interpretMathInput(input, controller.signal);
      if (requestId !== requestIdRef.current || controller.signal.aborted) return null;
      setState(resolvedPreflightState(response));
      trackInterpretationResponse(response);
      return response;
    } catch (caught) {
      if (requestId !== requestIdRef.current || controller.signal.aborted) return null;
      setState(failedPreflightState(caught instanceof Error ? caught.message : 'Không thể kiểm tra cách hiểu đề.'));
      if (failureCode && input.target !== 'auto') {
        trackNlpEvent({ taxonomyCode: failureCode, target: input.target });
      }
      return null;
    }
  }

  async function check(input: PendingInterpretation) {
    pendingRef.current = input;
    const response = await request(input);
    if (!response || response.status !== 'accepted') return null;
    const candidate = response.candidates.find((item) => item.candidate_id === response.selected_candidate_id);
    return candidate && candidateCanRun(candidate, response) ? { candidate, response } : null;
  }

  async function confirm(editedText: string) {
    const response = state.response;
    const candidate = selectedPreflightCandidate(state);
    const pending = pendingRef.current;
    if (!response || !candidate || !pending || statusBlocksExecution(response.status)) return null;
    const canonicalText = candidateCanonicalText(candidate, response);
    const confirmedText = editedText.trim();
    if (!confirmedText) return null;
    if (confirmedText === canonicalText) {
      if (!candidateCanRun(candidate, response)) return null;
      trackNlpEvent({
        taxonomyCode: 'clarification_accepted',
        target: response.target,
        status: response.status,
        confidence: candidate.confidence,
        candidateCount: response.candidates.length,
        adapterVersion: response.adapter_version,
      });
      return { candidate, response };
    }

    const confirmedResponse = await request({
      ...pending,
      text: confirmedText,
      provenance: [{ source: 'user_confirmed' }],
    }, 'canonical_validation_failure');
    if (!confirmedResponse || statusBlocksExecution(confirmedResponse.status)) return null;
    const confirmedCandidate = confirmedResponse.candidates.find(
      (item) => item.candidate_id === confirmedResponse.selected_candidate_id,
    ) ?? confirmedResponse.candidates[0];
    if (!confirmedCandidate || !candidateCanRun(confirmedCandidate, confirmedResponse)) return null;
    trackNlpEvent({
      taxonomyCode: 'clarification_edited',
      target: confirmedResponse.target,
      status: confirmedResponse.status,
      confidence: confirmedCandidate.confidence,
      candidateCount: confirmedResponse.candidates.length,
      adapterVersion: confirmedResponse.adapter_version,
    });
    return { candidate: confirmedCandidate, response: confirmedResponse };
  }

  function reset() {
    requestIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    pendingRef.current = null;
    setState(initialPreflightState);
  }

  return {
    state,
    check,
    confirm,
    selectCandidate: (candidateId) => setState((current) => selectPreflightCandidate(current, candidateId)),
    reset,
  };
}

export function InterpretationPanel({
  controller,
  title = 'Xác nhận cách hiểu đề',
  confirmLabel = 'Xác nhận và tiếp tục',
  onConfirm,
}: {
  controller: InterpretationPreflightController;
  title?: string;
  confirmLabel?: string;
  onConfirm: (confirmed: ConfirmedInterpretation) => void | Promise<void>;
}) {
  const { state } = controller;
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const [editedText, setEditedText] = useState('');
  const candidate = selectedPreflightCandidate(state);
  const response = state.response;

  useEffect(() => {
    if (state.phase === 'ready' || state.phase === 'error') panelRef.current?.focus();
  }, [state.phase]);

  useEffect(() => {
    setEditedText(candidate && response ? candidateCanonicalText(candidate, response) : '');
  }, [candidate?.candidate_id, response]);

  if (state.phase === 'idle') return null;
  if (state.phase === 'loading') {
    return <section className="nlp-preflight nlp-preflight--loading" role="status" aria-live="polite">Đang kiểm tra cách hiểu đề…</section>;
  }
  if (state.phase === 'error') {
    return (
      <section ref={panelRef} className="nlp-preflight nlp-preflight--error" role="alert" tabIndex={-1}>
        <strong>Không kiểm tra được đề</strong>
        <p>{state.error}</p>
        <button type="button" className="secondary-button" onClick={controller.reset}>Đóng</button>
      </section>
    );
  }
  if (!response) return null;

  const blocked = statusBlocksExecution(response.status);
  const canonicalText = candidate && candidateCanonicalText(candidate, response);
  const canonicalPreview = candidate ? mathPreview(candidate, editedText) : null;
  const editedCandidate = Boolean(candidate && editedText.trim() && editedText.trim() !== canonicalText);
  const canConfirm = Boolean(candidate && editedText.trim() && (editedCandidate || candidateCanRun(candidate, response)));
  const reason = response.status === 'abstained'
    ? 'Chưa tìm được cách hiểu đủ dữ kiện.'
    : response.status === 'unsupported'
      ? 'Yêu cầu nằm ngoài phạm vi công cụ.'
      : null;

  return (
    <section
      ref={panelRef}
      className={`nlp-preflight nlp-preflight--${response.status}`}
      role="dialog"
      aria-labelledby={titleId}
      tabIndex={-1}
    >
      <div className="nlp-preflight__head">
        <div>
          <span className="nlp-preflight__status">{statusLabel(response.status)}</span>
          <h2 id={titleId}>{title}</h2>
        </div>
        <button type="button" className="secondary-button" onClick={controller.reset}>Sửa đề</button>
      </div>

      {reason && <p className="nlp-preflight__blocking" role="alert">{reason}</p>}
      {response.candidates.length > 1 && (
        <fieldset className="nlp-preflight__candidates">
          <legend>Chọn cách hiểu</legend>
          {response.candidates.map((item) => (
            <label key={item.candidate_id}>
              <input
                type="radio"
                name={`${titleId}-candidate`}
                checked={item.candidate_id === state.selectedCandidateId}
                onChange={() => controller.selectCandidate(item.candidate_id)}
              />
              <span>{intentLabel(item)} · {formatConfidence(item.confidence)}</span>
            </label>
          ))}
        </fieldset>
      )}

      {candidate && (
        <div className="nlp-preflight__body">
          <dl className="nlp-preflight__summary">
            <div><dt>Mục tiêu</dt><dd>{intentLabel(candidate)}</dd></div>
            <div><dt>Độ tin cậy</dt><dd>{formatConfidence(candidate.confidence)}</dd></div>
            <div><dt>Nguồn</dt><dd>{provenanceLabel(candidate)}</dd></div>
          </dl>

          <label className="nlp-preflight__canonical">
            <span>Cách hiểu có thể chỉnh sửa</span>
            {canonicalPreview && (
              <span className="nlp-preflight__math-preview" aria-label="Xem trước công thức">
                <KatexSpan tex={canonicalPreview} />
              </span>
            )}
            <textarea
              value={editedText}
              onChange={(event) => setEditedText(event.target.value)}
              rows={3}
              maxLength={2000}
              disabled={blocked}
            />
          </label>

          <InterpretationDetails candidate={candidate} />
          {candidate.clarification_question && <p className="nlp-preflight__question">{candidate.clarification_question}</p>}
          {candidate.unsupported_reason && <p className="nlp-preflight__blocking">{candidate.unsupported_reason}</p>}
        </div>
      )}

      <div className="nlp-preflight__actions">
        <button type="button" className="secondary-button" onClick={controller.reset}>Hủy</button>
        <button
          type="button"
          className="auth-primary-button"
          disabled={!canConfirm || blocked}
          onClick={() => void controller.confirm(editedText).then((confirmed) => confirmed && onConfirm(confirmed))}
        >
          {confirmLabel}
        </button>
      </div>
    </section>
  );
}

function InterpretationDetails({ candidate }: { candidate: InterpretationCandidate }) {
  const givens = candidate.givens ?? [];
  const goals = candidate.goals ?? [];
  const unknowns = candidate.unknowns ?? [];
  const clarificationOptions = candidate.clarification_options ?? [];
  const details = [
    givens.length ? ['Dữ kiện đã hiểu', givens.map(factLabel).join('; ')] : null,
    goals.length ? ['Mục tiêu', goals.map(factLabel).join('; ')] : null,
    unknowns.length ? ['Chưa xác định', unknowns.join(', ')] : null,
    !givens.length && candidate.entities.length ? ['Đối tượng', candidate.entities.map((item) => `${item.name}${item.value === null || item.value === undefined || item.value === item.name ? '' : ` = ${String(item.value)}`}`).join(', ')] : null,
    !givens.length && candidate.constraints.length ? ['Ràng buộc', candidate.constraints.map((item) => `${item.kind}(${item.arguments.join(', ')})${item.value === null || item.value === undefined ? '' : ` = ${String(item.value)}`}`).join('; ')] : null,
    candidate.assumptions.length ? ['Giả định', candidate.assumptions.join('; ')] : null,
    candidate.missing_fields.length ? ['Còn thiếu', candidate.missing_fields.join(', ')] : null,
    candidate.ambiguities.length ? ['Điểm chưa rõ', candidate.ambiguities.map((item) => `${item.message}${item.alternatives.length ? ` Chọn: ${item.alternatives.join(' / ')}` : ''}`).join('; ')] : null,
    clarificationOptions.length ? ['Lựa chọn xác nhận', clarificationOptions.join(' / ')] : null,
    candidate.field_confidences.length ? ['Độ tin cậy từng phần', candidate.field_confidences.map((item) => `${item.field}: ${formatConfidence(item.confidence)}`).join('; ')] : null,
  ].filter((item): item is string[] => item !== null);
  if (!details.length) return null;
  return (
    <dl className="nlp-preflight__details">
      {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>
  );
}

function factLabel(fact: NlpFact) {
  const subject = fact.name || (fact.arguments.length ? `${fact.kind}(${fact.arguments.join(', ')})` : fact.kind);
  return fact.value === null || fact.value === undefined ? subject : `${subject} = ${String(fact.value)}`;
}


function mathPreview(candidate: InterpretationCandidate, value: string) {
  const text = value.trim();
  if (!text || /\b(?:derivative|integral|limit|stats|quadratic_)\s*\(/i.test(text)) return null;
  const format = candidate.canonical_payload?.input_format;
  if (format === 'latex') return text;
  if (/^[\dA-Za-z\\_{}()[\].,+\-*/^=<>!\s]+$/.test(text) && /[=<>^\\]/.test(text)) return text;
  return null;
}

function trackInterpretationResponse(response: InterpretationResponse) {
  const candidate = response.candidates.find((item) => item.candidate_id === response.selected_candidate_id)
    ?? response.candidates[0];
  const base = {
    target: response.target,
    status: response.status,
    confidence: candidate?.confidence,
    candidateCount: response.candidates.length,
    adapterVersion: response.adapter_version,
  };
  if (!candidate || candidate.intent.domain === 'unknown' || candidate.intent.task === 'unknown') {
    trackNlpEvent({ taxonomyCode: 'unknown_intent', ...base });
  }
  if (candidate && candidate.confidence < 0.65) {
    trackNlpEvent({ taxonomyCode: 'low_confidence', ...base });
  }
  if (response.status === 'needs_confirmation') {
    trackNlpEvent({ taxonomyCode: 'clarification_shown', ...base });
  }
  if (response.status === 'unsupported') {
    trackNlpEvent({ taxonomyCode: 'solver_unsupported', ...base });
  }
}

function statusLabel(status: InterpretationResponse['status']) {
  if (status === 'accepted') return 'Đã hiểu';
  if (status === 'needs_confirmation') return 'Cần xác nhận';
  if (status === 'unsupported') return 'Không hỗ trợ';
  return 'Chưa đủ dữ kiện';
}

function intentLabel(candidate: InterpretationCandidate) {
  return [candidate.intent.topic, candidate.intent.task].filter(Boolean).join(' · ');
}

function formatConfidence(value: number) {
  return `${Math.round(value * 100)}%`;
}

function provenanceLabel(candidate: InterpretationCandidate) {
  return Array.from(new Set(candidate.provenance.map((item) => item.source))).join(', ') || 'không xác định';
}