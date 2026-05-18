import { useRef, useState } from 'react';
import { EXAMPLE_GROUPS } from './constants';
import { SvgIcon } from './icons';

interface AnalyzerInputProps {
  expression: string;
  loading: boolean;
  ocrLoading: boolean;
  error: string | null;
  onExpressionChange: (value: string) => void;
  onAnalyze: () => void;
  onImageChange: (file?: File) => void | Promise<void>;
  onOpenGuide?: () => void;
}

export function AnalyzerInput({ expression, loading, ocrLoading, error, onExpressionChange, onAnalyze, onImageChange, onOpenGuide }: AnalyzerInputProps) {
  const [showAdvancedControls, setShowAdvancedControls] = useState(true);
  const [isDraggingImage, setIsDraggingImage] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleImageButtonClick() {
    if (loading || ocrLoading) return;
    const canReadClipboard = typeof navigator !== 'undefined' && !!navigator.clipboard?.read;
    if (!canReadClipboard) {
      fileInputRef.current?.click();
      return;
    }
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageType) continue;
        const blob = await item.getType(imageType);
        const file = new File([blob], 'clipboard-image.png', { type: imageType });
        await onImageChange(file);
        return;
      }
      fileInputRef.current?.click();
    } catch {
      fileInputRef.current?.click();
    }
  }

  function imageFileFromDataTransfer(dataTransfer: DataTransfer) {
    return Array.from(dataTransfer.files).find((file) => file.type.startsWith('image/'));
  }

  function handleImageDragOver(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!loading && !ocrLoading) setIsDraggingImage(true);
  }

  function handleImageDragLeave(event: React.DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDraggingImage(false);
  }

  function handleImageDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDraggingImage(false);
    if (loading || ocrLoading) return;
    void onImageChange(imageFileFromDataTransfer(event.dataTransfer));
  }

  async function handleFileChange(file?: File) {
    await onImageChange(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  return (
    <aside className="fa2-control-panel">
      <div className="fa2-sticky-controls">
        <div className="fa2-header">
          <div className="fa2-header-icon" aria-hidden="true"><SvgIcon name="wave" /></div>
          <div>
            <div className="fa2-header-title">Khảo sát hàm số</div>
            <div className="fa2-header-sub">Nhập hàm, xem đồ thị, đạo hàm, cực trị và tiệm cận</div>
          </div>
        </div>

        <div className="fa2-control-card fa2-formula-card">
          <div className="fa2-control-card-head">
            <span>Nhập công thức</span>
            <button
              type="button"
              className="fa2-guide-btn fa2-guide-btn-link"
              aria-label="Hướng dẫn nhập hàm"
              data-guide-hover="Xem chi tiết cách gõ công thức"
              onClick={() => onOpenGuide?.()}
              disabled={loading || ocrLoading}
            >
              <SvgIcon name="hint" />
            </button>
          </div>
          <div className="fa2-formula-row-control">
            <div className="fa2-input-wrap">
              <span className="fa2-prefix">y =</span>
              <input
                id="fa-expression-input"
                className="fa2-input"
                type="text"
                placeholder="x^3 - 3*x + 2"
                value={expression}
                onChange={(e) => onExpressionChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') onAnalyze(); }}
                onMouseDown={(e) => {
                  if (e.button === 2) e.preventDefault();
                }}
                onContextMenu={(e) => {
                  if (loading || ocrLoading) return;
                  e.preventDefault();
                  e.currentTarget.blur();
                  void handleImageButtonClick();
                }}
                disabled={loading || ocrLoading}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <button id="fa-submit-btn" type="button" className="sp-btn-primary" onClick={onAnalyze} disabled={loading || ocrLoading || !expression.trim()}>
              {loading ? <span className="sp-spinner" aria-hidden="true" /> : 'Phân tích'}
            </button>
          </div>
          <button type="button" className="fa2-advanced-toggle" onClick={() => setShowAdvancedControls((value) => !value)} aria-expanded={showAdvancedControls}>
            {showAdvancedControls ? 'Ẩn tùy chọn' : 'Hiện tùy chọn'}
            <SvgIcon name="chevron" />
          </button>
        </div>
      </div>

      {showAdvancedControls && <div className="fa2-advanced-panel">
        <div className="fa2-control-card">
          <div className="fa2-control-card-head"><span>Ví dụ nhanh</span></div>
          <div className="fa2-chip-groups">
            {EXAMPLE_GROUPS.map((group) => (
              <div key={group.label} className="fa2-chip-group">
                <div className="fa2-chip-group-title">{group.label}</div>
                <div className="sp-chips">
                  {group.items.map((ex) => <button key={ex.value} type="button" className="sp-chip" onClick={() => onExpressionChange(ex.value)}>{ex.label}</button>)}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="fa2-control-card fa2-upload-card">
          <div className="fa2-control-card-head"><span>Nhập bằng ảnh</span></div>
          <input ref={fileInputRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => void handleFileChange(e.target.files?.[0])} />
          <div
            className={`fa2-ocr-dropzone ${isDraggingImage ? 'is-dragging' : ''}`}
            onDragOver={handleImageDragOver}
            onDragLeave={handleImageDragLeave}
            onDrop={handleImageDrop}
          >
            <div className="fa2-ocr-dropzone-icon" aria-hidden="true"><SvgIcon name="upload" /></div>
            <strong>{ocrLoading ? 'Đang đọc ảnh...' : 'Kéo thả ảnh vào đây'}</strong>
            <span>Hoặc chọn tệp / dán ảnh từ clipboard để OCR công thức.</span>
            <div className="fa2-upload-actions">
              <button type="button" className="sp-btn-secondary" onClick={() => fileInputRef.current?.click()} disabled={loading || ocrLoading}>
                {ocrLoading ? <span className="sp-spinner" aria-hidden="true" /> : <SvgIcon name="attach" />} Chọn ảnh
              </button>
              <button type="button" className="sp-btn-secondary" onClick={() => void handleImageButtonClick()} disabled={loading || ocrLoading}>Dán ảnh clipboard</button>
            </div>
          </div>
        </div>
      </div>}

      {error && <div className="sp-error" role="alert">{error}</div>}
    </aside>
  );
}
