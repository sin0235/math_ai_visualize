import { useRef, useState } from 'react';
import { solveProblem, type SolveResponse, type SolveStep } from '../api/client';
import type { MathScene } from '../types/scene';
import { KatexSpan, sympyToLatex } from './KatexSpan';

interface SolverPanelProps {
  scene: MathScene;
  onHighlight: (names: string[]) => void;
}

const EXAMPLES = [
  'Tính khoảng cách AB',
  'Tính góc ABC',
  'Tính diện tích ABCD',
  'AB vuông góc CD?',
  'AB song song CD?',
  'Thể tích ABCD',
];

export function SolverPanel({ scene, onHighlight }: SolverPanelProps) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSolve() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveStep(null);
    onHighlight([]);
    try {
      const res = await solveProblem(scene, question.trim());
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi không xác định.');
    } finally {
      setLoading(false);
    }
  }

  function handleStepClick(step: SolveStep) {
    if (activeStep === step.index) {
      setActiveStep(null);
      onHighlight([]);
    } else {
      setActiveStep(step.index);
      onHighlight(step.highlight);
    }
  }

  return (
    <div className="sp-panel">
      {/* Header */}
      <div className="sp-header">
        <div className="sp-header-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </div>
        <div>
          <div className="sp-header-title">Giải toán từng bước</div>
          <div className="sp-header-sub">Click vào bước → highlight trên hình 3D</div>
        </div>
      </div>

      {/* Input */}
      <div className="sp-input-wrap">
        <input
          ref={inputRef}
          id="solver-question-input"
          className="sp-input"
          type="text"
          placeholder="Nhập câu hỏi, ví dụ: Tính khoảng cách AB"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') void handleSolve(); }}
          disabled={loading}
          autoComplete="off"
        />
        <button
          id="solver-submit-btn"
          type="button"
          className="sp-btn-primary"
          onClick={() => void handleSolve()}
          disabled={loading || !question.trim()}
          aria-label="Giải toán"
        >
          {loading
            ? <span className="sp-spinner" aria-hidden="true" />
            : <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
          }
        </button>
      </div>

      {/* Example chips */}
      <div className="sp-chips">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            className="sp-chip"
            onClick={() => { setQuestion(q); inputRef.current?.focus(); }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="sp-error" role="alert">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="sp-result">
          {/* Answer */}
          <div className="sp-answer">
            <span className="sp-answer-label">Kết quả</span>
            <span className="sp-answer-value">{result.answer}</span>
          </div>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="sp-warnings">
              {result.warnings.map((w, i) => <div key={i} className="sp-warning">{w}</div>)}
            </div>
          )}

          {/* Steps */}
          {result.steps.length > 0 && (
            <div className="sp-steps">
              <div className="sp-steps-meta">
                {result.steps.length} bước giải
              </div>
              {result.steps.map((step) => {
                const isActive = activeStep === step.index;
                return (
                  <button
                    key={step.index}
                    type="button"
                    id={`solver-step-${step.index}`}
                    className={`sp-step${isActive ? ' sp-step--on' : ''}`}
                    onClick={() => handleStepClick(step)}
                    aria-pressed={isActive}
                  >
                    {/* Step number line */}
                    <div className="sp-step-num-col">
                      <span className="sp-step-num">{step.index}</span>
                      {step.index < result.steps.length && <span className="sp-step-line" aria-hidden="true" />}
                    </div>

                    {/* Content */}
                    <div className="sp-step-content">
                      <div className="sp-step-head">
                        <span className="sp-step-title">{step.title}</span>
                        {step.highlight.length > 0 && (
                          <span className="sp-step-tag" title="Các điểm được highlight">
                            {step.highlight.join(' · ')}
                          </span>
                        )}
                      </div>
                      <p className="sp-step-text">{step.explanation}</p>
                      {step.expression && (
                        <div className="sp-step-formula">
                          <KatexSpan tex={sympyToLatex(step.expression)} />
                        </div>
                      )}
                      {step.result && (
                        <div className="sp-step-result">
                          <KatexSpan tex={`= ${sympyToLatex(step.result)}`} />
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
