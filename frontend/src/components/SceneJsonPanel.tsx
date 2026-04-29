import type { RenderResponse } from '../types/scene';

interface SceneJsonPanelProps {
  result: RenderResponse | null;
}

export function SceneJsonPanel({ result }: SceneJsonPanelProps) {
  const json = result ? JSON.stringify(result, null, 2) : 'Chưa có dữ liệu. Hãy nhập đề bài và nhấn "Dựng hình".';

  function copyJson() {
    if (!result) return;
    void navigator.clipboard.writeText(JSON.stringify(result, null, 2));
  }

  function downloadJson() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'scene.json';
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <details className="panel json-panel">
      <summary>Chi tiết kỹ thuật: Scene JSON</summary>
      {result && (
        <div className="json-actions">
          <button type="button" className="secondary-button" onClick={copyJson}>Sao chép JSON</button>
          <button type="button" className="secondary-button" onClick={downloadJson}>Tải JSON</button>
        </div>
      )}
      <pre>{json}</pre>
    </details>
  );
}
