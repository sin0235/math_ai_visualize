import { DragEvent, MouseEvent, useEffect, useMemo, useRef, useState } from 'react';

import { getMathCapabilities, type AlgebraTopic, type MathCapabilityRegistry } from '../../api/client';
import { KatexSpan } from '../KatexSpan';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
const DOMAIN_TEX: Record<AlgebraDomain, string> = {
  R: String.raw`\mathbb{R}`,
  C: String.raw`\mathbb{C}`,
  N: String.raw`\mathbb{N}`,
  Z: String.raw`\mathbb{Z}`,
};

export type AlgebraInputMode = 'natural' | 'math';
export interface SequenceDraft {
  kind: 'arithmetic' | 'geometric';
  target: 'term' | 'sum';
  u1: string;
  d: string;
  q: string;
  n: string;
}

export type IntervalPreset = '' | 'unit_circle' | 'custom';
export type AlgebraAngleUnit = 'radian' | 'degree';

export function AlgebraInput({
  input,
  topic,
  domain,
  variables,
  angleUnit,
  intervalPreset,
  intervalStart,
  intervalEnd,
  intervalClosedStart,
  intervalClosedEnd,
  loading,
  ocrLoading = false,
  ocrError = null,
  expanded,
  onExpandedChange,
  onInputChange,
  onTopicChange,
  onDomainChange,
  onVariablesChange,
  onAngleUnitChange,
  onIntervalPresetChange,
  onIntervalStartChange,
  onIntervalEndChange,
  onIntervalClosedStartChange,
  onIntervalClosedEndChange,
  sequenceDraft,
  onSequenceDraftChange,
  onOcrImage,
  onOcrClipboardImage,
  onSubmit,
}: {
  input: string;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  angleUnit: AlgebraAngleUnit;
  intervalPreset: IntervalPreset;
  intervalStart: string;
  intervalEnd: string;
  intervalClosedStart: boolean;
  intervalClosedEnd: boolean;
  loading: boolean;
  ocrLoading?: boolean;
  ocrError?: string | null;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  onInputChange: (value: string) => void;
  onTopicChange: (value: AlgebraTopic) => void;
  onDomainChange: (value: AlgebraDomain) => void;
  onVariablesChange: (value: string) => void;
  onAngleUnitChange: (value: AlgebraAngleUnit) => void;
  onIntervalPresetChange: (value: IntervalPreset) => void;
  onIntervalStartChange: (value: string) => void;
  onIntervalEndChange: (value: string) => void;
  onIntervalClosedStartChange: (value: boolean) => void;
  onIntervalClosedEndChange: (value: boolean) => void;
  sequenceDraft: SequenceDraft;
  onSequenceDraftChange: (value: SequenceDraft) => void;
  onOcrImage?: (file: File) => void;
  onOcrClipboardImage?: () => void;
  onSubmit: () => void;
}) {
  const [capabilityRegistry, setCapabilityRegistry] = useState<MathCapabilityRegistry | null>(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const busy = loading || ocrLoading;
  const suggestedTopic = suggestTopic(input);
  const topicOptions = capabilityRegistry?.ui.algebra_topics ?? [];
  const topicLabels = useMemo(
    () => new Map(topicOptions.map((option) => [option.topic, option.label])),
    [topicOptions],
  );

  useEffect(() => {
    let active = true;
    getMathCapabilities()
      .then((registry) => {
        if (!active) return;
        setCapabilityRegistry(registry);
        setCapabilityError(false);
      })
      .catch(() => {
        if (active) setCapabilityError(true);
      });
    return () => {
      active = false;
    };
  }, []);

  function pickImageFile(files: FileList | null) {
    if (!onOcrImage) return;
    const file = Array.from(files ?? []).find((item) => item.type.startsWith('image/'));
    if (file) onOcrImage(file);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (busy) return;
    setDragActive(false);
    pickImageFile(event.dataTransfer.files);
  }

  function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    if (busy || !onOcrImage) return;
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith('image/'));
    const file = imageItem?.getAsFile();
    if (!file) return;
    event.preventDefault();
    onOcrImage(file);
  }

  function handleTextAreaDoubleClick(event: MouseEvent<HTMLTextAreaElement>) {
    if (input.trim() || busy || !onOcrImage) return;
    event.preventDefault();
    fileInputRef.current?.click();
  }

  function handleContextMenu(event: MouseEvent<HTMLTextAreaElement>) {
    if (input.trim() || busy || !onOcrClipboardImage) return;
    event.preventDefault();
    onOcrClipboardImage();
  }

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Thiết lập bài toán</span>
        <h2>Nhập và cấu hình</h2>
      </div>
      <div className="algebra-input-section">
        <div className="algebra-input-section-head"><span>01</span><strong>Đề bài</strong></div>
        {topic === 'sequence' && (
          <SequenceBuilder draft={sequenceDraft} loading={busy} onChange={onSequenceDraftChange} />
        )}

        <div className="field-label algebra-vietnamese-input">
          <span>Nhập đề bằng tiếng Việt</span>
          <details className="ocr-actions-panel">
            <summary>Nhập bằng ảnh / OCR</summary>
            <div className="ocr-action-row" aria-label="Thao tác nhập bằng hình ảnh">
              <button type="button" disabled={busy || !onOcrImage} onClick={() => fileInputRef.current?.click()}>
                Tải ảnh đề bài
              </button>
              <button type="button" disabled={busy || !onOcrClipboardImage} onClick={() => onOcrClipboardImage?.()}>
                Dán ảnh
              </button>
            </div>
          </details>
          <div
            className={`textarea-wrap ocr-dropzone ${dragActive ? 'drag-active' : ''} ${!input.trim() ? 'empty' : ''}`}
            onDragOver={(event) => {
              event.preventDefault();
              if (!busy) setDragActive(true);
            }}
            onDragLeave={() => {
              if (!busy) setDragActive(false);
            }}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden-file-input"
              aria-label="Tải ảnh đề bài để OCR"
              title="Tải ảnh đề bài để OCR"
              onChange={(event) => {
                pickImageFile(event.target.files);
                event.target.value = '';
              }}
            />
            <textarea
              value={input}
              onChange={(event) => {
                if (busy) return;
                onInputChange(event.target.value);
              }}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') onSubmit();
              }}
              onPaste={handlePaste}
              onDoubleClick={handleTextAreaDoubleClick}
              onContextMenu={handleContextMenu}
              rows={7}
              maxLength={2000}
              disabled={busy}
              placeholder="Ví dụ: Tìm tích phân của 2*x+1; giải phương trình x^2 - 5x + 6 = 0"
            />
            {!busy && !input.trim() && (
              <div className="ocr-empty-hint">Bạn có thể gõ đề, kéo-thả ảnh hoặc paste ảnh trực tiếp vào khung này.</div>
            )}
            {ocrError && <div className="ocr-error">{ocrError}</div>}
            <div className="char-counter">{input.length}/2000 ký tự</div>
            {busy && (
              <div className="textarea-overlay" role="status" aria-live="polite">
                <div className="textarea-overlay-text">{ocrLoading ? 'Đang đọc ảnh...' : 'Đang giải...'}</div>
              </div>
            )}
          </div>
          <span className="algebra-ai-option-hint">
            Hệ thống dùng NLP và AI để hiểu đề tiếng Việt, sau đó solver kiểm chứng và dựng lời giải từng bước.
          </span>
        </div>

        {suggestedTopic && topic !== suggestedTopic && (
          <button type="button" className="algebra-topic-suggestion" onClick={() => onTopicChange(suggestedTopic)} disabled={busy}>
            Gợi ý dạng bài: {topicLabels.get(suggestedTopic) ?? suggestedTopic}
          </button>
        )}
      </div>

      <div className="algebra-input-section">
        <div className="algebra-input-section-head"><span>02</span><strong>Thiết lập lời giải</strong></div>
        <div className="algebra-option-grid">
        <label className="field-label">
          Dạng bài
          <select value={topic} onChange={(event) => onTopicChange(event.target.value as AlgebraTopic)} disabled={busy || !capabilityRegistry}>
            <option value="auto">Tự nhận dạng</option>
            {topicOptions.map((option) => (
              <option
                key={option.topic}
                value={option.topic}
                disabled={option.status === 'planned' || option.status === 'unsupported'}
              >
                {option.label}{option.status === 'partial' ? ' (một phần)' : option.status === 'planned' ? ' (sắp hỗ trợ)' : ''}
              </option>
            ))}
          </select>
          {capabilityError && (
            <span className="algebra-ai-option-hint" role="status">
              Không tải được danh mục dạng bài. Tự nhận dạng vẫn dùng được.
            </span>
          )}
        </label>
        <label className="field-label">
          <span className="algebra-field-heading">
            <span>Miền nghiệm</span>
            <KatexSpan tex={DOMAIN_TEX[domain]} />
          </span>
          <select value={domain} onChange={(event) => onDomainChange(event.target.value as AlgebraDomain)} disabled={busy}>
            <option value="R">Số thực (R)</option>
            <option value="C">Số phức (C)</option>
            <option value="N">Số tự nhiên (N)</option>
            <option value="Z">Số nguyên (Z)</option>
          </select>
        </label>
        <label className="field-label">
          Khoảng nghiệm
          <select
            value={intervalPreset}
            onChange={(event) => onIntervalPresetChange(event.target.value as IntervalPreset)}
            disabled={busy}
          >
            <option value="">Không giới hạn (miền đầy đủ)</option>
            <option value="unit_circle">Một vòng lượng giác</option>
            <option value="custom">Tùy chỉnh…</option>
          </select>
        </label>
        <label className="field-label">
          Đơn vị góc
          <select
            value={angleUnit}
            onChange={(event) => onAngleUnitChange(event.target.value as AlgebraAngleUnit)}
            disabled={busy}
          >
            <option value="radian">Radian</option>
            <option value="degree">Độ</option>
          </select>
        </label>
      </div>

      {intervalPreset === 'custom' && (
        <div className="algebra-interval-custom">
          <label className="field-label">
            Cận trái
            <input
              value={intervalStart}
              onChange={(event) => onIntervalStartChange(event.target.value)}
              placeholder="vd 0, -pi, -oo"
              disabled={busy}
            />
          </label>
          <label className="field-label">
            Cận phải
            <input
              value={intervalEnd}
              onChange={(event) => onIntervalEndChange(event.target.value)}
              placeholder="vd 2*pi, pi/2, oo"
              disabled={busy}
            />
          </label>
          <label className="field-label algebra-ai-option">
            <span className="algebra-ai-option-row">
              <input
                type="checkbox"
                checked={intervalClosedStart}
                onChange={(event) => onIntervalClosedStartChange(event.target.checked)}
                disabled={busy}
              />
              Đóng cận trái [
            </span>
          </label>
          <label className="field-label algebra-ai-option">
            <span className="algebra-ai-option-row">
              <input
                type="checkbox"
                checked={intervalClosedEnd}
                onChange={(event) => onIntervalClosedEndChange(event.target.checked)}
                disabled={busy}
              />
              Đóng cận phải ]
            </span>
          </label>
          <p className="algebra-ai-option-hint">
            Chỉ số, pi, e, oo (vd -pi, pi/2, 2*pi). Áp dụng cho phương trình/bất phương trình/lượng giác.
          </p>
        </div>
      )}

      <label className="field-label">
        Biến cần giải
        <input
          value={variables}
          onChange={(event) => onVariablesChange(event.target.value)}
          placeholder="x hoặc x,y hoặc z (để trống để tự nhận diện)"
          disabled={busy}
        />
      </label>

      </div>

      <button type="button" className="auth-primary-button algebra-submit" onClick={onSubmit} disabled={busy || (!input.trim() && topic !== 'sequence')}>
        {ocrLoading ? 'Đang đọc ảnh...' : loading ? 'Đang giải...' : 'Giải bài'}
      </button>
    </section>
  );
}

