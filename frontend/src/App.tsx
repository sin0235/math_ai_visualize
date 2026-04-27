import { useState } from 'react';

import { renderProblem } from './api/client';
import { ProblemInput } from './components/ProblemInput';
import { RendererPanel } from './components/RendererPanel';
import { SceneJsonPanel } from './components/SceneJsonPanel';
import type { RenderResponse } from './types/scene';
import './styles.css';

export default function App() {
  const [result, setResult] = useState<RenderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(problemText: string, preferredAiProvider?: string) {
    setLoading(true);
    setError(null);
    try {
      setResult(await renderProblem(problemText, preferredAiProvider));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Có lỗi không xác định.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">AI Math Renderer</p>
          <h1>Dựng hình từ đề bài</h1>
          <p>Nhập đề dạng văn bản để sinh scene JSON rồi render bằng GeoGebra hoặc Three.js.</p>
        </div>
      </header>

      <section className="workspace">
        <ProblemInput loading={loading} onSubmit={handleSubmit} />
        <div className="result-area">
          {error && <div className="error-box">{error}</div>}
          {result?.warnings.map((warning) => <div className="warning-box" key={warning}>{warning}</div>)}
          <RendererPanel result={result} />
          <SceneJsonPanel result={result} />
        </div>
      </section>
    </main>
  );
}
