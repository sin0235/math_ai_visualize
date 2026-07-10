import { useRef, useState } from 'react';
import { addStyles, EditableMathField } from 'react-mathquill';
import type { AlgebraInputFormat, AlgebraTopic } from '../../api/client';
import { KatexSpan } from '../KatexSpan';
import { isToolbarActionSupported } from './toolbarCapability';

addStyles();

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
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

export function AlgebraInput({
  input,
  inputFormat,
  inputMode,
  topic,
  domain,
  variables,
  useAiExtraction,
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
  onIntervalPresetChange: (value: IntervalPreset) => void;
  onIntervalStartChange: (value: string) => void;
  onIntervalEndChange: (value: string) => void;
  onIntervalClosedStartChange: (value: boolean) => void;
  onIntervalClosedEndChange: (value: boolean) => void;
  sequenceDraft: SequenceDraft;
  onSequenceDraftChange: (value: SequenceDraft) => void;
  onSubmit: () => void;
}) {
  const [activeSnippetGroup, setActiveSnippetGroup] = useState(0);
  const suggestedTopic = suggestTopic(input);
  const mathFieldRef = useRef<{
    cmd: (command: string) => void;
    write: (latex: string) => void;
    keystroke: (keys: string) => void;
    focus: () => void;
  } | null>(null);

  function insertMathSnippet(action: MathSnippetAction) {
    onInputModeChange('math');
    onInputFormatChange('latex');

    const mathField = mathFieldRef.current;
    if (!mathField) return;

    mathField.focus();
    if (action === 'frac') mathField.cmd('\\frac');
    else if (action === 'nthRoot') mathField.write('\\sqrt[3]{}');
    else if (action === 'power') mathField.write('^{}');
    else if (action === 'log') mathField.write('\\log_{}\\left(\\right)');
    else if (action === 'ln') mathField.write('\\ln\\left(\\right)');
    else if (action === 'abs') mathField.write('\\left|\\right|');
    else if (action === 'vector') mathField.write('\\vec{}');
    else if (action === 'derivative') {
      onTopicChange('calculus_derivative');
      mathField.write('\\frac{d}{dx}\\left(\\right)');
    }
    else if (action === 'integral') {
      onTopicChange('calculus_integral');
      mathField.write('\\int_{}^{}');
    }
    else if (action === 'sum') mathField.write('\\sum_{}^{}');
    else if (action === 'product') mathField.write('\\prod_{}^{}');
    else if (action === 'limit') {
      onTopicChange('calculus_limit');
      mathField.write('\\lim_{x\\to0}\\left(\\right)');
    }
    else if (action === 'system2') {
      onTopicChange('system');
      onVariablesChange('x,y');
      mathField.write('x+y=0; x-y=0');
    }
    else if (action === 'system3') {
      onTopicChange('system');
      onVariablesChange('x,y,z');
      mathField.write('x+y+z=0; x-y=0; y-z=0');
    }
    else if (action === 'equation') mathField.write('x=0');
    else if (action === 'sin') mathField.write('\\sin\\left(\\right)');
    else if (action === 'cos') mathField.write('\\cos\\left(\\right)');
    else if (action === 'tan') mathField.write('\\tan\\left(\\right)');
    else if (action === 'cot') mathField.write('\\cot\\left(\\right)');
    else if (action === 'asin') mathField.write('\\sin^{-1}\\left(\\right)');
    else if (action === 'acos') mathField.write('\\cos^{-1}\\left(\\right)');
    else if (action === 'atan') mathField.write('\\tan^{-1}\\left(\\right)');
    else if (action === 'acot') mathField.write('\\cot^{-1}\\left(\\right)');
    else if (action === 'gt') mathField.write('>');
    else if (action === 'lt') mathField.write('<');
    else if (action === 'ge') mathField.write('\\ge ');
    else if (action === 'le') mathField.write('\\le ');
    else if (action === 'eq') mathField.write('=');
    else if (action === 'ne') mathField.write('\\ne ');
    else if (action === 'approx') mathField.write('\\approx ');
    else if (action === 'plus') mathField.write('+');
    else if (action === 'minus') mathField.write('-');
    else if (action === 'pm') mathField.write('\\pm ');
    else if (action === 'times') mathField.write('\\cdot ');
    else if (action === 'divide') mathField.write('/');
    else if (action === 'pi') mathField.write('\\pi ');
    else if (action === 'e') mathField.write('e');
    else if (action === 'infty') mathField.write('\\infty ');
    else if (action === 'posInfty') mathField.write('+\\infty ');
    else if (action === 'negInfty') mathField.write('-\\infty ');
    else if (action === 'in') mathField.write('\\in ');
    else if (action === 'notin') mathField.write('\\notin ');
    else if (action === 'subset') mathField.write('\\subset ');
    else if (action === 'cup') mathField.write('\\cup ');
    else if (action === 'cap') mathField.write('\\cap ');
    else if (action === 'emptyset') mathField.write('\\emptyset ');
    else if (action === 'forall') mathField.write('\\forall ');
    else if (action === 'exists') mathField.write('\\exists ');
    else if (action === 'Rightarrow') mathField.write('\\Rightarrow ');
    else if (action === 'Leftrightarrow') mathField.write('\\Leftrightarrow ');
    else if (action === 'factorial') mathField.write('!');
    else if (action === 'combination') mathField.write('C_{}^{}');
    else if (action === 'permutation') mathField.write('A_{}^{}');
  }

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Bộ giải đại số</span>
        <h2>Nhập bài toán</h2>
      </div>

      <div className="algebra-mode-tabs" role="tablist" aria-label="Chế độ nhập">
        <button type="button" className={inputMode === 'natural' ? 'active' : ''} onClick={() => { onInputModeChange('natural'); onInputFormatChange('auto'); }} disabled={loading}>Tiếng Việt</button>
        <button type="button" className={inputMode === 'math' ? 'active' : ''} onClick={() => { onInputModeChange('math'); onInputFormatChange('latex'); }} disabled={loading}>Công thức</button>
      </div>

      {topic === 'sequence' && (
        <SequenceBuilder draft={sequenceDraft} loading={loading} onChange={onSequenceDraftChange} />
      )}

      {inputMode === 'math' ? (
        <div className="field-label algebra-math-field-wrap">
          Nhập công thức
          <EditableMathField
            latex={input}
            onChange={(mathField) => onInputChange(mathField.latex())}
            mathquillDidMount={(mathField) => { mathFieldRef.current = mathField; }}
            config={{ spaceBehavesLikeTab: true }}
            className="algebra-math-field"
          />
        </div>
      ) : (
        <label className="field-label">
          Nhập bài toán
          <textarea
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            placeholder="Nhập đề bài bằng tiếng Việt"
            rows={5}
            disabled={loading}
          />
        </label>
      )}

      {suggestedTopic && topic !== suggestedTopic && (
        <button type="button" className="algebra-topic-suggestion" onClick={() => onTopicChange(suggestedTopic)} disabled={loading}>
          Gợi ý dạng bài: {topicLabel(suggestedTopic)}
        </button>
      )}

      <div className="algebra-math-toolbar" aria-label="Chèn ô công thức">
        <div className="algebra-snippet-tabs" role="tablist" aria-label="Nhóm công thức">
          {MATH_SNIPPET_GROUPS.map((group, index) => (
            <button
              type="button"
              role="tab"
              key={group.title}
              className={activeSnippetGroup === index ? 'active' : ''}
              aria-selected={activeSnippetGroup === index}
              aria-label={group.title}
              title={group.title}
              onClick={() => setActiveSnippetGroup(index)}
              disabled={loading}
            >
              <KatexSpan tex={group.tex} className="algebra-snippet-katex" />
            </button>
          ))}
        </div>
        <div className="algebra-snippet-grid" role="tabpanel">
          {MATH_SNIPPET_GROUPS[activeSnippetGroup].items
            .filter((snippet) => isToolbarActionSupported(snippet.action))
            .map((snippet) => (
            <button type="button" key={snippet.title} title={snippet.title} aria-label={snippet.title} onClick={() => insertMathSnippet(snippet.action)} disabled={loading}>
              <KatexSpan tex={snippet.tex} className="algebra-snippet-katex" />
            </button>
          ))}
        </div>
      </div>

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
            <option value="combinatorics_probability">Tổ hợp</option>
            <option value="parameter">Tham số</option>
            <option value="calculus_derivative">Đạo hàm</option>
            <option value="calculus_limit">Giới hạn</option>
            <option value="calculus_integral">Tích phân</option>
          </select>
        </label>
        <label className="field-label">
          Miền nghiệm
          <select value={domain} onChange={(event) => onDomainChange(event.target.value as AlgebraDomain)} disabled={loading}>
            <option value="R">R</option>
            <option value="C">C</option>
            <option value="N">N</option>
            <option value="Z">Z</option>
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
            <option value="unit_circle">[0, 2π)</option>
            <option value="custom">Tùy chỉnh…</option>
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
            Mặc định dùng interpreter tiếng Việt (không cần đăng nhập). Bật AI khi đề mơ hồ — cần đăng nhập.
            Với chế độ tiếng Việt, bạn sẽ xác nhận topic/miền/biến trước khi giải.
          </span>
        </label>
      )}

      <button type="button" className="auth-primary-button algebra-submit" onClick={onSubmit} disabled={loading || (!input.trim() && topic !== 'sequence')}>
        {loading ? 'Đang giải...' : (inputMode === 'natural' || useAiExtraction ? 'Tiếp theo: xác nhận' : 'Giải bài')}
      </button>
    </section>
  );
}

