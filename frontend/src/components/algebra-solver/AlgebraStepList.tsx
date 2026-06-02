import type { AlgebraSolveStep } from '../../api/client';
import { KatexSpan } from '../KatexSpan';

export function AlgebraStepList({ steps }: { steps: AlgebraSolveStep[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="algebra-step-list">
      {steps.map((step) => (
        <article className="algebra-step-card" key={step.index}>
          <div className="algebra-step-head">
            <span className="algebra-step-index">{step.index}</span>
            <div>
              <strong>{step.title}</strong>
            </div>
          </div>
          {(step.before_latex || step.after_latex) && (
            <div className="algebra-transform-row" aria-label="Biến đổi trong bước này">
              {step.before_latex && (
                <div>
                  <FormulaLines tex={step.before_latex} />
                </div>
              )}
              {step.before_latex && step.after_latex && <span className="algebra-transform-arrow" aria-hidden="true">↓</span>}
              {step.after_latex && (
                <div>
                  <FormulaLines tex={step.after_latex} />
                </div>
              )}
            </div>
          )}
          {!step.before_latex && !step.after_latex && step.expression_latex && (
            <div className="algebra-formula-row">
              <FormulaLines tex={step.expression_latex} />
            </div>
          )}
          {!step.after_latex && step.result_latex && (
            step.kind === 'conclusion' ? null : (
              <div className="algebra-formula-row">
                <FormulaLines tex={step.result_latex} />
              </div>
            )
          )}
          <p>{step.explanation}</p>
        </article>
      ))}
    </div>
  );
}

function FormulaLines({ tex }: { tex: string }) {
  const lines = tex.split('\n').map((line) => line.trim()).filter(Boolean);
  return (
    <div className="algebra-formula-lines">
      {lines.map((line, index) => (
        <div className="algebra-formula-line" key={`${line}-${index}`}>
          <KatexSpan tex={line} className="algebra-katex" />
        </div>
      ))}
    </div>
  );
}
