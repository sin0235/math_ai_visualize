import { useRef, useState } from 'react';
import type { FunctionOcrExtraction } from '../../api/client';
import { EXAMPLE_GROUPS } from './constants';
import { SvgIcon } from './icons';

interface AnalyzerInputProps {
  expression: string;
  loading: boolean;
  ocrLoading: boolean;
  ocrCandidate: FunctionOcrExtraction | null;
  ocrPreviewUrl: string | null;
  error: string | null;
  parameterDetected: boolean;
  parameterMode: '' | 'symbolic' | 'substitute';
  parameterValue: string;
  onParameterModeChange: (value: '' | 'symbolic' | 'substitute') => void;
  onParameterValueChange: (value: string) => void;
  onExpressionChange: (value: string) => void;
  onAnalyze: () => void;
  onConfirmOcr: () => void;
  onDiscardOcr: () => void;
  onImageChange: (file?: File) => void | Promise<void>;
  onOpenGuide?: () => void;
}

export function AnalyzerInput({
  expression,
  loading,
  ocrLoading,
  ocrCandidate,
  ocrPreviewUrl,
  error,
  parameterDetected,
  parameterMode,
  parameterValue,
  onParameterModeChange,
  onParameterValueChange,
  onExpressionChange,
  onAnalyze,
  onConfirmOcr,
  onDiscardOcr,
  onImageChange,
  onOpenGuide,
}: AnalyzerInputProps) {
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
                onKeyDown={(e) => { if (e.key === 'Enter' && !ocrCandidate) onAnalyze(); }}
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
            <button id="fa-submit-btn" type="button" className="sp-btn-primary" onClick={onAnalyze} disabled={loading || ocrLoading || !!ocrCandidate || !expression.trim()}>
              {loading ? <span className="sp-spinner" aria-hidden="true" /> : ocrCandidate ? 'Xác nhận bên dưới' : 'Phân tích'}
            </button>
          </div>
          {parameterDetected && (
            <fieldset className="fa2-parameter-controls" disabled={loading || ocrLoading}>
              <legend>Tham số m</legend>
              <label>
                Chế độ phân tích
                <select
                  value={parameterMode}
                  onChange={(event) => onParameterModeChange(event.target.value as '' | 'symbolic' | 'substitute')}
                >
                  <option value="">Chọn chế độ</option>
                  <option value="symbolic">Phân tích symbolic theo case</option>
                  <option value="substitute">Thay giá trị exact</option>
                </select>
              </label>
              {parameterMode === 'substitute' && (
                <div className="fa2-parameter-value-controls">
                  <label>
                    Giá trị exact của m
                    <input
                      type="text"
                      value={parameterValue}
                      onChange={(event) => onParameterValueChange(event.target.value)}
                      placeholder="1/2, pi, sqrt(2), 20"
                      autoComplete="off"
                      spellCheck={false}
                    />
                  </label>
                  <label>
                    Slider gợi ý từ -10 đến 10
                    <input
                      type="range"
                      min="-10"
                      max="10"
                      step="0.1"
                      value={suggestedParameterValue(parameterValue)}
                      onChange={(event) => onParameterValueChange(event.target.value)}
                    />
                  </label>
                  <small>Slider chỉ gợi ý; giá trị exact nhập tay không bị giới hạn.</small>
                </div>
              )}
            </fieldset>
          )}
          <button type="button" className="fa2-advanced-toggle" onClick={() => setShowAdvancedControls((value) => !value)} aria-expanded={showAdvancedControls}>
            {showAdvancedControls ? 'Ẩn tùy chọn' : 'Hiện tùy chọn'}
            <SvgIcon name="chevron" />
          </button>
        </div>
        {ocrCandidate && (
          <section className="fa2-ocr-review" aria-labelledby="fa2-ocr-review-title">
            <div className="fa2-ocr-review-head">
              <strong id="fa2-ocr-review-title">Kiểm tra kết quả OCR</strong>
              <span>{ocrCandidate.needs_confirmation ? 'Cần xác nhận' : 'Sẵn sàng xác nhận'}</span>
            </div>
            {ocrPreviewUrl && <img src={ocrPreviewUrl} alt="Ảnh công thức đang được kiểm tra" />}
            <label className="fa2-ocr-confidence">
              Độ tin cậy {Math.round(ocrCandidate.confidence * 100)}%
              <progress max="1" value={ocrCandidate.confidence} />
            </label>
            <p>Sửa biểu thức trong ô <strong>y =</strong> phía trên nếu OCR nhận sai.</p>
            {ocrCandidate.ambiguous_tokens.length > 0 && (
              <div className="fa2-ocr-ambiguities" role="status">
                <strong>Ký hiệu chưa chắc chắn</strong>
                <ul>
                  {ocrCandidate.ambiguous_tokens.map((item, index) => (
                    <li key={`${item.token}-${index}`}>
                      <code>{item.token}</code>
                      {item.alternatives.length > 0 ? `; có thể là ${item.alternatives.join(', ')}` : ''}
                      {item.reason ? ` — ${item.reason}` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {ocrCandidate.warnings.length > 0 && (
              <ul className="fa2-ocr-warnings">
                {ocrCandidate.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
            <details>
              <summary>Văn bản OCR gốc</summary>
              <pre>{ocrCandidate.ocr_text || 'Không có văn bản OCR.'}</pre>
            </details>
            <div className="fa2-ocr-review-actions">
              <button type="button" className="sp-btn-primary" onClick={onConfirmOcr} disabled={loading || ocrLoading || !expression.trim()}>
                {loading ? <span className="sp-spinner" aria-hidden="true" /> : 'Xác nhận và phân tích'}
              </button>
              <button type="button" className="sp-btn-secondary" onClick={onDiscardOcr} disabled={loading || ocrLoading}>Bỏ kết quả OCR</button>
            </div>
          </section>
        )}
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

function suggestedParameterValue(value: string) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(-10, Math.min(10, numeric));
}
