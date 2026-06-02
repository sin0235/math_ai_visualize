import { useState } from 'react';
import { ApiError, solveAlgebra, type AlgebraInputFormat, type AlgebraSolveResponse, type AlgebraTopic } from '../api/client';
import { AlgebraInput, type AlgebraInputMode, type SequenceDraft } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';

export function AlgebraSolverPage() {
  const [input, setInput] = useState('Giải phương trình x bình phương - 5x + 6 bằng 0');
  const [inputMode, setInputMode] = useState<AlgebraInputMode>('natural');
  const [inputFormat, setInputFormat] = useState<AlgebraInputFormat>('auto');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [variables, setVariables] = useState('x');
  const [result, setResult] = useState<AlgebraSolveResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sequenceDraft, setSequenceDraft] = useState<SequenceDraft>({
    kind: 'arithmetic',
    target: 'term',
    u1: '2',
    d: '3',
    q: '2',
    n: '10',
  });

  async function handleSubmit() {
    const cleanInput = input.trim();
    const sequenceInput = topic === 'sequence' ? sequenceInputFromDraft(sequenceDraft) : '';
    const payloadInput = sequenceInput || cleanInput;
    if (!payloadInput || loading) return;
    setLoading(true);
    setError('');
    try {
      const response = await solveAlgebra({
        input: payloadInput,
        input_format: sequenceInput ? 'structured' : inputFormat,
        topic,
        domain,
        variables: variables.split(',').map((item) => item.trim()).filter(Boolean),
      });
      setResult(response);
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught.message);
      else setError(caught instanceof Error ? caught.message : 'Không thể giải bài đại số.');
    } finally {
      setLoading(false);
    }
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
          loading={loading}
          onInputChange={setInput}
          onInputFormatChange={setInputFormat}
          onInputModeChange={setInputMode}
          onTopicChange={setTopic}
          onDomainChange={setDomain}
          onVariablesChange={setVariables}
          sequenceDraft={sequenceDraft}
          onSequenceDraftChange={setSequenceDraft}
          onSubmit={handleSubmit}
        />
        <div className="algebra-result-wrap">
          {error && <div className="sp-error"><strong>Solver lỗi</strong><span>{error}</span></div>}
          {loading ? <AlgebraLoadingResult /> : result ? <AlgebraResult result={result} /> : <EmptyAlgebraResult />}
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
