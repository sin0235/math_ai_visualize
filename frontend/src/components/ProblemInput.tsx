import { FormEvent, useState } from 'react';

const examples = [
  'Cho A(1,2), B(4,5). Vẽ đường thẳng AB.',
  'Vẽ đồ thị hàm số y = x^2 - 2x + 1.',
  'Cho hình chóp S.ABCD có đáy ABCD là hình vuông, SA vuông góc với mặt phẳng đáy.',
];

interface ProblemInputProps {
  loading: boolean;
  onSubmit: (problemText: string, preferredAiProvider?: string) => void;
}

export function ProblemInput({ loading, onSubmit }: ProblemInputProps) {
  const [problemText, setProblemText] = useState(examples[0]);
  const [preferredAiProvider, setPreferredAiProvider] = useState('auto');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(problemText, preferredAiProvider);
  }

  return (
    <form className="panel problem-form" onSubmit={handleSubmit}>
      <div className="panel-title">Nhập đề bài</div>
      <textarea
        value={problemText}
        onChange={(event) => setProblemText(event.target.value)}
        rows={8}
        placeholder="Nhập đề toán cần dựng hình..."
      />
      <label className="field-label">
        Model
        <select value={preferredAiProvider} onChange={(event) => setPreferredAiProvider(event.target.value)}>
          <option value="auto">Tự động fallback</option>
          <option value="nvidia">NVIDIA DeepSeek V3.1 Terminus</option>
          <option value="nvidia_v4_flash">NVIDIA DeepSeek V4 Flash</option>
          <option value="nvidia_kimi_k2">NVIDIA Kimi K2 Thinking</option>
          <option value="openrouter">OpenRouter Nemotron</option>
          <option value="openrouter_gpt_oss">OpenRouter GPT OSS 120B</option>
          <option value="mock">Mock extractor</option>
        </select>
      </label>
      <button disabled={loading || !problemText.trim()} type="submit">
        {loading ? 'Đang dựng hình...' : 'Dựng hình'}
      </button>
      <div className="examples">
        {examples.map((example) => (
          <button key={example} type="button" onClick={() => setProblemText(example)}>
            {example}
          </button>
        ))}
      </div>
    </form>
  );
}
