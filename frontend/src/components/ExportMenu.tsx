import React, { useState } from 'react';
import { exportScene, type ExportFormat } from '../api/client';
import type { AdvancedRenderSettings, MathScene } from '../types/scene';

export interface ExportMenuProps {
  scene: MathScene;
  advancedSettings: AdvancedRenderSettings;
  onError?: (message: string) => void;
}

const FORMAT_LABELS: Record<ExportFormat, { label: string; hint: string }> = {
  pdf: { label: 'Xuất PDF (A4)', hint: 'Một trang in được, gồm đề bài và hình' },
  tikz: { label: 'Xuất TikZ (.tex)', hint: 'Chèn vào Word/Overleaf, dùng \\usepackage{tikz}' },
  ggb: { label: 'Xuất GeoGebra (.ggb)', hint: 'Mở bằng GeoGebra Classic để chỉnh sửa' },
};

export function ExportMenu({ scene, advancedSettings, onError }: ExportMenuProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<ExportFormat | null>(null);

  async function handleDownload(format: ExportFormat) {
    if (busy) return;
    setBusy(format);
    try {
      const { blob, filename } = await exportScene(format, scene, advancedSettings);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setOpen(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Lỗi không xác định';
      onError?.(message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="export-menu">
      <button
        type="button"
        className="export-menu-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        Xuất hình
      </button>
      {open && (
        <div className="export-menu-dropdown" role="menu">
          {(Object.keys(FORMAT_LABELS) as ExportFormat[]).map((fmt) => (
            <button
              key={fmt}
              type="button"
              role="menuitem"
              className="export-menu-item"
              disabled={busy !== null}
              onClick={() => handleDownload(fmt)}
            >
              <span className="export-menu-label">
                {busy === fmt ? 'Đang tải…' : FORMAT_LABELS[fmt].label}
              </span>
              <span className="export-menu-hint">{FORMAT_LABELS[fmt].hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default ExportMenu;
