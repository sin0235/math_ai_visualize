import { useRef, useState } from 'react';
import { addStyles, EditableMathField } from 'react-mathquill';
import type { AlgebraInputFormat, AlgebraTopic } from '../../api/client';

addStyles();

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
export type AlgebraInputMode = 'natural' | 'math';

const MATH_SNIPPET_GROUPS = [
  {
    title: 'Đa thức',
    label: 'x²',
    items: [
      { label: 'a⁄b', title: 'Phân thức', action: 'frac' },
      { label: 'ⁿ√a', title: 'Căn bậc n', action: 'nthRoot' },
      { label: 'aⁿ', title: 'Lũy thừa', action: 'power' },
      { label: 'logₐ', title: 'Loga', action: 'log' },
      { label: 'ln', title: 'Ln', action: 'ln' },
      { label: '|a|', title: 'Abs', action: 'abs' },
    ],
  },
  {
    title: 'Đạo hàm và phương trình',
    label: '∫',
    items: [
      { label: 'd/dx', title: 'Đạo hàm', action: 'derivative' },
      { label: '∫', title: 'Tích phân', action: 'integral' },
      { label: 'Σ', title: 'Tổng', action: 'sum' },
      { label: 'Π', title: 'Tích', action: 'product' },
      { label: 'lim', title: 'Giới hạn', action: 'limit' },
      { label: '{2', title: 'Hệ 2 ẩn', action: 'system2' },
      { label: '{3', title: 'Hệ 3 ẩn', action: 'system3' },
      { label: '=0', title: 'Phương trình', action: 'equation' },
    ],
  },
  {
    title: 'Lượng giác',
    label: 'sin',
    items: [
      { label: 'sin', title: 'Sin', action: 'sin' },
      { label: 'cos', title: 'Cos', action: 'cos' },
      { label: 'tan', title: 'Tan', action: 'tan' },
      { label: 'cot', title: 'Cot', action: 'cot' },
      { label: 'sin⁻¹', title: 'Arcsin', action: 'asin' },
      { label: 'cos⁻¹', title: 'Arccos', action: 'acos' },
      { label: 'tan⁻¹', title: 'Arctan', action: 'atan' },
      { label: 'cot⁻¹', title: 'Arccot', action: 'acot' },
    ],
  },
  {
    title: 'Phép tính',
    label: '≥',
    items: [
      { label: '>', title: 'Lớn hơn', action: 'gt' },
      { label: '<', title: 'Bé hơn', action: 'lt' },
      { label: '≥', title: 'Lớn hơn hoặc bằng', action: 'ge' },
      { label: '≤', title: 'Bé hơn hoặc bằng', action: 'le' },
      { label: '=', title: 'Bằng', action: 'eq' },
      { label: '≠', title: 'Khác', action: 'ne' },
      { label: '+', title: 'Cộng', action: 'plus' },
      { label: '−', title: 'Trừ', action: 'minus' },
      { label: '×', title: 'Nhân', action: 'times' },
      { label: '÷', title: 'Chia', action: 'divide' },
    ],
  },
] as const;

type MathSnippetAction = (typeof MATH_SNIPPET_GROUPS)[number]['items'][number]['action'];

export function AlgebraInput({
  input,
  inputFormat,
  inputMode,
  topic,
  domain,
  variables,
  loading,
  onInputChange,
  onInputFormatChange,
  onInputModeChange,
  onTopicChange,
  onDomainChange,
  onVariablesChange,
  onSubmit,
}: {
  input: string;
  inputFormat: AlgebraInputFormat;
  inputMode: AlgebraInputMode;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onInputFormatChange: (value: AlgebraInputFormat) => void;
  onInputModeChange: (value: AlgebraInputMode) => void;
  onTopicChange: (value: AlgebraTopic) => void;
  onDomainChange: (value: AlgebraDomain) => void;
  onVariablesChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const [activeSnippetGroup, setActiveSnippetGroup] = useState(0);
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
    else if (action === 'derivative') mathField.write('\\frac{d}{dx}\\left(\\right)');
    else if (action === 'integral') mathField.write('\\int_{}^{}\\left(\\right)dx');
    else if (action === 'sum') mathField.write('\\sum_{}^{}');
    else if (action === 'product') mathField.write('\\prod_{}^{}');
    else if (action === 'limit') mathField.write('\\lim_{x\\to 0}');
    else if (action === 'system2') {
      onTopicChange('system');
      onVariablesChange('x,y');
      onInputChange('x+y=0; x-y=0');
    }
    else if (action === 'system3') {
      onTopicChange('system');
      onVariablesChange('x,y,z');
      onInputChange('x+y+z=0; x-y=0; y-z=0');
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
    else if (action === 'plus') mathField.write('+');
    else if (action === 'minus') mathField.write('-');
    else if (action === 'times') mathField.write('\\cdot ');
    else if (action === 'divide') mathField.write('/');
  }

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Bộ giải đại số</span>
        <h2>Nhập bài toán</h2>
        <p>Gõ tiếng Việt tự nhiên hoặc nhập trực tiếp công thức; hệ thống sẽ diễn giải, giải và kiểm chứng kết quả.</p>
      </div>

      <div className="algebra-mode-tabs" role="tablist" aria-label="Chế độ nhập">
        <button type="button" className={inputMode === 'natural' ? 'active' : ''} onClick={() => { onInputModeChange('natural'); onInputFormatChange('auto'); }} disabled={loading}>Tiếng Việt</button>
        <button type="button" className={inputMode === 'math' ? 'active' : ''} onClick={() => { onInputModeChange('math'); onInputFormatChange('latex'); }} disabled={loading}>Công thức</button>
      </div>

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
              {group.label}
            </button>
          ))}
        </div>
        <div className="algebra-snippet-grid" role="tabpanel">
          {MATH_SNIPPET_GROUPS[activeSnippetGroup].items.map((snippet) => (
            <button type="button" key={snippet.title} title={snippet.title} aria-label={snippet.title} onClick={() => insertMathSnippet(snippet.action)} disabled={loading}>{snippet.label}</button>
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
            <option value="combinatorics_probability">Tổ hợp-xác suất</option>
            <option value="parameter">Tham số</option>
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
      </div>

      <label className="field-label">
        Biến cần giải
        <input
          value={variables}
          onChange={(event) => onVariablesChange(event.target.value)}
          placeholder="x hoặc x,y hoặc z"
          disabled={loading}
        />
      </label>

      <button type="button" className="auth-primary-button algebra-submit" onClick={onSubmit} disabled={loading || !input.trim()}>
        {loading ? 'Đang giải...' : 'Giải bài'}
      </button>
    </section>
  );
}
