import type { AlgebraTopic } from '../../api/client';

type AlgebraDomain = 'R' | 'C' | 'N' | 'Z';

type AlgebraExample = {
  label: string;
  input: string;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
};

const EXAMPLES: AlgebraExample[] = [
  { label: 'Phương trình bậc hai', input: 'x^2 - 5*x + 6 = 0', topic: 'equation', domain: 'R', variables: 'x' },
  { label: 'Bất phương trình', input: '(x-1)/(x+2) < 0', topic: 'inequality', domain: 'R', variables: 'x' },
  { label: 'Mũ', input: '2^(x+1)=8', topic: 'exponential_log', domain: 'R', variables: 'x' },
  { label: 'Log', input: 'log(x,2)+log(x-2,2)=3', topic: 'exponential_log', domain: 'R', variables: 'x' },
  { label: 'Lượng giác', input: 'sin(x)=1/2', topic: 'trigonometry', domain: 'R', variables: 'x' },
  { label: 'Số phức', input: 'z^2 + 1 = 0', topic: 'complex', domain: 'C', variables: 'z' },
  { label: 'Module số phức', input: 'Abs(3+4*i)', topic: 'complex', domain: 'C', variables: 'z' },
  { label: 'Hệ tuyến tính', input: 'x+y=3; x-y=1', topic: 'system', domain: 'R', variables: 'x,y' },
];

export function AlgebraInput({
  input,
  topic,
  domain,
  variables,
  loading,
  onInputChange,
  onTopicChange,
  onDomainChange,
  onVariablesChange,
  onSubmit,
}: {
  input: string;
  topic: AlgebraTopic;
  domain: AlgebraDomain;
  variables: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onTopicChange: (value: AlgebraTopic) => void;
  onDomainChange: (value: AlgebraDomain) => void;
  onVariablesChange: (value: string) => void;
  onSubmit: () => void;
}) {
  function applyExample(example: AlgebraExample) {
    onInputChange(example.input);
    onTopicChange(example.topic);
    onDomainChange(example.domain);
    onVariablesChange(example.variables);
  }

  return (
    <section className="algebra-input-panel">
      <div className="algebra-panel-heading">
        <span>Solver Đại số C3</span>
        <h2>Giải đại số có kiểm chứng</h2>
        <p>Hỗ trợ phương trình, bất phương trình, mũ-log, lượng giác, số phức và hệ phương trình bằng pipeline symbolic-first.</p>
      </div>
      <label className="field-label">
        Nhập bài toán
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Ví dụ: x^2 - 5*x + 6 = 0"
          rows={5}
          disabled={loading}
        />
      </label>
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
        {loading ? 'Đang giải...' : 'Giải và kiểm chứng'}
      </button>
    </section>
  );
}
