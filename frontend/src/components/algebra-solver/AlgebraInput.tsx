import { useMemo } from 'react';
import { addStyles, EditableMathField } from 'react-mathquill';
import type { AlgebraInputFormat, AlgebraTopic } from '../../api/client';
import { KatexSpan } from '../KatexSpan';

addStyles();

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';
export type AlgebraInputMode = 'natural' | 'math';

type AlgebraExample = {
  label: string;
  input: string;
  mode: AlgebraInputMode;
  inputFormat: AlgebraInputFormat;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
};

const EXAMPLES: AlgebraExample[] = [
  { label: 'Tiếng Việt', input: 'Giải phương trình x bình phương - 5x + 6 bằng 0', mode: 'natural', inputFormat: 'auto', topic: 'auto', domain: 'R', variables: 'x' },
  { label: 'Phương trình bậc hai', input: 'x^2 - 5x + 6 = 0', mode: 'math', inputFormat: 'latex', topic: 'equation', domain: 'R', variables: 'x' },
  { label: 'Bất phương trình', input: '\\frac{x-1}{x+2}<0', mode: 'math', inputFormat: 'latex', topic: 'inequality', domain: 'R', variables: 'x' },
  { label: 'Mũ', input: '2^{x+1}=8', mode: 'math', inputFormat: 'latex', topic: 'exponential_log', domain: 'R', variables: 'x' },
  { label: 'Log', input: '\\log_2(x)+\\log_2(x-2)=3', mode: 'math', inputFormat: 'latex', topic: 'exponential_log', domain: 'R', variables: 'x' },
  { label: 'Lượng giác', input: '\\sin(x)=\\frac{1}{2}', mode: 'math', inputFormat: 'latex', topic: 'trigonometry', domain: 'R', variables: 'x' },
  { label: 'Số phức', input: 'z^2 + 1 = 0', mode: 'math', inputFormat: 'latex', topic: 'complex', domain: 'C', variables: 'z' },
  { label: 'Hệ tuyến tính', input: 'x+y=3; x-y=1', mode: 'natural', inputFormat: 'auto', topic: 'system', domain: 'R', variables: 'x,y' },
  { label: 'Tổ hợp', input: 'C(10,3)', mode: 'natural', inputFormat: 'plain', topic: 'combinatorics_probability', domain: 'N', variables: 'n,k' },
  { label: 'Chỉnh hợp', input: 'A(5,2)', mode: 'natural', inputFormat: 'plain', topic: 'combinatorics_probability', domain: 'N', variables: 'n,k' },
  { label: 'Hệ số nhị thức', input: 'coefficient((1+x)^5,x,3)', mode: 'natural', inputFormat: 'plain', topic: 'combinatorics_probability', domain: 'N', variables: 'x' },
  { label: 'Cấp số cộng', input: 'arithmetic(u1=2,d=3,n=10)', mode: 'natural', inputFormat: 'plain', topic: 'sequence', domain: 'R', variables: 'n' },
  { label: 'Tổng cấp số nhân', input: 'geometric_sum(u1=3,q=2,n=5)', mode: 'natural', inputFormat: 'plain', topic: 'sequence', domain: 'R', variables: 'n' },
  { label: 'Tham số nghiệm kép', input: 'quadratic_double_root(a=1,b=-2*m,c=1,var=x,param=m)', mode: 'natural', inputFormat: 'plain', topic: 'parameter', domain: 'R', variables: 'x' },
  { label: 'Tham số dương mọi x', input: 'quadratic_positive_all(a=1,b=m,c=1,var=x,param=m)', mode: 'natural', inputFormat: 'plain', topic: 'parameter', domain: 'R', variables: 'x' },
];

const MATH_SNIPPETS = [
  { label: 'Phân số', value: '\\frac{}{}' },
  { label: 'Căn', value: '\\sqrt{}' },
  { label: 'Lũy thừa', value: '^{}' },
  { label: 'Log cơ số', value: '\\log_{}()' },
  { label: 'Sin', value: '\\sin()' },
  { label: '≤', value: '\\le ' },
  { label: '≥', value: '\\ge ' },
  { label: 'Hệ 2 ẩn', value: 'x+y=0; x-y=0' },
];

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
  function applyExample(example: AlgebraExample) {
    onInputChange(example.input);
    onInputModeChange(example.mode);
    onInputFormatChange(example.inputFormat);
    onTopicChange(example.topic);
    onDomainChange(example.domain);
    onVariablesChange(example.variables);
  }

  function insertMathSnippet(snippet: string) {
    onInputModeChange('math');
    onInputFormatChange('latex');
    const separator = input && !/[\s;]$/.test(input) && !snippet.startsWith('^') ? ' ' : '';
    onInputChange(`${input}${separator}${snippet}`);
  }

  const previewTex = useMemo(() => input.trim(), [input]);

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Math Input</span>
        <h2>Nhập như WolframAlpha</h2>
        <p>Gõ tiếng Việt tự nhiên hoặc nhập trực tiếp công thức bằng các ô toán học; hệ thống sẽ diễn giải rồi giải bằng symbolic solver có kiểm chứng.</p>
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
            className="algebra-math-field"
          />
        </div>
      ) : (
        <label className="field-label">
          Nhập bài toán
          <textarea
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            placeholder="Ví dụ: Giải phương trình x bình phương - 5x + 6 bằng 0"
            rows={5}
            disabled={loading}
          />
        </label>
      )}

      <div className="algebra-math-toolbar" aria-label="Chèn ô công thức">
        {MATH_SNIPPETS.map((snippet) => (
          <button type="button" key={snippet.label} onClick={() => insertMathSnippet(snippet.value)} disabled={loading}>{snippet.label}</button>
        ))}
      </div>

      {inputMode === 'math' && previewTex && (
        <div className="algebra-input-preview">
          <span>Preview · {inputFormat}</span>
          <KatexSpan tex={previewTex} className="algebra-katex" />
        </div>
      )}

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
          placeholder="Ví dụ: x hoặc x,y hoặc z"
          disabled={loading}
        />
      </label>

      <div className="algebra-examples" aria-label="Ví dụ nhanh">
        {EXAMPLES.map((example) => (
          <button type="button" key={example.label} onClick={() => applyExample(example)} disabled={loading} title={example.input}>{example.label}</button>
        ))}
      </div>

      <button type="button" className="auth-primary-button algebra-submit" onClick={onSubmit} disabled={loading || !input.trim()}>
        {loading ? 'Đang giải...' : 'Diễn giải, giải và kiểm chứng'}
      </button>
    </section>
  );
}
