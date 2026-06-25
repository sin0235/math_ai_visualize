import { DragEvent, FormEvent, MouseEvent, useRef, useState } from 'react';

import type { AdvancedRenderSettings, CoordinateAssignment, ReasoningLayerMode, Renderer } from '../types/scene';

export const defaultAdvancedSettings: AdvancedRenderSettings = {
  coordinate_assignment: 'ai',
  reasoning_layer: 'off',
  show_coordinates: null,
  auto_segments_from_faces: true,
  verify_scene: true,
  graph_intersections: false,
  show_axes: null,
  show_grid: null,
};

const nullableBooleanOptions = [
  { value: 'auto', label: 'Mặc định (AI quyết định)' },
  { value: 'true', label: 'Bật' },
  { value: 'false', label: 'Tắt' },
] as const;

export interface ModelOption {
  key: string;
  label: string;
  provider: string;
  description: string;
  modelId?: string;
}

export type TierKey = 'tier1' | 'tier2' | 'tier3';

const tierOptions: Array<{ value: TierKey; label: string; description: string }> = [
  { value: 'tier1', label: 'Tiêu chuẩn', description: 'Nhanh, phù hợp với hầu hết bài toán.' },
  { value: 'tier2', label: 'Nâng cao', description: 'Cân bằng giữa tốc độ và chất lượng.' },
  { value: 'tier3', label: 'Tối đa', description: 'Chất lượng cao nhất, xử lý chậm hơn.' },
];

const examples = [
  {
    tag: '2D',
    title: 'Đường thẳng qua hai điểm',
    text: 'Cho A(1,2), B(4,5). Vẽ đường thẳng AB.',
  },
  {
    tag: 'Hàm số',
    title: 'Đồ thị bậc hai',
    text: 'Vẽ đồ thị hàm số y = x^2 - 2x + 1.',
  },
  {
    tag: '3D',
    title: 'Hình chóp',
    text: 'Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.',
  },
  {
    tag: 'Đường tròn',
    title: 'Tâm và bán kính',
    text: 'Vẽ đường tròn tâm O bán kính 2.',
  },
  {
    tag: 'Tam giác',
    title: 'Tam giác vuông',
    text: 'Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Vẽ đường trung tuyến AM.',
  },
];

type NullableBooleanSelectValue = (typeof nullableBooleanOptions)[number]['value'];

