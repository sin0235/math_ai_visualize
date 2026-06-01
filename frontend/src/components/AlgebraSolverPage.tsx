import { useState } from 'react';
import { ApiError, solveAlgebra, type AlgebraSolveResponse, type AlgebraTopic } from '../api/client';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
import { AlgebraInput } from './algebra-solver/AlgebraInput';
import { AlgebraLoadingResult, AlgebraResult, EmptyAlgebraResult } from './algebra-solver/AlgebraResult';

export function AlgebraSolverPage() {
  const [input, setInput] = useState('x^2 - 5*x + 6 = 0');
  const [topic, setTopic] = useState<AlgebraTopic>('auto');
  const [domain, setDomain] = useState<AlgebraDomain>('R');
  const [variables, setVariables] = useState('x');
  const [result, setResult] = useState<AlgebraSolveResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    const cleanInput = input.trim();
    if (!cleanInput || loading) return;
    setLoading(true);
    setError('');
    try {
      const response = await solveAlgebra({
        input: cleanInput,
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
          topic={topic}
          domain={domain}
          variables={variables}
          loading={loading}
          onInputChange={setInput}
          onTopicChange={setTopic}
          onDomainChange={setDomain}
          onVariablesChange={setVariables}
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
