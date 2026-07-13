import type { AlgebraInputFormat, AlgebraTopic } from '../../api/client';
import { KatexSpan } from '../KatexSpan';
import { MathInputComposer } from '../math-input/MathInputComposer';

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

const MATH_SNIPPET_GROUPS = [
  {
    title: 'Đại số & Tổ hợp',
    tex: 'x^2',
    items: [
      { tex: '\\frac{a}{b}', title: 'Phân thức', action: 'frac' },
      { tex: '\\sqrt[n]{a}', title: 'Căn bậc n', action: 'nthRoot' },
      { tex: 'a^{n}', title: 'Lũy thừa', action: 'power' },
      { tex: '\\log_{a}', title: 'Loga', action: 'log' },
      { tex: '\\ln', title: 'Ln', action: 'ln' },
      { tex: '\\left|a\\right|', title: 'Abs', action: 'abs' },
      { tex: '!', title: 'Giai thừa', action: 'factorial' },
      { tex: 'C_n^k', title: 'Tổ hợp', action: 'combination' },
      { tex: 'A_n^k', title: 'Chỉnh hợp', action: 'permutation' },
    ],
  },
  {
    title: 'Giải tích & PT',
    tex: '\\int',
    items: [
      { tex: '\\frac{d}{dx}', title: 'Đạo hàm', action: 'derivative' },
      { tex: '\\int', title: 'Tích phân', action: 'integral' },
      { tex: '\\sum', title: 'Tổng', action: 'sum' },
      { tex: '\\prod', title: 'Tích', action: 'product' },
      { tex: '\\lim', title: 'Giới hạn', action: 'limit' },
      { tex: '\\begin{cases}\\square\\\\\\square\\end{cases}', title: 'Hệ 2 ẩn', action: 'system2' },
      { tex: '\\begin{cases}\\square\\\\\\square\\\\\\square\\end{cases}', title: 'Hệ 3 ẩn', action: 'system3' },
      { tex: '=0', title: 'Phương trình', action: 'equation' },
    ],
  },
  {
    title: 'Lượng giác & Hình',
    tex: '\\sin',
    items: [
      { tex: '\\sin', title: 'Sin', action: 'sin' },
      { tex: '\\cos', title: 'Cos', action: 'cos' },
      { tex: '\\tan', title: 'Tan', action: 'tan' },
      { tex: '\\cot', title: 'Cot', action: 'cot' },
      { tex: '\\sin^{-1}', title: 'Arcsin', action: 'asin' },
      { tex: '\\cos^{-1}', title: 'Arccos', action: 'acos' },
      { tex: '\\tan^{-1}', title: 'Arctan', action: 'atan' },
      { tex: '\\cot^{-1}', title: 'Arccot', action: 'acot' },
      // Degree unit hidden until backend supports angle_unit=degree
      { tex: '\\vec{v}', title: 'Vector', action: 'vector' },
    ],
  },
  {
    title: 'Ký hiệu & Logic',
    tex: '\\ge',
    items: [
      { tex: '>', title: 'Lớn hơn', action: 'gt' },
      { tex: '<', title: 'Bé hơn', action: 'lt' },
      { tex: '\\ge', title: 'Lớn hơn hoặc bằng', action: 'ge' },
      { tex: '\\le', title: 'Bé hơn hoặc bằng', action: 'le' },
      { tex: '=', title: 'Bằng', action: 'eq' },
      { tex: '\\ne', title: 'Khác', action: 'ne' },
      { tex: '\\approx', title: 'Xấp xỉ', action: 'approx' },
      { tex: '+', title: 'Cộng', action: 'plus' },
      { tex: '-', title: 'Trừ', action: 'minus' },
      { tex: '\\pm', title: 'Cộng trừ', action: 'pm' },
      { tex: '\\times', title: 'Nhân', action: 'times' },
      { tex: '\\div', title: 'Chia', action: 'divide' },
      { tex: '\\pi', title: 'Pi', action: 'pi' },
      { tex: 'e', title: 'Cơ số e', action: 'e' },
      { tex: '\\infty', title: 'Vô cùng', action: 'infty' },
      { tex: '+\\infty', title: 'Dương vô cùng', action: 'posInfty' },
      { tex: '-\\infty', title: 'Âm vô cùng', action: 'negInfty' },
      { tex: '\\in', title: 'Thuộc', action: 'in' },
      { tex: '\\notin', title: 'Không thuộc', action: 'notin' },
      { tex: '\\subset', title: 'Tập con', action: 'subset' },
      { tex: '\\cup', title: 'Hợp', action: 'cup' },
      { tex: '\\cap', title: 'Giao', action: 'cap' },
      { tex: '\\emptyset', title: 'Rỗng', action: 'emptyset' },
      { tex: '\\forall', title: 'Với mọi', action: 'forall' },
      { tex: '\\exists', title: 'Tồn tại', action: 'exists' },
      { tex: '\\Rightarrow', title: 'Suy ra', action: 'Rightarrow' },
      { tex: '\\Leftrightarrow', title: 'Tương đương', action: 'Leftrightarrow' },
    ],
  },
] as const;

