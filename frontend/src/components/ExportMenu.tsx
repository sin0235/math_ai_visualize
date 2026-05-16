import React, { useState } from 'react';
import { exportScene, type ExportFormat } from '../api/client';
import { buildExportFilename } from '../utils/exportFilename';
import type { ThreeSceneImageCapture } from './ThreeGeometryView';
import type { AdvancedRenderSettings, MathScene } from '../types/scene';

export interface ExportMenuProps {
  scene: MathScene;
  advancedSettings: AdvancedRenderSettings;
  onError?: (message: string) => void;
  captureCurrentView?: ThreeSceneImageCapture | null;
  preferCurrentViewCapture?: boolean;
}

interface ExportMenuItemsProps extends ExportMenuProps {
  itemClassName?: string;
  onAfterDownload?: () => void;
}

const EXPORT_FORMATS: ExportFormat[] = ['png', 'jpg', 'svg', 'katex-html', 'tikz'];

function formatLabelsForContext(preferThreeView: boolean): Record<ExportFormat, { label: string; hint: string }> {
  const base = {
    png: { label: 'Xuất PNG (.png)', hint: 'Ảnh raster, dùng nhanh trong tài liệu' },
    jpg: { label: 'Xuất JPG (.jpg)', hint: 'Ảnh nền trắng, dung lượng nhẹ' },
    svg: { label: 'Xuất SVG (.svg)', hint: 'Vector, phóng to không vỡ' },
    'katex-html': { label: 'Xuất HTML KaTeX (.html)', hint: 'File HTML hiển thị công thức bằng KaTeX' },
    tikz: { label: 'Xuất TikZ (.tex)', hint: 'Chèn vào Word/Overleaf, dùng \\usepackage{tikz}' },
  } satisfies Record<ExportFormat, { label: string; hint: string }>;
  if (!preferThreeView) return base;
  return {
    ...base,
    png: { ...base.png, hint: 'Chụp đúng góc nhìn khung Three.js hiện tại.' },
    jpg: { ...base.jpg, hint: 'Chụp đúng góc nhìn khung Three.js hiện tại.' },
    svg: {
      ...base.svg,
      hint: 'Nhúng ảnh chụp đúng góc nhìn hiện tại vào file SVG.',
    },
    'katex-html': {
      label: 'Xuất HTML (.html)',
      hint: 'Nhúng ảnh chụp đúng góc nhìn hiện tại vào trang HTML.',
    },
    tikz: {
      ...base.tikz,
      hint: 'TikZ chỉ hỗ trợ phép chiếu vector cố định cho hình 3D.',
    },
  };
}

function exportLock(
  format: ExportFormat,
  captureCurrentView: ThreeSceneImageCapture | null | undefined,
  preferCurrentViewCapture: boolean,
): { locked: boolean; reason?: string } {
  if (format === 'tikz' && preferCurrentViewCapture) {
    return { locked: true, reason: 'TikZ chưa hỗ trợ giữ góc nhìn Three.js hiện tại. Hãy dùng PNG, JPG, SVG hoặc HTML.' };
  }
  if (format === 'png' || format === 'jpg' || (preferCurrentViewCapture && (format === 'svg' || format === 'katex-html'))) {
    const ready = typeof captureCurrentView === 'function';
    if (preferCurrentViewCapture && !ready) {
      return { locked: true, reason: 'Chưa sẵn sàng chụp góc nhìn — đợi hình Three.js hiển thị xong rồi thử lại.' };
    }
    return { locked: false };
  }
  return { locked: false };
}

