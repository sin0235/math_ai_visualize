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
            <strong>{step.title}</strong>
          </div>
          <p>{step.explanation}</p>
          {step.expression_latex && (
            <div className="algebra-formula-row">
              <span>Công thức</span>
              <KatexSpan tex={step.expression_latex} className="algebra-katex" />
            </div>
          )}
          {step.result_latex && (
            <div className="algebra-formula-row">
              <span>Kết quả</span>
              <KatexSpan tex={step.result_latex} className="algebra-katex" />
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
