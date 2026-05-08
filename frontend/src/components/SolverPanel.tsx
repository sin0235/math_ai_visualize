import { useRef, useState } from 'react';
import { solveProblem, type SolveResponse, type SolveStep } from '../api/client';
import type { RuntimeSettings } from '../types/settings';
import type { MathScene } from '../types/scene';
import { KatexSpan, sympyToLatex } from './KatexSpan';

interface SolverPanelProps {
  scene: MathScene;
  runtimeSettings?: RuntimeSettings;
  onHighlight: (names: string[]) => void;
}

function buildExamples(scene: MathScene) {
  const pointNames = scene.objects
    .filter((obj): obj is Extract<MathScene['objects'][number], { type: 'point_3d' | 'point_2d' }> => obj.type === 'point_3d' || obj.type === 'point_2d')
    .map((point) => point.name);
  const face = scene.objects.find((obj): obj is Extract<MathScene['objects'][number], { type: 'face' }> => obj.type === 'face' && obj.points.length >= 3);
  const base = face?.points ?? pointNames.slice(0, 4);
  const apex = pointNames.find((name) => !base.includes(name)) ?? pointNames[0];
  const edge = base.length >= 2 ? `${base[0]}${base[1]}` : '';
  const secondEdge = base.length >= 4 ? `${base[2]}${base[3]}` : edge;
  const plane = base.length >= 3 ? `(${base.join('')})` : '';
  const examples = [
    pointNames.length >= 2 ? `d(${pointNames[0]},${pointNames[1]})` : '',
    apex && edge && !edge.includes(apex) ? `d(${apex},${edge})` : '',
    apex && plane && !base.includes(apex) ? `d(${apex},${plane})` : '',
    edge && secondEdge && edge !== secondEdge ? `Góc giữa ${edge} và ${secondEdge}` : '',
    apex && edge && plane && !base.includes(apex) ? `Góc giữa ${apex}${base[0]} và ${plane}` : '',
    base.length >= 3 ? `S(${base.join('')})` : '',
    apex && base.length >= 3 && !base.includes(apex) ? `V(${apex}.${base.join('')})` : '',
  ].filter(Boolean);
  return Array.from(new Set(examples));
}

export function SolverPanel({ scene, runtimeSettings, onHighlight }: SolverPanelProps) {
  const examples = buildExamples(scene);
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
      const res = await solveProblem(scene, question.trim(), runtimeSettings);
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
          <div className="sp-header-sub">Click vào bước để highlight trên hình</div>
        </div>
      </div>

      {/* Input */}
      <div className="sp-input-wrap">
        <input
          ref={inputRef}
          id="solver-question-input"
          className="sp-input"
          type="text"
          placeholder="Nhập câu hỏi, ví dụ: d(A,(BCD))"
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
        {examples.map((q) => (
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
                      {step.formula_latex && (
                        <div className="sp-step-formula">
                          <span>Công thức: </span>
                          <KatexSpan tex={step.formula_latex} />
                        </div>
                      )}
                      {step.substitution_latex && (
                        <div className="sp-step-formula">
                          <span>Thế số: </span>
                          <KatexSpan tex={step.substitution_latex} />
                        </div>
                      )}
                      {step.result_latex && (
                        <div className="sp-step-result">
                          <span>Kết quả: </span>
                          <KatexSpan tex={step.result_latex} />
                        </div>
                      )}
                      {!step.formula_latex && step.expression && (
                        <div className="sp-step-formula">
                          <KatexSpan tex={sympyToLatex(step.expression)} />
                        </div>
                      )}
                      {!step.result_latex && step.result && (
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
