import type { RenderResponse } from '../types/scene';

interface SceneJsonPanelProps {
  result: RenderResponse | null;
}

export function SceneJsonPanel({ result }: SceneJsonPanelProps) {
  return (
    <section className="panel json-panel">
      <div className="panel-title">Scene JSON</div>
      <pre>{result ? JSON.stringify(result, null, 2) : 'Chưa có dữ liệu.'}</pre>
    </section>
  );
}
