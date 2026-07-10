import { useMemo, useRef, useState } from 'react';
import { ApiError, solveAlgebra, type AlgebraInputFormat, type AlgebraInterval, type AlgebraSolveResponse, type AlgebraTopic } from '../api/client';
import { AlgebraInput, suggestTopic, type AlgebraAngleUnit, type AlgebraInputMode, type SequenceDraft } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';
import {
  clearAlgebraHistory,
  loadAlgebraHistory,
  saveAlgebraHistoryItem,
  type AlgebraHistoryItem,
} from './algebra-solver/algebraHistory';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
export type IntervalPreset = '' | 'unit_circle' | 'custom';

export function AlgebraSolverPage() {
  const [input, setInput] = useState('');
  const [inputMode, setInputMode] = useState<AlgebraInputMode>('natural');
  const [inputFormat, setInputFormat] = useState<AlgebraInputFormat>('auto');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [variables, setVariables] = useState('');
  const [useAiExtraction, setUseAiExtraction] = useState(false);
  const [angleUnit, setAngleUnit] = useState<AlgebraAngleUnit>('radian');
  /** empty = full R; unit_circle = [0, 2π); custom = user bounds */
  const [intervalPreset, setIntervalPreset] = useState<IntervalPreset>('');
  const [intervalStart, setIntervalStart] = useState('0');
  const [intervalEnd, setIntervalEnd] = useState('2*pi');
  const [intervalClosedStart, setIntervalClosedStart] = useState(true);
  const [intervalClosedEnd, setIntervalClosedEnd] = useState(false);
  const [result, setResult] = useState<AlgebraSolveResponse | null>(null);
  const [solvedFingerprint, setSolvedFingerprint] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  /** Pre-solve confirmation for natural / AI paths (trust boundary). */
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [history, setHistory] = useState<AlgebraHistoryItem[]>(() => loadAlgebraHistory());
  const submitLockRef = useRef(false);
  const [sequenceDraft, setSequenceDraft] = useState<SequenceDraft>({
    kind: 'arithmetic',
    target: 'term',
    u1: '2',
    d: '3',
    q: '2',
    n: '10',
  });

  const currentFingerprint = useMemo(
    () => fingerprintRequest({
      input, inputMode, inputFormat, topic, domain, variables, useAiExtraction, angleUnit,
      intervalPreset, intervalStart, intervalEnd, intervalClosedStart, intervalClosedEnd, sequenceDraft,
    }),
    [input, inputMode, inputFormat, topic, domain, variables, useAiExtraction, angleUnit, intervalPreset, intervalStart, intervalEnd, intervalClosedStart, intervalClosedEnd, sequenceDraft],
  );
  const resultStale = Boolean(result && solvedFingerprint && currentFingerprint !== solvedFingerprint);

  const sequenceInput = topic === 'sequence' ? sequenceInputFromDraft(sequenceDraft) : '';
  const cleanInput = input.trim();
  const payloadInput = sequenceInput || cleanInput;
  const inferredTopic = sequenceInput ? 'sequence' as const : suggestTopic(cleanInput);
  const payloadTopic = (inferredTopic && inferredTopic !== topic ? inferredTopic : topic) as AlgebraTopic;
  const variableList = variables.split(',').map((item) => item.trim()).filter(Boolean);
  const intervalPayload = buildIntervalPayload({
    intervalPreset,
    intervalStart,
    intervalEnd,
    intervalClosedStart,
    intervalClosedEnd,
    angleUnit,
  });

  function requestConfirmIfNeeded() {
    if (!payloadInput || loading || submitLockRef.current) return;
    // Math mode + no AI: direct solve. Natural or AI: confirm interpretation intent first.
    if (inputMode === 'math' && !useAiExtraction && !sequenceInput) {
      void runSolve();
      return;
    }
    setPendingConfirm(true);
    setError('');
  }

  async function runSolve() {
    if (!payloadInput || loading || submitLockRef.current) return;
    submitLockRef.current = true;
    setPendingConfirm(false);
    setLoading(true);
    setError('');
    try {
      const response = await solveAlgebra({
        input: payloadInput,
        input_format: sequenceInput ? 'structured' : inputFormat,
        topic: payloadTopic,
        domain,
        variables: variableList,
        angle_unit: angleUnit,
        interval: intervalPayload,
        options: {
          // Natural mode defaults to rule-based; AI only when user opts in.
          use_ai_extraction: inputMode === 'natural' && useAiExtraction && !sequenceInput,
        },
      });
      setResult(response);
      setSolvedFingerprint(currentFingerprint);
      if (response.status !== 'error' || response.problem_type === 'timeout') {
        setHistory(saveAlgebraHistoryItem(response));
      }
    } catch (caught) {
      // Do not leave a prior successful answer looking "current" after 429/5xx errors.
      setResult(null);
      setSolvedFingerprint('');
      if (caught instanceof ApiError) setError(caught.message);
      else setError(caught instanceof Error ? caught.message : 'Không thể giải bài đại số.');
    } finally {
      setLoading(false);
      submitLockRef.current = false;
    }
  }

  function handleApplyCanonical(canonical: string) {
    setInput(canonical);
    setInputMode('math');
    setInputFormat('plain');
    setUseAiExtraction(false);
    setPendingConfirm(false);
  }

  function restoreHistoryItem(item: AlgebraHistoryItem) {
    setInput(item.input);
    setInputMode('math');
    setInputFormat('plain');
    setUseAiExtraction(false);
    setPendingConfirm(false);
    setError('');
  }

  return (
    <section className="algebra-solver-page">
      <div className="algebra-workspace">
        <AlgebraInput
          input={input}
          inputFormat={inputFormat}
          inputMode={inputMode}
          topic={topic}
          domain={domain}
          variables={variables}
          useAiExtraction={useAiExtraction}
          angleUnit={angleUnit}
          intervalPreset={intervalPreset}
          intervalStart={intervalStart}
          intervalEnd={intervalEnd}
          intervalClosedStart={intervalClosedStart}
          intervalClosedEnd={intervalClosedEnd}
          loading={loading}
          onInputChange={(value) => { setInput(value); setPendingConfirm(false); }}
          onInputFormatChange={setInputFormat}
          onInputModeChange={(value) => { setInputMode(value); setPendingConfirm(false); }}
          onTopicChange={(value) => { setTopic(value); setPendingConfirm(false); }}
          onDomainChange={(value) => { setDomain(value); setPendingConfirm(false); }}
          onVariablesChange={(value) => { setVariables(value); setPendingConfirm(false); }}
          onUseAiExtractionChange={(value) => { setUseAiExtraction(value); setPendingConfirm(false); }}
          onAngleUnitChange={(value) => { setAngleUnit(value); setPendingConfirm(false); }}
          onIntervalPresetChange={(value) => { setIntervalPreset(value); setPendingConfirm(false); }}
          onIntervalStartChange={(value) => { setIntervalStart(value); setPendingConfirm(false); }}
          onIntervalEndChange={(value) => { setIntervalEnd(value); setPendingConfirm(false); }}
          onIntervalClosedStartChange={(value) => { setIntervalClosedStart(value); setPendingConfirm(false); }}
          onIntervalClosedEndChange={(value) => { setIntervalClosedEnd(value); setPendingConfirm(false); }}
          sequenceDraft={sequenceDraft}
          onSequenceDraftChange={(value) => { setSequenceDraft(value); setPendingConfirm(false); }}
          onSubmit={requestConfirmIfNeeded}
        />
        <div className="algebra-result-wrap">
          {history.length > 0 && (
            <section className="algebra-history-panel" aria-label="Lịch sử bài gần đây">
              <div className="algebra-history-head">
                <strong>Lịch sử gần đây (máy này)</strong>
                <button
                  type="button"
                  className="algebra-action-btn"
                  onClick={() => { clearAlgebraHistory(); setHistory([]); }}
                >
                  Xóa
                </button>
              </div>
              <ul className="algebra-history-list">
                {history.slice(0, 8).map((item) => (
                  <li key={item.id}>
                    <button type="button" className="algebra-history-item" onClick={() => restoreHistoryItem(item)}>
                      <span className="algebra-history-meta">{item.topic} · {item.status}</span>
                      <span className="algebra-history-input">{item.input}</span>
                      <span className="algebra-history-answer">{item.answer}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {error && <div className="sp-error"><strong>Solver lỗi</strong><span>{error}</span></div>}
          {pendingConfirm && !loading && (
            <section className="algebra-confirm-panel" role="dialog" aria-labelledby="algebra-confirm-title">
              <div className="algebra-panel-heading">
                <span>Xác nhận trước khi giải</span>
                <h2 id="algebra-confirm-title">Cách hệ thống sẽ hiểu đề</h2>
              </div>
              <p className="algebra-confirm-lead">
                Kiểm tra topic, miền, biến, đơn vị góc và khoảng. AI (nếu bật) chỉ diễn giải ngôn ngữ — không được đè lựa chọn explicit của bạn.
              </p>
              <dl className="algebra-interpretation-grid">
                <div>
                  <dt>Đề gửi</dt>
                  <dd><code>{payloadInput}</code></dd>
                </div>
                <div>
                  <dt>Dạng bài</dt>
                  <dd>{payloadTopic}{inferredTopic && inferredTopic !== topic ? ' (đã gợi ý từ đề)' : ''}</dd>
                </div>
                <div>
                  <dt>Miền</dt>
                  <dd>{domain}</dd>
                </div>
                <div>
                  <dt>Biến</dt>
                  <dd>{variableList.length ? variableList.join(', ') : 'tự nhận diện'}</dd>
                </div>
                <div>
                  <dt>Đơn vị góc</dt>
                  <dd>{angleUnit === 'degree' ? 'độ (°)' : 'radian'}</dd>
                </div>
                <div>
                  <dt>Khoảng</dt>
                  <dd>{intervalSummary(intervalPayload)}</dd>
                </div>
                <div>
                  <dt>AI extraction</dt>
                  <dd>{inputMode === 'natural' && useAiExtraction && !sequenceInput ? 'bật (cần đăng nhập)' : 'tắt — rule-based'}</dd>
                </div>
              </dl>
              <div className="algebra-confirm-actions">
                <button type="button" className="algebra-action-btn" onClick={() => setPendingConfirm(false)}>
                  Sửa lại
                </button>
                <button type="button" className="auth-primary-button" onClick={() => void runSolve()}>
                  Xác nhận &amp; giải
                </button>
              </div>
            </section>
          )}
          {loading ? (
            <AlgebraLoadingResult />
          ) : result && !pendingConfirm ? (
            <AlgebraResult
              result={result}
              stale={resultStale}
              onApplyCanonical={handleApplyCanonical}
            />
          ) : !pendingConfirm ? (
            <EmptyAlgebraResult />
          ) : null}
        </div>
      </div>
    </section>
  );
}

function sequenceInputFromDraft(draft: SequenceDraft) {
  if (!draft.u1.trim() || !draft.n.trim()) return '';
  if (draft.kind === 'arithmetic') {
    if (!draft.d.trim()) return '';
    return `${draft.target === 'sum' ? 'arithmetic_sum' : 'arithmetic'}(u1=${draft.u1.trim()},d=${draft.d.trim()},n=${draft.n.trim()})`;
  }
  if (!draft.q.trim()) return '';
  return `${draft.target === 'sum' ? 'geometric_sum' : 'geometric'}(u1=${draft.u1.trim()},q=${draft.q.trim()},n=${draft.n.trim()})`;
}

function buildIntervalPayload(state: {
  intervalPreset: IntervalPreset;
  intervalStart: string;
  intervalEnd: string;
  intervalClosedStart: boolean;
  intervalClosedEnd: boolean;
  angleUnit: AlgebraAngleUnit;
}): AlgebraInterval | null {
  if (state.intervalPreset === '') return null;
  if (state.intervalPreset === 'unit_circle') {
    if (state.angleUnit === 'degree') {
      return { variable: 'x', start: '0', end: '360', closed_start: true, closed_end: false };
    }
    return { variable: 'x', start: '0', end: '2*pi', closed_start: true, closed_end: false };
  }
  const start = state.intervalStart.trim();
  const end = state.intervalEnd.trim();
  if (!start && !end) return null;
  return {
    variable: 'x',
    start: start || null,
    end: end || null,
    closed_start: state.intervalClosedStart,
    closed_end: state.intervalClosedEnd,
  };
}

function intervalSummary(interval: AlgebraInterval | null): string {
  if (!interval) return 'không giới hạn (miền đầy đủ)';
  const left = interval.closed_start === false ? '(' : '[';
  const right = interval.closed_end === false ? ')' : ']';
  return `${left}${interval.start ?? '-∞'}, ${interval.end ?? '+∞'}${right}`;
}

function fingerprintRequest(state: {
  input: string;
  inputMode: AlgebraInputMode;
  inputFormat: AlgebraInputFormat;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  useAiExtraction: boolean;
  angleUnit: AlgebraAngleUnit;
  intervalPreset: IntervalPreset;
  intervalStart: string;
  intervalEnd: string;
  intervalClosedStart: boolean;
  intervalClosedEnd: boolean;
  sequenceDraft: SequenceDraft;
}) {
  return JSON.stringify({
    input: state.input.trim(),
    inputMode: state.inputMode,
    inputFormat: state.inputFormat,
    topic: state.topic,
    domain: state.domain,
    variables: state.variables,
    useAiExtraction: state.useAiExtraction,
    angleUnit: state.angleUnit,
    intervalPreset: state.intervalPreset,
    intervalStart: state.intervalStart,
    intervalEnd: state.intervalEnd,
    intervalClosedStart: state.intervalClosedStart,
    intervalClosedEnd: state.intervalClosedEnd,
    sequenceDraft: state.sequenceDraft,
  });
}
