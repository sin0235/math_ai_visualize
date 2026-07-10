import { useMemo, useRef, useState } from 'react';
import { ApiError, solveAlgebra, type AlgebraInputFormat, type AlgebraSolveResponse, type AlgebraTopic } from '../api/client';
import { AlgebraInput, suggestTopic, type AlgebraInputMode, type SequenceDraft } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';

export function AlgebraSolverPage() {
  const [input, setInput] = useState('');
  const [inputMode, setInputMode] = useState<AlgebraInputMode>('natural');
  const [inputFormat, setInputFormat] = useState<AlgebraInputFormat>('auto');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [variables, setVariables] = useState('');
  const [useAiExtraction, setUseAiExtraction] = useState(false);
  /** empty = full R; unit_circle = [0, 2π) */
  const [intervalPreset, setIntervalPreset] = useState<'' | 'unit_circle'>('');
  const [result, setResult] = useState<AlgebraSolveResponse | null>(null);
  const [solvedFingerprint, setSolvedFingerprint] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
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
    () => fingerprintRequest({ input, inputMode, inputFormat, topic, domain, variables, useAiExtraction, intervalPreset, sequenceDraft }),
    [input, inputMode, inputFormat, topic, domain, variables, useAiExtraction, intervalPreset, sequenceDraft],
  );
  const resultStale = Boolean(result && solvedFingerprint && currentFingerprint !== solvedFingerprint);

  async function handleSubmit() {
    const cleanInput = input.trim();
    const sequenceInput = topic === 'sequence' ? sequenceInputFromDraft(sequenceDraft) : '';
    const payloadInput = sequenceInput || cleanInput;
    if (!payloadInput || loading || submitLockRef.current) return;
    submitLockRef.current = true;
    const inferredTopic = sequenceInput ? 'sequence' : suggestTopic(cleanInput);
    const payloadTopic = inferredTopic && inferredTopic !== topic ? inferredTopic : topic;
    setLoading(true);
    setError('');
    try {
      const response = await solveAlgebra({
        input: payloadInput,
        input_format: sequenceInput ? 'structured' : inputFormat,
        topic: payloadTopic,
        domain,
        variables: variables.split(',').map((item) => item.trim()).filter(Boolean),
        interval: intervalPreset === 'unit_circle'
          ? { variable: 'x', start: '0', end: '2*pi', closed_start: true, closed_end: false }
          : null,
        options: {
          // Natural mode defaults to rule-based; AI only when user opts in.
          use_ai_extraction: inputMode === 'natural' && useAiExtraction && !sequenceInput,
        },
      });
      setResult(response);
      setSolvedFingerprint(currentFingerprint);
    } catch (caught) {
      // Do not leave a prior successful answer looking "current" after 504/429/errors.
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
          intervalPreset={intervalPreset}
          loading={loading}
          onInputChange={setInput}
          onInputFormatChange={setInputFormat}
          onInputModeChange={setInputMode}
          onTopicChange={setTopic}
          onDomainChange={setDomain}
          onVariablesChange={setVariables}
          onUseAiExtractionChange={setUseAiExtraction}
          onIntervalPresetChange={setIntervalPreset}
          sequenceDraft={sequenceDraft}
          onSequenceDraftChange={setSequenceDraft}
          onSubmit={handleSubmit}
        />
        <div className="algebra-result-wrap">
          {error && <div className="sp-error"><strong>Solver lỗi</strong><span>{error}</span></div>}
          {loading ? (
            <AlgebraLoadingResult />
          ) : result ? (
            <AlgebraResult
              result={result}
              stale={resultStale}
              onApplyCanonical={handleApplyCanonical}
            />
          ) : (
            <EmptyAlgebraResult />
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

function fingerprintRequest(state: {
  input: string;
  inputMode: AlgebraInputMode;
  inputFormat: AlgebraInputFormat;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  useAiExtraction: boolean;
  intervalPreset: '' | 'unit_circle';
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
    intervalPreset: state.intervalPreset,
    sequenceDraft: state.sequenceDraft,
  });
}
