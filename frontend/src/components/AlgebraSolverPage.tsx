import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ApiError,
  deleteAlgebraHistory,
  getAlgebraHistory,
  listAlgebraHistory,
  solveAlgebra,
  type AlgebraDomainSource,
  type AlgebraHistoryItem as ServerHistoryItem,
  type AlgebraInputFormat,
  type AlgebraInterval,
  type AlgebraSolveResponse,
  type AlgebraTopic,
} from '../api/client';
import { AlgebraInput, suggestTopic, type AlgebraAngleUnit, type AlgebraInputMode, type SequenceDraft } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';
import { KatexSpan, MixedTextRenderer } from './KatexSpan';
import {
  clearAlgebraHistory,
  loadAlgebraHistory,
  saveAlgebraHistoryItem,
  type AlgebraHistoryItem,
} from './algebra-solver/algebraHistory';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
const DOMAIN_TEX: Record<AlgebraDomain, string> = {
  R: String.raw`\mathbb{R}`,
  C: String.raw`\mathbb{C}`,
  N: String.raw`\mathbb{N}`,
  Z: String.raw`\mathbb{Z}`,
};
export type IntervalPreset = '' | 'unit_circle' | 'custom';

export function AlgebraSolverPage() {
  const [input, setInput] = useState('');
  const [inputMode, setInputMode] = useState<AlgebraInputMode>('natural');
  const [inputFormat, setInputFormat] = useState<AlgebraInputFormat>('auto');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [domainSource, setDomainSource] = useState<AlgebraDomainSource>('default');
  const [variables, setVariables] = useState('');
  const [useAiExtraction, setUseAiExtraction] = useState(false);
  const [angleUnit, setAngleUnit] = useState<AlgebraAngleUnit>('radian');
  const [intervalPreset, setIntervalPreset] = useState<IntervalPreset>('');
  const [intervalStart, setIntervalStart] = useState('0');
  const [intervalEnd, setIntervalEnd] = useState('2*pi');
  const [intervalClosedStart, setIntervalClosedStart] = useState(true);
  const [intervalClosedEnd, setIntervalClosedEnd] = useState(false);
  const [result, setResult] = useState<AlgebraSolveResponse | null>(null);
  const [solvedFingerprint, setSolvedFingerprint] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [localHistory, setLocalHistory] = useState<AlgebraHistoryItem[]>(() => loadAlgebraHistory());
  const [serverHistory, setServerHistory] = useState<ServerHistoryItem[]>([]);
  const [historySource, setHistorySource] = useState<'local' | 'server'>('local');
  const submitLockRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const [sequenceDraft, setSequenceDraft] = useState<SequenceDraft>({
    kind: 'arithmetic',
    target: 'term',
    u1: '2',
    d: '3',
    q: '2',
    n: '10',
  });

  useEffect(() => {
    void (async () => {
      try {
        const items = await listAlgebraHistory({ limit: 20 });
        setServerHistory(items);
        setHistorySource('server');
      } catch {
        setHistorySource('local');
      }
    })();
  }, []);

  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - started) / 1000));
    }, 500);
    return () => window.clearInterval(timer);
  }, [loading]);

  const currentFingerprint = useMemo(
    () => fingerprintRequest({
      input, inputMode, inputFormat, topic, domain, domainSource, variables, useAiExtraction, angleUnit,
      intervalPreset, intervalStart, intervalEnd, intervalClosedStart, intervalClosedEnd, sequenceDraft,
    }),
    [input, inputMode, inputFormat, topic, domain, domainSource, variables, useAiExtraction, angleUnit, intervalPreset, intervalStart, intervalEnd, intervalClosedStart, intervalClosedEnd, sequenceDraft],
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
    if (inputMode === 'math' && !useAiExtraction && !sequenceInput) {
      void runSolve();
      return;
    }
    setPendingConfirm(true);
    setError('');
  }

  function cancelSolve() {
    abortRef.current?.abort();
    abortRef.current = null;
  }

  async function runSolve() {
    if (!payloadInput || loading || submitLockRef.current) return;
    submitLockRef.current = true;
    setPendingConfirm(false);
    setLoading(true);
    setError('');
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await solveAlgebra({
        input: payloadInput,
        input_format: sequenceInput ? 'structured' : inputFormat,
        topic: payloadTopic,
        domain,
        domain_source: domainSource,
        variables: variableList,
        angle_unit: angleUnit,
        interval: intervalPayload,
        save_history: true,
        options: {
          use_ai_extraction: inputMode === 'natural' && useAiExtraction && !sequenceInput,
        },
      }, { signal: controller.signal });
      setResult(response);
      setSolvedFingerprint(currentFingerprint);
      setLocalHistory(saveAlgebraHistoryItem(response));
      if (historySource === 'server') {
        try {
          setServerHistory(await listAlgebraHistory({ limit: 20 }));
        } catch {
          // keep local
        }
      }
    } catch (caught) {
      if (caught instanceof ApiError && caught.message.includes('hủy')) {
        setError(caught.message);
      } else {
        setResult(null);
        setSolvedFingerprint('');
        if (caught instanceof ApiError) setError(caught.message);
        else setError(caught instanceof Error ? caught.message : 'Không thể giải bài đại số.');
      }
    } finally {
      setLoading(false);
      submitLockRef.current = false;
      abortRef.current = null;
    }
  }

  function handleApplyCanonical(canonical: string) {
    setInput(canonical);
    setInputMode('math');
    setInputFormat('plain');
    setUseAiExtraction(false);
    setPendingConfirm(false);
  }

  function handleDomainChange(value: AlgebraDomain) {
    setDomain(value);
    setDomainSource('user');
    setPendingConfirm(false);
  }

  function restoreLocalHistoryItem(item: AlgebraHistoryItem) {
    setInput(item.input);
    setInputMode('math');
    setInputFormat('plain');
    setUseAiExtraction(false);
    setPendingConfirm(false);
    setError('');
  }

  async function restoreServerHistoryItem(item: ServerHistoryItem) {
    try {
      const detail = await getAlgebraHistory(item.id);
      if (detail.response) {
        setResult(detail.response);
        setSolvedFingerprint('');
      }
      setInput(detail.problem_preview || item.problem_preview);
      setInputMode('math');
      setInputFormat('plain');
      setPendingConfirm(false);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được lịch sử.');
    }
  }

  return (
    <section className="algebra-solver-page">
      <header className="algebra-page-header">
        <div>
          <p className="algebra-page-kicker">Không gian giải toán</p>
          <h1>Bộ giải đại số</h1>
          <p>Nhập đề bằng tiếng Việt hoặc công thức, kiểm tra cách hiểu rồi theo dõi lời giải từng bước.</p>
        </div>
        <div className="algebra-page-meta" aria-label="Khả năng bộ giải">
          <span>MathQuill để nhập</span>
          <span>KaTeX để đọc</span>
          <span>Kiểm chứng kết quả</span>
        </div>
      </header>
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
          onDomainChange={handleDomainChange}
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
          {(historySource === 'server' ? serverHistory.length > 0 : localHistory.length > 0) && (
            <section className="algebra-history-panel" aria-label="Lịch sử bài gần đây">
              <div className="algebra-history-head">
                <strong>
                  {historySource === 'server' ? 'Lịch sử tài khoản' : 'Lịch sử máy này'}
                </strong>
                <button
                  type="button"
                  className="algebra-action-btn"
                  onClick={() => {
                    if (historySource === 'server') {
                      setServerHistory([]);
                    } else {
                      clearAlgebraHistory();
                      setLocalHistory([]);
                    }
                  }}
                >
                  Ẩn
                </button>
              </div>
              <ul className="algebra-history-list">
                {historySource === 'server'
                  ? serverHistory.slice(0, 8).map((item) => (
                    <li key={item.id}>
                      <button type="button" className="algebra-history-item" onClick={() => void restoreServerHistoryItem(item)}>
                        <span className="algebra-history-meta">{item.topic} · {item.status}</span>
                        <span className="algebra-history-input">{item.problem_preview}</span>
                      </button>
                      <button
                        type="button"
                        className="algebra-action-btn"
                        onClick={() => {
                          void deleteAlgebraHistory(item.id).then(async () => {
                            setServerHistory(await listAlgebraHistory({ limit: 20 }));
                          }).catch(() => undefined);
                        }}
                      >
                        Xóa
                      </button>
                    </li>
                  ))
                  : localHistory.slice(0, 8).map((item) => (
                    <li key={item.id}>
                      <button type="button" className="algebra-history-item" onClick={() => restoreLocalHistoryItem(item)}>
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
                Kiểm tra topic, miền, biến, đơn vị góc và khoảng.
                {domainSource === 'default' ? ' Miền R đang là mặc định — đổi nếu bài số phức.' : ' Miền do bạn chọn (sticky).'}
              </p>
              <dl className="algebra-interpretation-grid">
                <div>
                  <dt>Đề gửi</dt>
                  <dd>
                    {inputMode === 'math' || inputFormat === 'latex'
                      ? <KatexSpan tex={payloadInput} />
                      : <code>{payloadInput}</code>}
                  </dd>
                </div>
                <div>
                  <dt>Dạng bài</dt>
                  <dd>{payloadTopic}</dd>
                </div>
                <div>
                  <dt>Miền</dt>
                  <dd><KatexSpan tex={DOMAIN_TEX[domain]} /> <span className="algebra-domain-source">{domainSource === 'user' ? 'do bạn chọn' : 'mặc định'}</span></dd>
                </div>
                <div>
                  <dt>Biến</dt>
                  <dd>{variableList.length ? variableList.join(', ') : 'tự nhận diện'}</dd>
                </div>
                <div>
                  <dt>Đơn vị góc</dt>
                  <dd>{angleUnit === 'degree' ? <KatexSpan tex="{}^\\circ" /> : 'radian'}</dd>
                </div>
                <div>
                  <dt>Khoảng</dt>
                  <dd><MixedTextRenderer text={intervalSummary(intervalPayload)} /></dd>
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
            <AlgebraLoadingResult elapsedSeconds={elapsedSeconds} onCancel={cancelSolve} />
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
  const start = intervalBoundTex(interval.start, '-\\infty');
  const end = intervalBoundTex(interval.end, '+\\infty');
  return `$${left}${start},${end}${right}$`;
}

function intervalBoundTex(value: string | number | null | undefined, fallback: string) {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value)
    .replace(/\bpi\b/g, '\\pi')
    .replace(/\boo\b/g, '\\infty')
    .replace(/\*/g, '\\cdot ');
}

function fingerprintRequest(state: {
  input: string;
  inputMode: AlgebraInputMode;
  inputFormat: AlgebraInputFormat;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  domainSource: AlgebraDomainSource;
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
    domainSource: state.domainSource,
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
