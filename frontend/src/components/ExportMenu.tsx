import { useState } from 'react';

import { exportScene, type ExportFormat, type ExportViewCapture } from '../api/client';
import { committedSceneRefV3, downstreamGateMessageV3 } from '../hooks/sceneWorkspaceV3State';
import type { SceneWorkspaceResponseV3 } from '../types/sceneV3';
import type { ThreeSceneImageCapture } from './ThreeGeometryView';

export interface ExportMenuProps {
  workspace: SceneWorkspaceResponseV3;
  onError?: (message: string) => void;
  captureCurrentView?: ThreeSceneImageCapture | null;
  preferCurrentViewCapture?: boolean;
}

interface ExportMenuItemsProps extends ExportMenuProps {
  itemClassName?: string;
  onAfterDownload?: () => void;
  menuRole?: boolean;
}

const EXPORT_FORMATS: ExportFormat[] = ['png', 'jpg', 'svg', 'katex-html', 'tikz', 'pdf', 'ggb'];

const FORMAT_LABELS: Record<ExportFormat, { label: string; hint: string }> = {
  png: { label: 'Xuất PNG (.png)', hint: 'Ảnh raster, dùng nhanh trong tài liệu' },
  jpg: { label: 'Xuất JPG (.jpg)', hint: 'Ảnh nền trắng, dung lượng nhẹ' },
  svg: { label: 'Xuất SVG (.svg)', hint: 'Vector, phóng to không vỡ' },
  'katex-html': { label: 'Xuất HTML KaTeX (.html)', hint: 'Trang HTML chứa hình và công thức' },
  tikz: { label: 'Xuất TikZ (.tex)', hint: 'Chèn vào Word hoặc Overleaf' },
  pdf: { label: 'Xuất PDF (.pdf)', hint: 'File PDF để in hoặc chia sẻ' },
  ggb: { label: 'Xuất GeoGebra (.ggb)', hint: 'Mở và chỉnh sửa tiếp trong GeoGebra' },
};

export function ExportMenuItems({
  workspace,
  onError,
  captureCurrentView,
  preferCurrentViewCapture = false,
  itemClassName = 'export-menu-item',
  onAfterDownload,
  menuRole = false,
}: ExportMenuItemsProps): JSX.Element {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const gateMessage = downstreamGateMessageV3(workspace, 'xuất file');
  const captureUnavailable = preferCurrentViewCapture && typeof captureCurrentView !== 'function';

  async function handleDownload(format: ExportFormat) {
    if (busy || gateMessage || captureUnavailable) return;
    setBusy(format);
    try {
      const scene = workspace.scene;
      const viewCapture = preferCurrentViewCapture && captureCurrentView
        ? await capturePayload(captureCurrentView)
        : undefined;
      const { blob, filename } = await exportScene(
        format,
        committedSceneRefV3(workspace),
        scene,
        viewCapture,
      );
      downloadBlob(blob, filename);
      onAfterDownload?.();
    } catch (caught) {
      onError?.(caught instanceof Error ? caught.message : 'Lỗi không xác định');
    } finally {
      setBusy(null);
    }
  }

  const lockMessage = gateMessage || (captureUnavailable ? 'Chưa sẵn sàng chụp góc nhìn hiện tại.' : null);
  return (
    <>
      {lockMessage && <div className="export-menu-warning" role="note">{lockMessage}</div>}
      {EXPORT_FORMATS.map((format) => {
        const labels = FORMAT_LABELS[format];
        const disabled = busy !== null || Boolean(lockMessage);
        return (
          <button
            key={format}
            type="button"
            role={menuRole ? 'menuitem' : undefined}
            className={`${itemClassName}${disabled ? ' is-locked' : ''}`}
            disabled={disabled}
            title={lockMessage ?? labels.hint}
            onClick={() => void handleDownload(format)}
          >
            <ExportFormatIcon />
            <span><strong>{busy === format ? 'Đang tải…' : labels.label}</strong><small>{labels.hint}</small></span>
          </button>
        );
      })}
    </>
  );
}

async function capturePayload(capture: ThreeSceneImageCapture): Promise<ExportViewCapture> {
  const blob = await capture('image/png');
  const dataUrl = await blobToDataUrl(blob);
  const size = await imageSizeFromDataUrl(dataUrl);
  return { mime_type: 'image/png', data_url: dataUrl, ...size };
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
    const image = new Image();
    image.onload = () => resolve({ width: image.naturalWidth || 1280, height: image.naturalHeight || 720 });
    image.onerror = () => reject(new Error('Không đọc được kích thước ảnh góc nhìn hiện tại.'));
    image.src = dataUrl;
  });
}

export function ExportMenu(props: ExportMenuProps): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <div className="export-menu">
      <button type="button" className="export-menu-trigger" onClick={() => setOpen((value) => !value)} aria-haspopup="menu" aria-expanded={open}>Xuất hình</button>
      {open && (
        <div className="export-menu-dropdown" role="menu">
          <ExportMenuItems {...props} onAfterDownload={() => setOpen(false)} menuRole />
        </div>
      )}
    </div>
  );
}

function ExportFormatIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /><path d="M14 3v5h5M9 15h6M9 18h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

export default ExportMenu;