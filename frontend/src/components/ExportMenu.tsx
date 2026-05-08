import React, { useState } from 'react';
import { exportScene, type ExportFormat } from '../api/client';
import type { AdvancedRenderSettings, MathScene } from '../types/scene';

export interface ExportMenuProps {
  scene: MathScene;
  advancedSettings: AdvancedRenderSettings;
  onError?: (message: string) => void;
}

interface ExportMenuItemsProps extends ExportMenuProps {
  itemClassName?: string;
  onAfterDownload?: () => void;
}

const FORMAT_LABELS: Record<ExportFormat, { label: string; hint: string }> = {
  png: { label: 'Xuất PNG (.png)', hint: 'Ảnh raster, dùng nhanh trong tài liệu' },
  jpg: { label: 'Xuất JPG (.jpg)', hint: 'Ảnh nền trắng, dung lượng nhẹ' },
  svg: { label: 'Xuất SVG (.svg)', hint: 'Vector, phóng to không vỡ' },
  pdf: { label: 'Xuất PDF (A4)', hint: 'Một trang in được, gồm đề bài và hình' },
  'katex-html': { label: 'Xuất HTML KaTeX (.html)', hint: 'File HTML hiển thị công thức bằng KaTeX' },
  tikz: { label: 'Xuất TikZ (.tex)', hint: 'Chèn vào Word/Overleaf, dùng \\usepackage{tikz}' },
  ggb: { label: 'Xuất GeoGebra (.ggb)', hint: 'Mở bằng GeoGebra Classic để chỉnh sửa' },
};

const EXPORT_FORMATS: ExportFormat[] = ['png', 'jpg', 'svg', 'pdf', 'katex-html', 'tikz', 'ggb'];

export function ExportMenuItems({ scene, advancedSettings, onError, itemClassName = 'export-menu-item', onAfterDownload }: ExportMenuItemsProps): JSX.Element {
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
      onAfterDownload?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Lỗi không xác định';
      onError?.(message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {EXPORT_FORMATS.map((fmt) => (
        <button key={fmt} type="button" role="menuitem" className={itemClassName} disabled={busy !== null} onClick={() => handleDownload(fmt)}>
          <ExportFormatIcon format={fmt} />
          <span>
            <strong>{busy === fmt ? 'Đang tải…' : FORMAT_LABELS[fmt].label}</strong>
            <small>{FORMAT_LABELS[fmt].hint}</small>
          </span>
        </button>
      ))}
    </>
  );
}

export function ExportMenu({ scene, advancedSettings, onError }: ExportMenuProps): JSX.Element {
  const [open, setOpen] = useState(false);

  return (
    <div className="export-menu">
      <button type="button" className="export-menu-trigger" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}>
        Xuất hình
      </button>
      {open && (
        <div className="export-menu-dropdown" role="menu">
          <ExportMenuItems scene={scene} advancedSettings={advancedSettings} onError={onError} onAfterDownload={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}

function ExportFormatIcon({ format }: { format: ExportFormat }) {
  if (format === 'png' || format === 'jpg') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="m7 16 4-4 3 3 2-2 2 3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /><circle cx="9" cy="9" r="1.4" fill="currentColor" /></svg>;
  }
  if (format === 'svg') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14v10H5z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M8 12h8M12 8v8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
  }
  if (format === 'katex-html') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v16H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M9 9h6M9 12h4M9 15h5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
  }
  if (format === 'tikz') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 7 4 12l4 5M16 7l4 5-4 5M10 19l4-14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  }
  if (format === 'ggb') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="1.8" /><circle cx="8" cy="9" r="1.4" fill="currentColor" /><circle cx="15" cy="8" r="1.4" fill="currentColor" /><circle cx="16" cy="15" r="1.4" fill="currentColor" /><circle cx="9" cy="16" r="1.4" fill="currentColor" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M14 3v5h5M9 15h6M9 18h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

export default ExportMenu;
