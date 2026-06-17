import { useState } from 'react';
import type { AlgebraSolveStep } from '../../api/client';
import { KatexSpan, MixedTextRenderer } from '../KatexSpan';

export function AlgebraStepList({ steps, isSubStep = false }: { steps: AlgebraSolveStep[], isSubStep?: boolean }) {
  if (!steps || steps.length === 0) return null;
  return (
    <div className={`algebra-step-list ${isSubStep ? 'algebra-sub-step-list' : ''}`}>
      {steps.map((step, idx) => (
        <AlgebraStepCard key={step.index || idx} step={step} isSubStep={isSubStep} />
      ))}
    </div>
  );
}

function AlgebraStepCard({ step, isSubStep }: { step: AlgebraSolveStep, isSubStep: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasSubSteps = step.sub_steps && step.sub_steps.length > 0;

  return (
    <article className={`algebra-step-card ${isSubStep ? 'sub-step' : ''}`}>
      <div 
        className="algebra-step-head" 
        onClick={() => hasSubSteps && setIsExpanded(!isExpanded)} 
        style={{ cursor: hasSubSteps ? 'pointer' : 'default' }}
      >
        <span className="algebra-step-index">{step.index}</span>
        <div style={{ flex: 1 }}>
          <strong>{step.title}</strong>
          {(step.method || step.rule) && (
            <span className="algebra-step-rule">
              <MixedTextRenderer text={step.rule || step.method || ''} />
            </span>
          )}
        </div>
        {hasSubSteps && (
          <button className="algebra-accordion-toggle" aria-expanded={isExpanded}>
            {isExpanded ? '▲ Thu gọn' : '▼ Chi tiết'}
          </button>
        )}
      </div>

      <div className="algebra-step-body">
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
        {step.explanation && (
          <p><MixedTextRenderer text={step.short_explanation || step.explanation} /></p>
        )}

        {hasSubSteps && isExpanded && (
          <div className="algebra-nested-steps" style={{ marginTop: '1rem', paddingLeft: '1rem', borderLeft: '2px dashed var(--surface-1)' }}>
             <AlgebraStepList steps={step.sub_steps!} isSubStep={true} />
          </div>
        )}
      </div>
    </article>
  );
}

function FormulaLines({ tex }: { tex: string }) {
  const lines = splitFormulaLines(tex);
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

function splitFormulaLines(tex: string) {
  const normalized = tex
    .replace(/^\\begin\{aligned\}/, '')
    .replace(/\\end\{aligned\}$/, '')
    .replace(/\\\\/g, '\n');
  return normalized.split('\n').map((line) => line.trim()).filter(Boolean);
}