export function suggestTopic(input: string): AlgebraTopic | null {
  const text = input.trim().toLowerCase();
  if (!text) return null;
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
        <button type="button" className={draft.target === 'term' ? 'active' : ''} onClick={() => update({ target: 'term' })} disabled={loading}>Tính uₙ</button>
        <button type="button" className={draft.target === 'sum' ? 'active' : ''} onClick={() => update({ target: 'sum' })} disabled={loading}>Tính Sₙ</button>
      </div>
      <div className="algebra-sequence-grid">
        <label className="field-label">
          u₁
          <input value={draft.u1} onChange={(event) => update({ u1: event.target.value })} disabled={loading} inputMode="decimal" />
        </label>
        {draft.kind === 'arithmetic' ? (
          <label className="field-label">
            d
            <input value={draft.d} onChange={(event) => update({ d: event.target.value })} disabled={loading} inputMode="decimal" />
          </label>
        ) : (
          <label className="field-label">
            q
            <input value={draft.q} onChange={(event) => update({ q: event.target.value })} disabled={loading} inputMode="decimal" />
          </label>
        )}
        <label className="field-label">
          n
          <input value={draft.n} onChange={(event) => update({ n: event.target.value })} disabled={loading} inputMode="numeric" />
        </label>
      </div>
    </section>
  );
}