export function ExportMenuItems({ scene, advancedSettings, onError, captureCurrentView, preferCurrentViewCapture = false, itemClassName = 'export-menu-item', onAfterDownload }: ExportMenuItemsProps): JSX.Element {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const labels = formatLabelsForContext(preferCurrentViewCapture);

  async function handleDownload(format: ExportFormat) {
    if (busy) return;
    const lock = exportLock(format, captureCurrentView, preferCurrentViewCapture);
    if (lock.locked) return;
    setBusy(format);
    try {
      const { blob, filename } = await getExportBlob(format, scene, advancedSettings, captureCurrentView, preferCurrentViewCapture);
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
      {EXPORT_FORMATS.map((fmt) => {
        const { locked: isLocked, reason: lockReason } = exportLock(fmt, captureCurrentView, preferCurrentViewCapture);
        const tooltip = isLocked ? lockReason : undefined;
        const fmtLabels = labels[fmt];
        return (
          <button
            key={fmt}
            type="button"
            role="menuitem"
            className={itemClassName}
            disabled={busy !== null || isLocked}
            aria-disabled={isLocked || undefined}
            title={tooltip}
            onClick={() => handleDownload(fmt)}
          >
            <ExportFormatIcon format={fmt} />
            <span>
              <strong>
                {busy === fmt ? 'Đang tải…' : fmtLabels.label}
                {isLocked && lockReason && <em className="export-menu-locked-tag"> ({lockReason})</em>}
              </strong>
              <small>{isLocked && lockReason ? lockReason : fmtLabels.hint}</small>
            </span>
          </button>
        );
      })}
    </>
  );
}

async function getExportBlob(format: ExportFormat, scene: MathScene, advancedSettings: AdvancedRenderSettings, captureCurrentView?: ThreeSceneImageCapture | null, preferCurrentViewCapture = false) {
  if (format === 'png' || format === 'jpg') {
    if (typeof captureCurrentView === 'function') {
      return {
        blob: await captureCurrentView(format === 'png' ? 'image/png' : 'image/jpeg'),
        filename: buildExportFilename(scene, format),
      };
    }
    if (preferCurrentViewCapture) throw new Error('Chưa thể chụp góc nhìn hiện tại. Vui lòng chờ hình tải xong rồi thử lại.');
  }

  if (preferCurrentViewCapture && typeof captureCurrentView === 'function' && (format === 'svg' || format === 'katex-html')) {
    const imageBlob = await captureCurrentView('image/png');
    const dataUrl = await blobToDataUrl(imageBlob);
    const size = await imageSizeFromDataUrl(dataUrl);
    if (format === 'svg') {
      return {
        blob: new Blob([buildCurrentViewSvg(scene, dataUrl, size)], { type: 'image/svg+xml;charset=utf-8' }),
        filename: buildExportFilename(scene, format),
      };
    }
    return {
      blob: new Blob([buildCurrentViewHtml(scene, dataUrl, size)], { type: 'text/html;charset=utf-8' }),
      filename: buildExportFilename(scene, format),
    };
  }

  return exportScene(format, scene, advancedSettings);
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error ?? new Error('Không đọc được ảnh góc nhìn hiện tại.'));
    reader.readAsDataURL(blob);
  });
}

function imageSizeFromDataUrl(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth || 1280, height: img.naturalHeight || 720 });
    img.onerror = () => reject(new Error('Không đọc được kích thước ảnh góc nhìn hiện tại.'));
    img.src = dataUrl;
  });
}

function buildCurrentViewSvg(scene: MathScene, imageHref: string, size: { width: number; height: number }) {
  const title = escapeXml(scene.problem_text || 'Hinh');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size.width}" height="${size.height}" viewBox="0 0 ${size.width} ${size.height}" role="img" aria-label="${title}">
  <title>${title}</title>
  <image href="${imageHref}" x="0" y="0" width="${size.width}" height="${size.height}" preserveAspectRatio="xMidYMid meet"/>
</svg>
`;
}

function buildCurrentViewHtml(scene: MathScene, imageSrc: string, size: { width: number; height: number }) {
  const title = escapeHtml(scene.problem_text || 'Hình');
  const topic = escapeHtml(scene.topic.replace(/_/g, ' '));
  return `<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title}</title>
  <style>
    :root { color: #111827; background: #f8fafc; font-family: Arial, sans-serif; }
    body { margin: 0; padding: 24px; }
    main { max-width: ${Math.max(720, Math.min(size.width, 1200))}px; margin: 0 auto; }
    h1 { font-size: 20px; margin: 0 0 8px; }
    p { margin: 0 0 16px; color: #475569; }
    img { width: 100%; height: auto; display: block; border: 1px solid #dbe3ef; background: #fff; }
  </style>
</head>
<body>
  <main>
    <h1>${title}</h1>
    <p>${topic} · ảnh chụp từ góc nhìn Three.js hiện tại</p>
    <img src="${imageSrc}" width="${size.width}" height="${size.height}" alt="${title}" />
  </main>
</body>
</html>
`;
}

function escapeHtml(value: string) {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeXml(value: string) {
  return escapeHtml(value).replace(/'/g, '&apos;');
}

export function ExportMenu({ scene, advancedSettings, onError, captureCurrentView, preferCurrentViewCapture }: ExportMenuProps): JSX.Element {
  const [open, setOpen] = useState(false);

  return (
    <div className="export-menu">
      <button type="button" className="export-menu-trigger" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}>
        Xuất hình
      </button>
      {open && (
        <div className="export-menu-dropdown" role="menu">
          <ExportMenuItems scene={scene} advancedSettings={advancedSettings} onError={onError} captureCurrentView={captureCurrentView} preferCurrentViewCapture={preferCurrentViewCapture} onAfterDownload={() => setOpen(false)} />
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
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M14 3v5h5M9 15h6M9 18h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

export default ExportMenu;
