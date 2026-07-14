import { useEffect, useMemo, useRef, useState } from 'react';
import { useInterpretationPreflight } from './nlp/InterpretationPanel';
import {
  ApiError,
  consumeAnalyzerLinkFromLocation,
  deleteAlgebraHistory,
  getAlgebraHistory,
  listAlgebraHistory,
  ocrImageByUploadId,
  solveAlgebra,
  uploadOcrImage,
  type AlgebraDomainSource,
  type AlgebraHistoryItem as ServerHistoryItem,
  type AlgebraInputFormat,
  type AlgebraHandoffPayload,
  type AlgebraInterval,
  type AlgebraSolveResponse,
  type AlgebraTopic,
} from '../api/client';
import { AlgebraInput, suggestTopic, type AlgebraAngleUnit, type AlgebraInputMode, type SequenceDraft } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';
import {
  loadAlgebraHistory,
  saveAlgebraHistoryItem,
  type AlgebraHistoryItem,
} from './algebra-solver/algebraHistory';
import { isDocumentHidden, showBrowserNotify } from '../utils/browserNotify';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
export type IntervalPreset = '' | 'unit_circle' | 'custom';

type ToastKind = 'error' | 'warning' | 'info';

export function AlgebraSolverPage({
  onToast,
}: {
  onToast?: (title: string, message: string, kind?: ToastKind, details?: string[]) => void;
} = {}) {
  const [input, setInput] = useState('');
  const [inputMode, setInputMode] = useState<AlgebraInputMode>('natural');
  const [inputFormat, setInputFormat] = useState<AlgebraInputFormat>('auto');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [domainSource, setDomainSource] = useState<AlgebraDomainSource>('default');
  const [variables, setVariables] = useState('');
  const [useAiExtraction, setUseAiExtraction] = useState(true);
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
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [inputExpanded, setInputExpanded] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const preflight = useInterpretationPreflight();
  const [localHistory, setLocalHistory] = useState<AlgebraHistoryItem[]>(() => loadAlgebraHistory());
  const [serverHistory, setServerHistory] = useState<ServerHistoryItem[]>([]);
  const [historySource, setHistorySource] = useState<'local' | 'server'>('local');
  const submitLockRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const ocrInFlightRef = useRef(false);
  const DEFAULT_OCR_MAX_MB = 10;
  const [sequenceDraft, setSequenceDraft] = useState<SequenceDraft>({
    kind: 'arithmetic',
    target: 'term',
    u1: '2',
    d: '3',
    q: '2',
    n: '10',
  });

  useEffect(() => {
    void consumeAnalyzerLinkFromLocation<AlgebraHandoffPayload>('algebra_solver')
      .then((payload) => {
        if (!payload || payload.version !== 'algebra-solver-v1') return;
        setInput(payload.input);
        setInputMode('math');
        setInputFormat(payload.input_format);
        setTopic(payload.topic);
        setDomain(payload.domain);
        setDomainSource('user');
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Không mở được handoff analyzer.'));
  }, []);

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

  async function requestConfirmIfNeeded() {
    if (!payloadInput || loading || submitLockRef.current) return;
    if (!sequenceInput) {
      setError('');
      await preflight.check({
        text: payloadInput,
        target: 'algebra',
        input_mode: 'natural',
        input_format: 'auto',
        context: { topic: payloadTopic, domain, variables: variableList },
      });
    }
    await runSolve();
  }

  function cancelSolve() {
    abortRef.current?.abort();
    abortRef.current = null;
  }

  async function runSolve() {
    if (!payloadInput || loading || submitLockRef.current) return;
    submitLockRef.current = true;
    preflight.reset();
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
      setInputExpanded(false);
      setSolvedFingerprint(currentFingerprint);
      setLocalHistory(saveAlgebraHistoryItem(response));
      notifyAlgebraSideChannel(response, onToast);
      if (historySource === 'server') {
        try {
          setServerHistory(await listAlgebraHistory({ limit: 20 }));
        } catch {
          // keep local
        }
      }
    } catch (caught) {
      if (caught instanceof ApiError && caught.message.includes('hủy')) {
        setError('');
        onToast?.('Đã hủy', caught.message, 'info');
      } else {
        setResult(null);
        setSolvedFingerprint('');
        const message = caught instanceof ApiError
          ? caught.message
          : caught instanceof Error
            ? caught.message
            : 'Không thể giải bài đại số.';
        setError('');
        onToast?.('Không giải được', message, 'error');
      }
    } finally {
      setLoading(false);
      submitLockRef.current = false;
      abortRef.current = null;
    }
  }

  function handleApplyCanonical(canonical: string) {
    setInput(canonical);
    setInputMode('natural');
    setInputFormat('auto');
    setUseAiExtraction(true);
    preflight.reset();
  }

  async function handleOcrClipboardImage() {
    if (!navigator.clipboard?.read) {
      const message = 'Trình duyệt chưa hỗ trợ đọc ảnh từ clipboard.';
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
      return;
    }
    try {
      const clipboardItems = await navigator.clipboard.read();
      for (const item of clipboardItems) {
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageType) continue;
        const blob = await item.getType(imageType);
        await handleOcrImage(new File([blob], 'clipboard-image.png', { type: imageType }));
        return;
      }
      const message = 'Clipboard hiện không có ảnh để OCR.';
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Không đọc được ảnh từ clipboard.';
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
    }
  }

  async function handleOcrImage(file: File) {
    if (ocrInFlightRef.current || loading) return;
    if (!file.type.startsWith('image/')) {
      const message = 'File OCR phải là ảnh.';
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
      return;
    }
    const maxBytes = DEFAULT_OCR_MAX_MB * 1024 * 1024;
    if (file.size > maxBytes) {
      const message = `Ảnh OCR vượt quá giới hạn ${DEFAULT_OCR_MAX_MB}MB.`;
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
      return;
    }

    ocrInFlightRef.current = true;
    setOcrLoading(true);
    setOcrError(null);
    try {
      const uploaded = await uploadOcrImage(file);
      const response = await ocrImageByUploadId(uploaded.file_id);
      const text = (response.text || '').trim();
      if (!text) {
        const message = 'OCR không đọc được chữ trong ảnh. Hãy chụp rõ hơn hoặc gõ tay.';
        setOcrError(message);
        onToast?.('OCR thất bại', message, 'warning');
        return;
      }
      setInput(text);
      setInputMode('natural');
      setInputFormat('auto');
      setUseAiExtraction(true);
      preflight.reset();
      onToast?.('OCR xong', 'Đã điền đề từ ảnh. Kiểm tra rồi bấm Giải bài.', 'info');
    } catch (caught) {
      const message = caught instanceof ApiError
        ? caught.message
        : caught instanceof Error
          ? caught.message
          : 'Không thể OCR ảnh đề bài.';
      setOcrError(message);
      onToast?.('OCR thất bại', message, 'error');
    } finally {
      ocrInFlightRef.current = false;
      setOcrLoading(false);
    }
  }

  function handleDomainChange(value: AlgebraDomain) {
    setDomain(value);
    setDomainSource('user');
    preflight.reset();
  }

  function restoreLocalHistoryItem(item: AlgebraHistoryItem) {
    setInput(item.input);
    setInputMode('natural');
    setInputFormat('auto');
    setUseAiExtraction(true);
    preflight.reset();
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
      setInputMode('natural');
      setInputFormat('auto');
      setUseAiExtraction(true);
      preflight.reset();
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tải được lịch sử.');
    }
  }

  return (
    <section className="algebra-solver-page">
      <div className="algebra-workspace">
        <AlgebraInput
          input={input}
          topic={topic}
          domain={domain}
          variables={variables}
          angleUnit={angleUnit}
          intervalPreset={intervalPreset}
          intervalStart={intervalStart}
          intervalEnd={intervalEnd}
          intervalClosedStart={intervalClosedStart}
          intervalClosedEnd={intervalClosedEnd}
          loading={loading}
          ocrLoading={ocrLoading}
          ocrError={ocrError}
          expanded={inputExpanded}
          onExpandedChange={setInputExpanded}
          onInputChange={(value) => { setInput(value); setOcrError(null); preflight.reset(); }}
          onTopicChange={(value) => { setTopic(value); preflight.reset(); }}
          onDomainChange={handleDomainChange}
          onVariablesChange={(value) => { setVariables(value); preflight.reset(); }}
          onAngleUnitChange={(value) => { setAngleUnit(value); preflight.reset(); }}
          onIntervalPresetChange={(value) => { setIntervalPreset(value); preflight.reset(); }}
          onIntervalStartChange={(value) => { setIntervalStart(value); preflight.reset(); }}
          onIntervalEndChange={(value) => { setIntervalEnd(value); preflight.reset(); }}
          onIntervalClosedStartChange={(value) => { setIntervalClosedStart(value); preflight.reset(); }}
          onIntervalClosedEndChange={(value) => { setIntervalClosedEnd(value); preflight.reset(); }}
          sequenceDraft={sequenceDraft}
          onSequenceDraftChange={(value) => { setSequenceDraft(value); preflight.reset(); }}
          onOcrImage={(file) => { void handleOcrImage(file); }}
          onOcrClipboardImage={() => { void handleOcrClipboardImage(); }}
          onSubmit={requestConfirmIfNeeded}
        />
        <div className="algebra-result-wrap">
                    {loading ? (
            <AlgebraLoadingResult elapsedSeconds={elapsedSeconds} onCancel={cancelSolve} />
          ) : result ? (
            <AlgebraResult
              result={result}
              stale={resultStale}
              onApplyCanonical={handleApplyCanonical}
            />
          ) : preflight.state.phase === 'idle' ? (
            <EmptyAlgebraResult />
          ) : null}
          {(historySource === 'server' ? serverHistory.length > 0 : localHistory.length > 0) && (
            <section className="algebra-history-panel" aria-label="Lịch sử bài gần đây">
              <details className="algebra-history-disclosure">
                <summary>
                  <strong>{historySource === 'server' ? 'Lịch sử tài khoản' : 'Lịch sử máy này'}</strong>
                  <span>{historySource === 'server' ? serverHistory.length : localHistory.length} bài</span>
                </summary>
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
                          aria-label={`Xóa ${item.problem_preview} khỏi lịch sử`}
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
              </details>
            </section>
          )}
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

function notifyAlgebraSideChannel(
  result: AlgebraSolveResponse,
  onToast?: (title: string, message: string, kind?: ToastKind, details?: string[]) => void,
) {
  if (!onToast) return;
  const routine = (value: string) => (
    value.includes('Đã diễn giải đề tiếng Việt')
    || value.includes('Đầu vào gồm cả mô tả tự nhiên')
    || value.includes('Miền R đang là mặc định')
    || value.includes('rule-based')
    || value.includes('NLP:')
    || value.includes('mathcore')
  );
  const warnings = (result.warnings || []).filter((item) => item.trim() && !routine(item));
  const errors = (result.errors || []).filter((item) => item.trim());
  if (result.status === 'error' || result.status === 'unsupported') {
    onToast(
      result.status === 'unsupported' ? 'Chưa hỗ trợ dạng này' : 'Không giải được',
      result.answer || errors[0] || 'Không thể giải bài này.',
      result.status === 'unsupported' ? 'warning' : 'error',
      [...errors, ...warnings].slice(0, 5),
    );
    return;
  }
  const details = [...warnings, ...errors].slice(0, 6);
  if (details.length > 0) {
    onToast('Lưu ý khi giải', details[0], 'warning', details.slice(1));
  }
  const failedChecks = (result.verification?.checks || []).filter((check) => check.status === 'fail' || check.status === 'warn');
  if (result.verification?.status === 'failed' || failedChecks.length > 0) {
    onToast(
      'Cần rà lại kết quả',
      failedChecks[0]?.detail || 'Một số kiểm tra lời giải chưa đạt.',
      'warning',
      failedChecks.slice(0, 4).map((check) => check.detail || check.name).filter(Boolean),
    );
    return;
  }
  // Clean solved: OS notify only when tab is hidden.
  if (result.status === 'solved' && (result.steps?.length || 0) > 0 && details.length === 0 && isDocumentHidden()) {
    showBrowserNotify({
      title: 'Đã giải xong',
      body: (result.answer || 'Có lời giải từng bước.').slice(0, 120),
      kind: 'info',
      tag: 'solve-done',
    });
  }
}