function parseNullableBoolean(value: NullableBooleanSelectValue): boolean | null {
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

function formatNullableBoolean(value: boolean | null | undefined): NullableBooleanSelectValue {
  if (value === true) return 'true';
  if (value === false) return 'false';
  return 'auto';
}

interface ProblemInputProps {
  loading: boolean;
  ocrLoading: boolean;
  ocrError: string | null;
  problemText: string;
  tier: TierKey;
  onProblemTextChange: (next: string) => void;
  onTierChange: (next: TierKey) => void;
  onOcrImage: (file: File) => void;
  onOcrClipboardImage: () => void;
  onSubmit: (
    problemText: string,
    tier: TierKey,
    advancedSettings?: AdvancedRenderSettings,
    preferredRenderer?: Renderer,
    preferredAiModel?: string,
  ) => void;
  modelOptions?: ModelOption[];
}

export function ProblemInput({
  loading,
  ocrLoading,
  ocrError,
  problemText,
  tier,
  onProblemTextChange,
  onTierChange,
  onOcrImage,
  onOcrClipboardImage,
  onSubmit,
  modelOptions = [],
}: ProblemInputProps) {
  const [preferredRenderer, setPreferredRenderer] = useState<'auto' | Renderer>('auto');
  const [preferredModelKey, setPreferredModelKey] = useState('default:auto');
  const [advancedSettings, setAdvancedSettings] = useState<AdvancedRenderSettings>(defaultAdvancedSettings);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const busy = loading || ocrLoading;
  const submitDisabled = busy;

  function updateAdvancedSettings(next: Partial<AdvancedRenderSettings>) {
    setAdvancedSettings((current) => ({ ...current, ...next }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const selectedModel = modelOptions.find((option) => option.key === preferredModelKey);
    onSubmit(
      problemText,
      tier,
      advancedSettings,
      preferredRenderer === 'auto' ? undefined : preferredRenderer,
      selectedModel?.modelId,
    );
  }

  function pickImageFile(files: FileList | null) {
    const file = Array.from(files ?? []).find((item) => item.type.startsWith('image/'));
    if (file) {
      onOcrImage(file);
    }
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (busy) return;
    setDragActive(false);
    pickImageFile(event.dataTransfer.files);
  }

  function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    if (busy) return;
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith('image/'));
    const file = imageItem?.getAsFile();
    if (!file) return;
    event.preventDefault();
    onOcrImage(file);
  }

  function handleTextAreaDoubleClick(event: MouseEvent<HTMLTextAreaElement>) {
    if (problemText.trim() || loading || ocrLoading) return;
    event.preventDefault();
    fileInputRef.current?.click();
  }

  function handleContextMenu(event: MouseEvent<HTMLTextAreaElement>) {
    if (problemText.trim() || loading || ocrLoading) return;
    event.preventDefault();
    onOcrClipboardImage();
  }

  function openImagePicker() {
    fileInputRef.current?.click();
  }

  return (
    <form className="panel problem-form" onSubmit={handleSubmit}>
      <div>
        <div className="panel-title">Nhập mô tả</div>
        <details className="ocr-actions-panel">
          <summary>Nhập bằng ảnh / OCR</summary>
          <div className="ocr-action-row" aria-label="Thao tác nhập bằng hình ảnh">
            <button type="button" disabled={busy} onClick={openImagePicker}>Tải ảnh đề bài</button>
            <button type="button" disabled={busy} onClick={onOcrClipboardImage}>Dán ảnh</button>
          </div>
        </details>
      </div>
      <div
        className={`textarea-wrap ocr-dropzone ${dragActive ? 'drag-active' : ''} ${!problemText.trim() ? 'empty' : ''}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragActive(true);
        }}
        onDragLeave={() => { if (!busy) setDragActive(false); }}
        onDrop={handleDrop}
      >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden-file-input"
            onChange={(event) => {
              pickImageFile(event.target.files);
              event.target.value = '';
            }}
          />
          <textarea
            value={problemText}
            disabled={busy}
            onChange={(event) => {
              if (busy) return;
              onProblemTextChange(event.target.value);
            }}
            onPaste={handlePaste}
            onDoubleClick={handleTextAreaDoubleClick}
            onContextMenu={handleContextMenu}
            rows={10}
            maxLength={2000}
            placeholder="Ví dụ: Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Vẽ đường trung tuyến AM."
          />
          {!busy && !problemText.trim() && <div className="ocr-empty-hint">Bạn có thể gõ đề, kéo-thả ảnh hoặc paste ảnh trực tiếp vào khung này.</div>}
          {ocrError && <div className="ocr-error">{ocrError}</div>}
          <div className="char-counter">{problemText.length}/2000 ký tự</div>
        {busy && (
          <div className="textarea-overlay" role="status" aria-live="polite">
            <Spinner className="spinner-overlay" />
            <div className="textarea-overlay-text">{loading ? 'Đang dựng hình...' : 'Đang đọc ảnh...'}</div>
          </div>
        )}
      </div>
      <label className="field-label">
        <span title="Chọn mức độ chất lượng AI dùng để phân tích đề và dựng hình">Mức độ chất lượng</span>
        <select
          value={tier}
          title={tierOptions.find((option) => option.value === tier)?.description ?? ''}
          onChange={(event) => onTierChange(event.target.value as TierKey)}
        >
          {tierOptions.map((option) => (
            <option key={option.value} value={option.value} title={option.description}>{option.label}</option>
          ))}
        </select>
        <span className="field-hint">{tierOptions.find((option) => option.value === tier)?.description}</span>
      </label>
      <button disabled={submitDisabled || !problemText.trim()} type="submit" className="submit-button submit-button-sticky">
        {(loading || ocrLoading) && <Spinner />}
        {ocrLoading ? 'Đang đọc ảnh...' : loading ? 'Đang dựng hình...' : 'Dựng hình'}
      </button>
      <details className="advanced-settings">
        <summary title="Các tùy chọn này không di chuyển điểm đã được đề bài xác định.">Tùy chọn nâng cao</summary>
        <label className="field-label">
          Chiến lược đặt tọa độ
          <select
            value={advancedSettings.coordinate_assignment}
            onChange={(event) => updateAdvancedSettings({ coordinate_assignment: event.target.value as CoordinateAssignment })}
          >
            <option value="ai">AI tự quyết định</option>
            <option value="auto_origin">Tự động thêm gốc tọa độ khi cần</option>
            <option value="prefer_o_origin">Dùng điểm O trong đề nếu phù hợp</option>
          </select>
        </label>
        <label className="field-label">
          Lớp suy luận trước khi vẽ
          <select
            value={advancedSettings.reasoning_layer}
            onChange={(event) => updateAdvancedSettings({ reasoning_layer: event.target.value as ReasoningLayerMode })}
          >
            <option value="off">Tắt</option>
            <option value="auto">Tự động khi đề cần suy luận</option>
            <option value="force">Luôn bật</option>
          </select>
          <span className="field-hint">Hữu ích cho toán thực tế hoặc đề cần xác định mô hình/hình cần vẽ trước.</span>
        </label>
        <label className="field-label">
          Công cụ vẽ
          <select value={preferredRenderer} onChange={(event) => setPreferredRenderer(event.target.value as 'auto' | Renderer)}>
            <option value="auto">Tự động (AI chọn 2D hoặc 3D)</option>
            <option value="geogebra_2d">GeoGebra 2D</option>
            <option value="geogebra_3d">GeoGebra 3D</option>
            <option value="threejs_3d">Three.js 3D</option>
          </select>
        </label>
        {modelOptions.length > 0 && (
          <label className="field-label">
            Model dựng hình
            <select value={preferredModelKey} onChange={(event) => setPreferredModelKey(event.target.value)}>
              {modelOptions.map((option) => (
                <option key={option.key} value={option.key} title={option.description}>{option.label}</option>
              ))}
            </select>
            <span className="field-hint">{modelOptions.find((option) => option.key === preferredModelKey)?.description ?? 'Backend tự chọn model phù hợp.'}</span>
          </label>
        )}
        <label className="field-label">
          Hiển thị tọa độ điểm
          <select
            value={formatNullableBoolean(advancedSettings.show_coordinates)}
            onChange={(event) => updateAdvancedSettings({ show_coordinates: parseNullableBoolean(event.target.value as NullableBooleanSelectValue) })}
          >
            {nullableBooleanOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label className="field-label">
          Hiển thị trục tọa độ
          <select
            value={formatNullableBoolean(advancedSettings.show_axes)}
            onChange={(event) => updateAdvancedSettings({ show_axes: parseNullableBoolean(event.target.value as NullableBooleanSelectValue) })}
          >
            {nullableBooleanOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label className="field-label">
          Hiển thị lưới nền
          <select
            value={formatNullableBoolean(advancedSettings.show_grid)}
            onChange={(event) => updateAdvancedSettings({ show_grid: parseNullableBoolean(event.target.value as NullableBooleanSelectValue) })}
          >
            {nullableBooleanOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={advancedSettings.auto_segments_from_faces}
            onChange={(event) => updateAdvancedSettings({ auto_segments_from_faces: event.target.checked })}
          />
          Tự động thêm cạnh từ các mặt
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={advancedSettings.verify_scene}
            onChange={(event) => updateAdvancedSettings({ verify_scene: event.target.checked })}
          />
          Kiểm chứng quan hệ hình học
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={advancedSettings.graph_intersections}
            onChange={(event) => updateAdvancedSettings({ graph_intersections: event.target.checked })}
          />
          Tìm giao điểm tự động
        </label>
      </details>
      <details className="examples">
        <summary className="examples-title">Đề mẫu</summary>
        {examples.map((example) => (
          <button key={example.text} type="button" onClick={() => onProblemTextChange(example.text)} className="example-card">
            <span className="example-tag">{example.tag}</span>
            <span className="example-title">{example.title}</span>
            <span className="example-text">{example.text}</span>
          </button>
        ))}
      </details>
    </form>
  );
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg className={`spinner ${className ?? ''}`.trim()} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
