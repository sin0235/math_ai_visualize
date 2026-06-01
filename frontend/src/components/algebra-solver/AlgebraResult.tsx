import type { AlgebraSolveResponse } from '../../api/client';
import { KatexSpan } from '../KatexSpan';
import { AlgebraStepList } from './AlgebraStepList';
import { AlgebraVerificationBadge } from './AlgebraVerificationBadge';

export function EmptyAlgebraResult() {
  return (
    <div className="algebra-empty-result">
      <strong>Kết quả sẽ hiện ở đây</strong>
      <span>Nhập phương trình hoặc bất phương trình ở cột trái để xem lời giải và báo cáo kiểm chứng.</span>
    </div>
  );
}

export function AlgebraLoadingResult() {
  return (
    <div className="algebra-empty-result" aria-live="polite" aria-busy="true">
      <strong>Đang giải bài toán...</strong>
      <span>Hệ thống đang chạy solver symbolic và verifier.</span>
    </div>
  );
}

export function AlgebraResult({ result }: { result: AlgebraSolveResponse }) {
  return (
    <section className="algebra-result-panel">
      <div className="algebra-result-header">
        <div>
          <span>{result.topic} · {result.problem_type}</span>
          <h2>{statusTitle(result.status)}</h2>
        </div>
        <AlgebraVerificationBadge status={result.verification.status} />
      </div>

      <div className="algebra-result-card algebra-answer-card">
        <span>Đáp án</span>
        {result.answer_latex ? <KatexSpan tex={result.answer_latex} display className="algebra-answer-katex" /> : <strong>{result.answer}</strong>}
        <p>{result.answer}</p>
      </div>

      {result.input_interpretation && (
        <section className="algebra-result-card algebra-interpretation-card">
          <span>Input interpretation</span>
          <h3>Hệ thống hiểu đề bài như sau</h3>
          <KatexSpan tex={result.input_interpretation.canonical_input} className="algebra-katex" />
          <div className="algebra-interpretation-chips">
            {result.input_interpretation.chips.map((chip) => (
              <span key={`${chip.kind}-${chip.label}-${chip.value}`} title={chip.value}>{chip.label}: {chip.value}</span>
            ))}
          </div>
        </section>
      )}

      <div className="algebra-result-grid">
        <InfoList title="Điều kiện/giả thiết" items={result.assumptions} empty="Chưa phát hiện điều kiện đặc biệt." />
        <InfoList title="Cảnh báo" items={[...result.warnings, ...result.errors]} empty="Không có cảnh báo." />
      </div>

      <section className="algebra-result-card">
        <h3>Kiểm tra lại</h3>
        <div className="algebra-check-list">
          {result.verification.checks.length === 0 ? <span>Không có check chi tiết.</span> : result.verification.checks.map((check, index) => (
            <article className={`algebra-check ${check.status}`} key={`${check.name}-${index}`}>
              <strong>{check.name}</strong>
              <span>{check.detail}</span>
              {check.latex && <KatexSpan tex={check.latex} className="algebra-katex" />}
            </article>
          ))}
        </div>
      </section>

      <section className="algebra-result-card">
        <h3>Các bước giải</h3>
        <AlgebraStepList steps={result.steps} />
      </section>
    </section>
  );
}

function InfoList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <section className="algebra-result-card">
      <h3>{title}</h3>
      {items.length > 0 ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{empty}</p>}
    </section>
  );
}

function statusTitle(status: AlgebraSolveResponse['status']) {
  if (status === 'solved') return 'Đã giải được';
  if (status === 'partial') return 'Kết quả một phần';
  if (status === 'unsupported') return 'Chưa hỗ trợ dạng này';
  return 'Không thể giải';
}
