import { useEffect, useMemo, useRef, useState } from 'react';
import { getAnalyzerCapabilities, type AnalyzerCapabilityRegistry, type FunctionOcrExtraction } from '../../api/client';
import { KatexSpan, sympyToLatex } from '../KatexSpan';
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
  const [showAdvancedControls, setShowAdvancedControls] = useState(false);
  const [isDraggingImage, setIsDraggingImage] = useState(false);
  const [inputMode, setInputMode] = useState<'plain' | 'latex'>('plain');
  const [registry, setRegistry] = useState<AnalyzerCapabilityRegistry | null>(null);
  const [parameterRangeMode, setParameterRangeMode] = useState<'auto' | 'user'>('auto');
  const [parameterMinDraft, setParameterMinDraft] = useState('-10');
  const [parameterMaxDraft, setParameterMaxDraft] = useState('10');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const exampleGroups = useMemo(() => {
    if (!registry) return EXAMPLE_GROUPS;
    const groups = new Map<string, Array<{ label: string; value: string }>>();
    for (const example of registry.examples) {
      const items = groups.get(example.category) ?? [];
      items.push({ label: example.label, value: example.expression });
      groups.set(example.category, items);
    }
    return Array.from(groups, ([label, items]) => ({ label, items }));
  }, [registry]);
  const previewTex = inputMode === 'latex' ? expression : sympyToLatex(expression);
  const parameterMin = Number(parameterMinDraft);
  const parameterMax = Number(parameterMaxDraft);
  const parameterRangeValid = parameterMinDraft.trim() !== '' && parameterMaxDraft.trim() !== ''
    && Number.isFinite(parameterMin) && Number.isFinite(parameterMax) && parameterMin < parameterMax;
  const sliderMin = parameterRangeValid ? parameterMin : -10;
  const sliderMax = parameterRangeValid ? parameterMax : 10;

  useEffect(() => {
    let active = true;
    void getAnalyzerCapabilities().then((value) => {
      if (!active) return;
      setRegistry(value);
      const range = value.parameters.ranges.m;
      if (range) {
        setParameterMinDraft(String(range.min));
        setParameterMaxDraft(String(range.max));
      }
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

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
    <section className="fa2-control-panel" aria-label="Nhập hàm số">
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
            <label className="fa2-input-mode">
              <span className="sr-only">Chế độ nhập công thức</span>
              <select value={inputMode} onChange={(event) => setInputMode(event.target.value as 'plain' | 'latex')} disabled={loading || ocrLoading}>
                <option value="plain">Văn bản</option>
                <option value="latex">LaTeX</option>
              </select>
            </label>
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
                placeholder={inputMode === 'latex' ? String.raw`\frac{x^2-1}{x-2}` : 'x^3 - 3*x + 2'}
                list="fa-expression-functions"
                aria-describedby={`fa-expression-syntax fa-expression-preview${error ? ' fa-expression-error' : ''}`}
                aria-invalid={!!error}
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
              <datalist id="fa-expression-functions">
                {registry?.parser.functions.map((name) => <option key={name} value={`${name}(`} />)}
              </datalist>
            </div>
            <button id="fa-submit-btn" type="button" className="sp-btn-primary" onClick={onAnalyze} disabled={loading || ocrLoading || !!ocrCandidate || !expression.trim()}>
              {loading ? <span className="sp-spinner" aria-hidden="true" /> : ocrCandidate ? 'Xác nhận bên dưới' : 'Phân tích'}
            </button>
          </div>
          <div id="fa-expression-preview" className="fa2-expression-preview" aria-live="polite">
            <span>Xem trước</span>
            {expression.trim() ? <KatexSpan tex={previewTex} /> : <span>Nhập biểu thức để xem công thức.</span>}
          </div>
          <small id="fa-expression-syntax" className="fa2-expression-syntax">
            Dùng biến <code>x</code>{registry?.parameters.supported.includes('m') ? <> và tham số <code>m</code></> : null}. Xem hướng dẫn để biết cú pháp hỗ trợ.
          </small>
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
                    Miền slider
                    <select value={parameterRangeMode} onChange={(event) => {
                      const mode = event.target.value as 'auto' | 'user';
                      setParameterRangeMode(mode);
                      if (mode === 'auto') {
                        const range = registry?.parameters.ranges.m;
                        setParameterMinDraft(String(range?.min ?? -10));
                        setParameterMaxDraft(String(range?.max ?? 10));
                      }
                    }}>
                      <option value="auto">Tự động theo registry backend</option>
                      <option value="user">Tùy chỉnh</option>
                    </select>
                  </label>
                  {parameterRangeMode === 'user' && (
                    <div className="fa2-parameter-range-inputs">
                      <label>
                        Giá trị nhỏ nhất
                        <input type="number" value={parameterMinDraft} aria-invalid={!parameterRangeValid} step="any" onChange={(event) => setParameterMinDraft(event.target.value)} />
                      </label>
                      <label>
                        Giá trị lớn nhất
                        <input type="number" value={parameterMaxDraft} aria-invalid={!parameterRangeValid} step="any" onChange={(event) => setParameterMaxDraft(event.target.value)} />
                      </label>
                      {!parameterRangeValid && <small role="alert">Cận slider phải là số hữu hạn và cận trái nhỏ hơn cận phải.</small>}
                    </div>
                  )}
                  <label>
                    Slider gợi ý từ {parameterMinDraft || '?'} đến {parameterMaxDraft || '?'}
                    <input
                      type="range"
                      min={sliderMin}
                      max={sliderMax}
                      step={registry?.parameters.ranges.m?.step ?? 0.1}
                      value={suggestedParameterValue(parameterValue, sliderMin, sliderMax)}
                      onChange={(event) => onParameterValueChange(event.target.value)}
                      disabled={!parameterRangeValid}
                    />
                  </label>
                  <small>Slider chỉ gợi ý; giá trị exact nhập tay không bị giới hạn.</small>
                </div>
              )}
            </fieldset>
          )}
          <button type="button" className="fa2-advanced-toggle" onClick={() => setShowAdvancedControls((value) => !value)} aria-expanded={showAdvancedControls}>
            {showAdvancedControls ? 'Ẩn nhập nâng cao' : 'Ví dụ và nhập bằng ảnh'}
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
            {exampleGroups.map((group) => (
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
            role="button"
            tabIndex={loading || ocrLoading ? -1 : 0}
            aria-label="Chọn ảnh để OCR công thức"
            aria-disabled={loading || ocrLoading}
            onKeyDown={(event) => {
              if ((event.key === 'Enter' || event.key === ' ') && !loading && !ocrLoading) {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
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

      {error && <div id="fa-expression-error" className="sp-error" role="alert">{error}</div>}
    </section>
  );
}

function suggestedParameterValue(value: string, min: number, max: number) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return Math.max(min, Math.min(max, 0));
  return Math.max(min, Math.min(max, numeric));
}