type MathSnippetAction = (typeof MATH_SNIPPET_GROUPS)[number]['items'][number]['action'];

export type IntervalPreset = '' | 'unit_circle' | 'custom';
export type AlgebraAngleUnit = 'radian' | 'degree';

export function AlgebraInput({
  input,
  inputFormat,
  inputMode,
  topic,
  domain,
  variables,
  useAiExtraction,
  angleUnit,
  intervalPreset,
  intervalStart,
  intervalEnd,
  intervalClosedStart,
  intervalClosedEnd,
  loading,
  onInputChange,
  onInputFormatChange,
  onInputModeChange,
  onTopicChange,
  onDomainChange,
  onVariablesChange,
  onUseAiExtractionChange,
  onAngleUnitChange,
  onIntervalPresetChange,
  onIntervalStartChange,
  onIntervalEndChange,
  onIntervalClosedStartChange,
  onIntervalClosedEndChange,
  sequenceDraft,
  onSequenceDraftChange,
  onSubmit,
}: {
  input: string;
  inputFormat: AlgebraInputFormat;
  inputMode: AlgebraInputMode;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  useAiExtraction: boolean;
  angleUnit: AlgebraAngleUnit;
  intervalPreset: IntervalPreset;
  intervalStart: string;
  intervalEnd: string;
  intervalClosedStart: boolean;
  intervalClosedEnd: boolean;
  loading: boolean;
  onInputChange: (value: string) => void;
  onInputFormatChange: (value: AlgebraInputFormat) => void;
  onInputModeChange: (value: AlgebraInputMode) => void;
  onTopicChange: (value: AlgebraTopic) => void;
  onDomainChange: (value: AlgebraDomain) => void;
  onVariablesChange: (value: string) => void;
  onUseAiExtractionChange: (value: boolean) => void;
  onAngleUnitChange: (value: AlgebraAngleUnit) => void;
  onIntervalPresetChange: (value: IntervalPreset) => void;
  onIntervalStartChange: (value: string) => void;
  onIntervalEndChange: (value: string) => void;
  onIntervalClosedStartChange: (value: boolean) => void;
  onIntervalClosedEndChange: (value: boolean) => void;
  sequenceDraft: SequenceDraft;
  onSequenceDraftChange: (value: SequenceDraft) => void;
  onSubmit: () => void;
}) {
  const suggestedTopic = suggestTopic(input);

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Thiết lập bài toán</span>
        <h2>Nhập và cấu hình</h2>
      </div>

      <div className="algebra-input-section">
        <div className="algebra-input-section-head"><span>01</span><strong>Đề bài</strong></div>
        {topic === 'sequence' && (
          <SequenceBuilder draft={sequenceDraft} loading={loading} onChange={onSequenceDraftChange} />
        )}

        <MathInputComposer
          value={input}
          mode={inputMode}
          onChange={onInputChange}
          onModeChange={(mode) => {
            onInputModeChange(mode);
            onInputFormatChange(mode === 'math' ? 'latex' : 'auto');
          }}
          keyboard="algebra"
          disabled={loading}
          label="Nhập bài toán"
          naturalPlaceholder="Ví dụ: Giải phương trình x² - 5x + 6 = 0"
          onSubmit={onSubmit}
        />

        {suggestedTopic && topic !== suggestedTopic && (
          <button type="button" className="algebra-topic-suggestion" onClick={() => onTopicChange(suggestedTopic)} disabled={loading}>
            Gợi ý dạng bài: {topicLabel(suggestedTopic)}
          </button>
        )}
      </div>

      <div className="algebra-input-section">
        <div className="algebra-input-section-head"><span>02</span><strong>Thiết lập lời giải</strong></div>
        <div className="algebra-option-grid">
        <label className="field-label">
          Dạng bài
          <select value={topic} onChange={(event) => onTopicChange(event.target.value as AlgebraTopic)} disabled={loading}>
            <option value="auto">Tự nhận dạng</option>
            <option value="equation">Phương trình</option>
            <option value="inequality">Bất phương trình</option>
            <option value="exponential_log">Mũ-log</option>
            <option value="trigonometry">Lượng giác</option>
            <option value="complex">Số phức</option>
            <option value="system">Hệ phương trình</option>
            <option value="sequence">Cấp số</option>
            <option value="combinatorics_probability">Tổ hợp / XS</option>
            <option value="statistics">Thống kê</option>
            <option value="parameter">Tham số</option>
            <option value="calculus_derivative">Đạo hàm</option>
            <option value="calculus_limit">Giới hạn</option>
            <option value="calculus_integral">Tích phân</option>
          </select>
        </label>
        <label className="field-label">
          <span className="algebra-field-heading">
            <span>Miền nghiệm</span>
            <KatexSpan tex={DOMAIN_TEX[domain]} />
          </span>
          <select value={domain} onChange={(event) => onDomainChange(event.target.value as AlgebraDomain)} disabled={loading}>
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
            disabled={loading}
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
            disabled={loading}
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
              disabled={loading}
            />
          </label>
          <label className="field-label">
            Cận phải
            <input
              value={intervalEnd}
              onChange={(event) => onIntervalEndChange(event.target.value)}
              placeholder="vd 2*pi, pi/2, oo"
              disabled={loading}
            />
          </label>
          <label className="field-label algebra-ai-option">
            <span className="algebra-ai-option-row">
              <input
                type="checkbox"
                checked={intervalClosedStart}
                onChange={(event) => onIntervalClosedStartChange(event.target.checked)}
                disabled={loading}
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
                disabled={loading}
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
          disabled={loading}
        />
      </label>

      {inputMode === 'natural' && (
        <label className="field-label algebra-ai-option">
          <span className="algebra-ai-option-row">
            <input
              type="checkbox"
              checked={useAiExtraction}
              onChange={(event) => onUseAiExtractionChange(event.target.checked)}
              disabled={loading}
            />
            Dùng AI diễn giải đề
          </span>
          <span className="algebra-ai-option-hint">
            Mặc định dùng bộ phân tích tiếng Việt. Bật AI khi đề mơ hồ; tính năng này cần đăng nhập.
            Bạn luôn xác nhận dạng bài, miền và biến trước khi giải.
          </span>
        </label>
      )}
      </div>

      <button type="button" className="auth-primary-button algebra-submit" onClick={onSubmit} disabled={loading || (!input.trim() && topic !== 'sequence')}>
        {loading ? 'Đang giải...' : (inputMode === 'natural' || useAiExtraction ? 'Tiếp theo: xác nhận' : 'Giải bài')}
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

function topicLabel(topic: AlgebraTopic) {
  if (topic === 'inequality') return 'Bất phương trình';
  if (topic === 'system') return 'Hệ phương trình';
  if (topic === 'trigonometry') return 'Lượng giác';
  if (topic === 'exponential_log') return 'Mũ-log';
  if (topic === 'parameter') return 'Tham số';
  if (topic === 'sequence') return 'Cấp số';
  if (topic === 'statistics') return 'Thống kê';
  if (topic === 'combinatorics_probability') return 'Tổ hợp / XS';
  if (topic === 'calculus_derivative') return 'Đạo hàm';
  if (topic === 'calculus_limit') return 'Giới hạn';
  if (topic === 'calculus_integral') return 'Tích phân';
  return 'Tự nhận dạng';
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
