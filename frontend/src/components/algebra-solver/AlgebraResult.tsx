import type { AlgebraSolveResponse } from '../../api/client';
import { KatexSpan } from '../KatexSpan';
import { AlgebraStepList } from './AlgebraStepList';

export function EmptyAlgebraResult() {
  return (
    <div className="algebra-empty-result">
      <EmptyResultIllustration />
      <strong>Kết quả sẽ hiện ở đây</strong>
      <span>Nhập bài toán ở cột trái để xem lời giải và báo cáo kiểm chứng.</span>
    </div>
  );
}

export function AlgebraLoadingResult() {
  return (
    <div className="algebra-empty-result" aria-live="polite" aria-busy="true">
      <EmptyResultIllustration />
      <strong>Đang giải bài toán...</strong>
      <span>Đang lập lời giải từng bước và kiểm tra lại kết quả.</span>
    </div>
  );
}

export function AlgebraResult({ result }: { result: AlgebraSolveResponse }) {
  const assumptions = result.assumptions.filter(hasText);
  const notices = [...result.warnings, ...result.errors].filter((item) => hasText(item) && !isRoutineInterpretationNotice(item));
  const checks = result.verification.checks.filter((check) => (
    check.status !== 'pass'
    && (hasText(check.name) || hasText(check.detail) || hasText(check.latex))
  ));
  const steps = result.steps.filter((step) => (
    step.kind !== 'conclusion'
    && (
      hasText(step.title)
      || hasText(step.explanation)
      || hasText(step.goal)
      || hasText(step.why)
      || hasText(step.rule)
      || hasText(step.operation)
      || hasText(step.before_latex)
      || hasText(step.after_latex)
      || hasText(step.expression_latex)
      || hasText(step.result_latex)
      || hasText(step.pitfall)
      || hasText(step.check)
    )
  ));

  return (
    <section className="algebra-result-panel">
      <div className="algebra-result-header">
        <div>
          <span className="algebra-eyebrow">{compactMeta(result.topic, result.problem_type)}</span>
          <h2>{statusTitle(result.status)}</h2>
        </div>
      </div>

      {(hasText(result.answer_latex) || hasText(result.answer)) && (
        <section className="algebra-result-card algebra-answer-card">
          <span className="algebra-eyebrow">Đáp án</span>
          {result.answer_latex ? (
            <KatexSpan tex={result.answer_latex} display className="algebra-answer-katex" />
          ) : (
            <strong className="algebra-answer-text">{result.answer}</strong>
          )}
        </section>
      )}

      {(assumptions.length > 0 || notices.length > 0) && (
        <div className="algebra-result-grid">
          {assumptions.length > 0 && (
            <section className="algebra-result-card">
              <SectionTitle title="Điều kiện/giả thiết" />
              <InfoList items={assumptions} />
            </section>
          )}
          {notices.length > 0 && (
            <section className="algebra-result-card">
              <SectionTitle title="Cảnh báo" />
              <InfoList items={notices} />
            </section>
          )}
        </div>
      )}

      {checks.length > 0 && (
        <section className="algebra-result-card">
          <SectionTitle title="Kiểm tra lại" />
          <div className="algebra-check-list">
            {checks.map((check, index) => (
              <article className={`algebra-check ${check.status}`} key={`${check.name}-${index}`}>
                {hasText(check.name) && <strong>{verificationCheckLabel(check.name)}</strong>}
                {hasText(check.detail) && <span>{check.detail}</span>}
                {check.latex && <KatexSpan tex={check.latex} className="algebra-katex" />}
              </article>
            ))}
          </div>
        </section>
      )}

      {steps.length > 0 && (
        <section className="algebra-result-card">
          <SectionTitle title="Các bước giải" />
          <AlgebraStepList steps={steps} />
        </section>
      )}
    </section>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h3>{title}</h3>;
}

function InfoList({ items }: { items: string[] }) {
  return (
    <ul className="algebra-info-list">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

function EmptyResultIllustration() {
  return (
    <svg className="algebra-empty-illustration" viewBox="0 0 160 120" role="img" aria-label="Minh họa bảng lời giải">
      <rect x="24" y="18" width="112" height="84" rx="8" />
      <path d="M42 42h72M42 60h38M42 78h58" />
      <circle cx="116" cy="76" r="14" />
      <path d="m109 76 5 5 11-13" />
      <path d="M30 32h112M52 18v84M80 18v84M108 18v84M24 46h112M24 74h112" className="grid-lines" />
    </svg>
  );
}

function compactMeta(topic: string, problemType: string) {
  return [topic, problemType].filter(hasText).join(' · ');
}

function hasText(value: string | null | undefined) {
  return typeof value === 'string' && value.trim().length > 0;
}

function isRoutineInterpretationNotice(value: string) {
  return value.includes('Đã diễn giải đề tiếng Việt thành biểu thức chuẩn trước khi giải.')
    || value.includes('Đầu vào gồm cả mô tả tự nhiên và ký hiệu toán; hệ thống ưu tiên phần biểu thức được trích xuất.');
}

function verificationCheckLabel(name: string) {
  const labels: Record<string, string> = {
    empty_solution_set: 'Không có nghiệm để thử lại',
    symbolic_solution_set: 'Kiểm tra tập nghiệm',
    candidate_substitution: 'Thay nghiệm vào đề gốc',
    domain_constraints_valid: 'Kiểm tra điều kiện xác định',
    inequality_sample: 'Thử điểm trong khoảng nghiệm',
  };
  return labels[name] || name.replace(/_/g, ' ');
}

function statusTitle(status: AlgebraSolveResponse['status']) {
  if (status === 'solved') return 'Đã giải được';
  if (status === 'partial') return 'Kết quả một phần';
  if (status === 'unsupported') return 'Chưa hỗ trợ dạng này';
  return 'Không thể giải';
}