export function suggestTopic(input: string): AlgebraTopic | null {
  const text = input.trim().toLowerCase();
  if (!text) return null;
  if (/stats\(|stats_freq\(|thống kê|thong ke|trung bình|trung binh|phương sai|phuong sai|median|mean|variance/.test(text)) return 'statistics';
  if (/derivative|đạo hàm|dao ham|d\/dx|\\frac\{d\}\{d[a-z]\}/.test(text)) return 'calculus_derivative';
  if (/limit|giới hạn|gioi han|lim|\\lim/.test(text)) return 'calculus_limit';
  if (/integral|tích phân|tich phan|nguyên hàm|nguyen ham|\\int/.test(text)) return 'calculus_integral';
  if (/\\(?:sin|cos|tan|cot)\s*\^\s*\{?-1\}?|\\arc(?:sin|cos|tan|cot)|\b(?:asin|acos|atan|acot|arcsin|arccos|arctan|arccot)\b/.test(text)) return 'trigonometry';
  if (/[<>≤≥]|\\le|\\ge/.test(text)) return 'inequality';
  if (text.includes(';')) return 'system';
  if (/sin|cos|tan|cot|\\sin|\\cos|\\tan|\\cot/.test(text)) return 'trigonometry';
  if (/log|ln|\\log|\\ln|\^\(/.test(text)) return 'exponential_log';
  if (/quadratic_/.test(text)) return 'parameter';
  if (/u_?1|cấp số|cap so|arithmetic|geometric/.test(text)) return 'sequence';
  return null;
}

function SequenceBuilder({ draft, loading, onChange }: { draft: SequenceDraft; loading: boolean; onChange: (value: SequenceDraft) => void }) {
  function update(patch: Partial<SequenceDraft>) {
    onChange({ ...draft, ...patch });
  }

  return (
    <section className="algebra-sequence-builder" aria-label="Điền nhanh cấp số">
      <div className="algebra-segmented-row" role="group" aria-label="Loại cấp số">
        <button type="button" className={draft.kind === 'arithmetic' ? 'active' : ''} onClick={() => update({ kind: 'arithmetic' })} disabled={loading}>Cấp số cộng</button>
        <button type="button" className={draft.kind === 'geometric' ? 'active' : ''} onClick={() => update({ kind: 'geometric' })} disabled={loading}>Cấp số nhân</button>
      </div>
      <div className="algebra-segmented-row" role="group" aria-label="Cần tính">
        <button type="button" className={draft.target === 'term' ? 'active' : ''} onClick={() => update({ target: 'term' })} disabled={loading}>Tính <KatexSpan tex="u_n" /></button>
        <button type="button" className={draft.target === 'sum' ? 'active' : ''} onClick={() => update({ target: 'sum' })} disabled={loading}>Tính <KatexSpan tex="S_n" /></button>
      </div>
      <div className="algebra-sequence-grid">
        <label className="field-label">
          <KatexSpan tex="u_1" />
          <input value={draft.u1} onChange={(event) => update({ u1: event.target.value })} disabled={loading} inputMode="decimal" />
        </label>
        {draft.kind === 'arithmetic' ? (
          <label className="field-label">
            <KatexSpan tex="d" />
            <input value={draft.d} onChange={(event) => update({ d: event.target.value })} disabled={loading} inputMode="decimal" />
          </label>
        ) : (
          <label className="field-label">
            <KatexSpan tex="q" />
            <input value={draft.q} onChange={(event) => update({ q: event.target.value })} disabled={loading} inputMode="decimal" />
          </label>
        )}
        <label className="field-label">
          <KatexSpan tex="n" />
          <input value={draft.n} onChange={(event) => update({ n: event.target.value })} disabled={loading} inputMode="numeric" />
        </label>
      </div>
    </section>
  );
}
