import { useState } from 'react';
import { downloadAlgebraPdf, type AlgebraSolveResponse, type AlgebraVerificationCheck } from '../../api/client';
import { KatexSpan, MixedTextRenderer } from '../KatexSpan';
import { AlgebraStepList } from './AlgebraStepList';
import { MathCapabilitySummary } from '../MathCapabilitySummary';

const ANALYZER_PREFILL_KEY = 'math_ai_analyzer_prefill';

export function EmptyAlgebraResult() {
  return (
    <div className="algebra-empty-result">
      <div className="algebra-empty-card">
        <p className="algebra-empty-eyebrow">Không gian lời giải</p>
        <EmptyResultIllustration />
        <strong>Kết quả sẽ hiện ở đây</strong>
        <span>Nhập bài toán ở cột trái để nhận lời giải có cấu trúc và kiểm chứng.</span>
        <ul className="algebra-empty-features" aria-label="Nội dung kết quả">
          <li>Lời giải từng bước</li>
          <li>Đáp án chính xác</li>
          <li>Báo cáo kiểm chứng</li>
        </ul>
      </div>
    </div>
  );
}

export function AlgebraLoadingResult({
  elapsedSeconds = 0,
  onCancel,
}: {
  elapsedSeconds?: number;
  onCancel?: () => void;
}) {
  return (
    <div className="algebra-empty-result" aria-live="polite" aria-busy="true">
      <EmptyResultIllustration />
      <strong>Đang giải bài toán...</strong>
      <span>
        Đang lập lời giải từng bước và kiểm tra lại kết quả
        {elapsedSeconds > 0 ? ` · ${elapsedSeconds}s` : ''}.
        Có thể mất tới ~15 giây.
      </span>
      {onCancel && (
        <button type="button" className="algebra-action-btn" onClick={onCancel}>
          Hủy chờ
        </button>
      )}
    </div>
  );
}

export function AlgebraResult({
  result,
  stale = false,
  onApplyCanonical,
}: {
  result: AlgebraSolveResponse;
  stale?: boolean;
  onApplyCanonical?: (canonical: string) => void;
}) {
  const [copyFeedback, setCopyFeedback] = useState('');
  const [showAllChecks, setShowAllChecks] = useState(false);
  const assumptions = result.assumptions.filter(hasText);
  const notices = [...result.warnings, ...result.errors].filter((item) => hasText(item) && !isRoutineInterpretationNotice(item));
  const allChecks = result.verification.checks.filter((check) => hasText(check.name) || hasText(check.detail) || hasText(check.latex));
  const failWarnChecks = allChecks.filter((check) => check.status !== 'pass');
  const visibleChecks = showAllChecks ? allChecks : failWarnChecks;
  const passCount = allChecks.filter((check) => check.status === 'pass').length;
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
  const interpretation = result.input_interpretation;
  const analyzerExpression = expressionForAnalyzer(result);

  async function copyText(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback(`Đã copy ${label}`);
      window.setTimeout(() => setCopyFeedback(''), 2000);
    } catch {
      setCopyFeedback('Không copy được (trình duyệt chặn clipboard)');
      window.setTimeout(() => setCopyFeedback(''), 2500);
    }
  }

  function openAnalyzer() {
    if (!analyzerExpression) return;
    try {
      sessionStorage.setItem(ANALYZER_PREFILL_KEY, analyzerExpression);
    } catch {
      // ignore storage failures
    }
    window.history.pushState({}, document.title, '/analyzer');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  return (
    <section className={`algebra-result-panel ${stale ? 'is-stale' : ''}`}>
      <div className="algebra-result-header">
        <div>
          <span className="algebra-eyebrow">{compactMeta(result.topic, result.problem_type)}</span>
          <h2>{statusTitle(result.status)}</h2>
          {stale && (
            <span className="algebra-stale-badge" role="status">
              Kết quả của đề trước — nhấn Giải bài để cập nhật
            </span>
          )}
        </div>
        <div className="algebra-result-actions">
          {(hasText(result.answer_latex) || hasText(result.answer)) && (
            <>
              <button type="button" className="algebra-action-btn" onClick={() => copyText('đáp án', result.answer)}>
                Copy đáp án
              </button>
              {hasText(result.answer_latex) && (
                <button type="button" className="algebra-action-btn" onClick={() => copyText('LaTeX', result.answer_latex || '')}>
                  Copy LaTeX
                </button>
              )}
              <button type="button" className="algebra-action-btn" onClick={() => copyText('Markdown', buildMarkdown(result))}>
                Copy Markdown
              </button>
              <button type="button" className="algebra-action-btn" onClick={() => downloadMarkdown(result)}>
                Tải .md
              </button>
              <button type="button" className="algebra-action-btn" onClick={() => downloadPrintableHtml(result)}>
                Tải HTML/in
              </button>
              <button
                type="button"
                className="algebra-action-btn"
                onClick={() => {
                  void downloadAlgebraPdf(result).catch(() => {
                    setCopyFeedback('Không tải được PDF server');
                    window.setTimeout(() => setCopyFeedback(''), 2500);
                  });
                }}
              >
                Tải PDF (server)
              </button>
            </>
          )}
          {analyzerExpression && (
            <button type="button" className="algebra-action-btn algebra-action-primary" onClick={openAnalyzer}>
              Mở Function Analyzer
            </button>
          )}
        </div>
      </div>
      {copyFeedback && <p className="algebra-copy-feedback" aria-live="polite">{copyFeedback}</p>}

      {(hasText(result.answer_latex) || hasText(result.answer)) && (
        <section className="algebra-result-card algebra-answer-card">
          <span className="algebra-eyebrow">Đáp án</span>
          {result.answer_latex ? (
            <KatexSpan tex={result.answer_latex} display className="algebra-answer-katex" />
          ) : (
            <strong className="algebra-answer-text"><MixedTextRenderer text={result.answer} /></strong>
          )}
          {result.verification.status !== 'skipped' && (
            <span className={`algebra-verify-pill status-${result.verification.status}`}>
              {verificationStatusLabel(result.verification.status)}
            </span>
          )}
        </section>
      )}

      <MathCapabilitySummary solution={result.solution_ir} />

      {steps.length > 0 && (
        <section className="algebra-result-card algebra-solution-steps">
          <SectionTitle title="Các bước giải" />
          <AlgebraStepList steps={steps} />
        </section>
      )}

      {interpretation && (
        <details className="algebra-result-card algebra-result-disclosure">
          <summary>
            <span>Hệ thống hiểu đề</span>
            <small>Thông tin kỹ thuật</small>
          </summary>
          <div className="algebra-result-disclosure-content">
          <dl className="algebra-interpretation-grid">
            <div>
              <dt>Đề gốc</dt>
              <dd><code>{result.input}</code></dd>
            </div>
            <div>
              <dt>Canonical</dt>
              <dd><code>{interpretation.canonical_input}</code></dd>
            </div>
            <div>
              <dt>Nguồn</dt>
              <dd>{sourceLabel(interpretation.source)}</dd>
            </div>
            <div>
              <dt>Định dạng</dt>
              <dd>{interpretation.detected_format}</dd>
            </div>
            <div>
              <dt>Topic gợi ý</dt>
              <dd>{interpretation.topic_hint}</dd>
            </div>
            <div>
              <dt>Miền</dt>
              <dd>{interpretation.domain}</dd>
            </div>
            {interpretation.variables.length > 0 && (
              <div>
                <dt>Biến</dt>
                <dd>{interpretation.variables.join(', ')}</dd>
              </div>
            )}
          </dl>
          {interpretation.chips.length > 0 && (
            <div className="algebra-chip-row">
              {interpretation.chips.map((chip) => (
                <span className="algebra-chip" key={`${chip.kind}-${chip.value}`}>{chip.label}: {chip.value}</span>
              ))}
            </div>
          )}
          {interpretation.warnings.length > 0 && (
            <InfoList items={interpretation.warnings} />
          )}
          {onApplyCanonical && interpretation.canonical_input && interpretation.canonical_input !== result.input && (
            <button
              type="button"
              className="algebra-action-btn"
              onClick={() => onApplyCanonical(interpretation.canonical_input)}
            >
              Đưa canonical vào ô nhập để sửa &amp; giải lại
            </button>
          )}
          </div>
        </details>
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

      {(allChecks.length > 0 || result.verification.status !== 'skipped') && (
        <section className="algebra-result-card">
          <div className="algebra-section-head">
            <SectionTitle title="Kiểm chứng" />
            {allChecks.length > 0 && (
              <span className="algebra-verify-summary">
                {passCount}/{allChecks.length} kiểm tra đạt · {verificationStatusLabel(result.verification.status)}
              </span>
            )}
          </div>
          {result.verification.method.length > 0 && (
            <p className="algebra-verify-method">Phương pháp: {result.verification.method.join(', ')}</p>
          )}
          {visibleChecks.length > 0 && (
            <div className="algebra-check-list">
              {visibleChecks.map((check, index) => (
                <CheckCard check={check} key={`${check.name}-${index}`} />
              ))}
            </div>
          )}
          {allChecks.some((check) => check.status === 'pass') && (
            <button
              type="button"
              className="algebra-action-btn"
              onClick={() => setShowAllChecks((value) => !value)}
            >
              {showAllChecks ? 'Ẩn kiểm tra đã đạt' : 'Hiện tất cả kiểm tra'}
            </button>
          )}
        </section>
      )}

    </section>
  );
}

function CheckCard({ check }: { check: AlgebraVerificationCheck }) {
  return (
    <article className={`algebra-check ${check.status}`}>
      {hasText(check.name) && <strong>{verificationCheckLabel(check.name)}</strong>}
      <span className="algebra-check-status">
        {check.status === 'pass' ? 'Đạt' : check.status === 'fail' ? 'Không đạt' : check.status === 'warn' ? 'Cảnh báo' : 'Bỏ qua'}
      </span>
      {hasText(check.detail) && <span>{check.detail}</span>}
      {check.latex && <KatexSpan tex={check.latex} className="algebra-katex" />}
    </article>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h3>{title}</h3>;
}

function InfoList({ items }: { items: string[] }) {
  return (
    <ul className="algebra-info-list">
      {items.map((item) => <li key={item}><MixedTextRenderer text={item} /></li>)}
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

function downloadMarkdown(result: AlgebraSolveResponse) {
  const text = buildMarkdown(result);
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `algebra-solution-${(result.request_id || 'export').slice(0, 16)}.md`;
  anchor.click();
  // Defer revoke so browsers that start download asynchronously still have a live URL.
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/** Printable HTML — open print dialog so user can Save as PDF without extra deps. */
function downloadPrintableHtml(result: AlgebraSolveResponse) {
  const html = buildPrintableHtml(result);
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, '_blank', 'noopener,noreferrer');
  if (win) {
    win.addEventListener('load', () => {
      try {
        win.focus();
        win.print();
      } catch {
        // user can still print manually
      }
    });
  } else {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `algebra-solution-${(result.request_id || 'export').slice(0, 16)}.html`;
    anchor.click();
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function buildPrintableHtml(result: AlgebraSolveResponse): string {
  const escape = (value: string) =>
    value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const steps = result.steps
    .filter((step) => step.kind !== 'conclusion')
    .map((step) => {
      const body = [
        step.explanation ? `<p>${escape(step.explanation)}</p>` : '',
        step.after_latex ? `<p><code>${escape(step.after_latex)}</code></p>` : '',
      ].join('');
      return `<section><h3>${step.index}. ${escape(step.title || '')}</h3>${body}</section>`;
    })
    .join('\n');
  return `<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/>
<title>Lời giải đại số</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#111;line-height:1.5}
  h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:1.4rem}
  code,pre{background:#f4f4f5;padding:2px 6px;border-radius:4px}
  pre{padding:10px;overflow:auto;white-space:pre-wrap}
  .meta{color:#555;font-size:0.9rem}
  @media print{body{margin:0}}
</style></head><body>
<h1>Kết quả đại số</h1>
<p class="meta">Trạng thái: ${escape(result.status)} · Topic: ${escape(result.topic)}
${result.request_id ? ` · ID: ${escape(result.request_id)}` : ''}</p>
<h2>Đề</h2><pre>${escape(result.input)}</pre>
<h2>Canonical</h2><pre>${escape(result.normalized_input)}</pre>
<h2>Đáp án</h2><p>${escape(result.answer)}</p>
${result.answer_latex ? `<pre>${escape(result.answer_latex)}</pre>` : ''}
<h2>Các bước</h2>
${steps || '<p>(không có bước)</p>'}
<h2>Kiểm chứng</h2><p>${escape(result.verification.status)}</p>
<script>window.addEventListener('load',function(){/* ready for print */});</script>
</body></html>`;
}

function buildMarkdown(result: AlgebraSolveResponse): string {
  const lines = [
    `# Kết quả đại số`,
    '',
    `**Trạng thái:** ${result.status}`,
    `**Topic:** ${result.topic}`,
    '',
    `## Đề`,
    '```',
    result.input,
    '```',
    '',
    `## Canonical`,
    '```',
    result.normalized_input,
    '```',
    '',
    `## Đáp án`,
    result.answer,
  ];
  if (result.answer_latex) {
    lines.push('', '```latex', result.answer_latex, '```');
  }
  if (result.assumptions.length) {
    lines.push('', '## Giả thiết', ...result.assumptions.map((item) => `- ${item}`));
  }
  if (result.warnings.length) {
    lines.push('', '## Cảnh báo', ...result.warnings.map((item) => `- ${item}`));
  }
  if (result.steps.length) {
    lines.push('', '## Các bước');
    for (const step of result.steps) {
      if (step.kind === 'conclusion') continue;
      lines.push(`### ${step.index}. ${step.title}`);
      if (step.explanation) lines.push(step.explanation);
      if (step.after_latex) lines.push(`$$${step.after_latex}$$`);
      lines.push('');
    }
  }
  lines.push('', `## Kiểm chứng: ${result.verification.status}`);
  return lines.join('\n');
}

export function expressionForAnalyzer(result: AlgebraSolveResponse): string | null {
  const raw = (result.normalized_input || result.input || '').trim();
  if (!raw) return null;
  const derivative = raw.match(/^derivative\(expr=([^,)]+)/i);
  if (derivative) return cleanAnalyzerExpr(derivative[1]);
  const limit = raw.match(/^limit\(expr=([^,)]+)/i);
  if (limit) return cleanAnalyzerExpr(limit[1]);
  const integral = raw.match(/^integral\(expr=([^,)]+)/i);
  if (integral) return cleanAnalyzerExpr(integral[1]);
  if (/^(arithmetic|geometric|C\(|A\(|factorial|coefficient|quadratic_)/i.test(raw)) return null;
  if (raw.includes(';')) return null;
  const split = raw.match(/^(.+?)(?:<=|>=|!=|=|<|>)/);
  if (split) return cleanAnalyzerExpr(split[1]);
  return cleanAnalyzerExpr(raw);
}

function cleanAnalyzerExpr(value: string) {
  return value.trim().replace(/\*\*/g, '^').replace(/\s+/g, '');
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

function sourceLabel(source: string) {
  if (source === 'rule_based_vi') return 'Rule-based tiếng Việt';
  if (source === 'latex_normalizer') return 'LaTeX normalizer';
  if (source === 'structured_ui') return 'Structured UI';
  return source;
}

function verificationCheckLabel(name: string) {
  const labels: Record<string, string> = {
    empty_solution_set: 'Tập nghiệm rỗng',
    symbolic_solution_set: 'Tập nghiệm symbolic',
    candidate_substitution: 'Thay nghiệm vào đề gốc',
    domain_constraints_valid: 'Điều kiện xác định',
    inequality_sample: 'Thử điểm khoảng nghiệm',
    condition_set_detected: 'ConditionSet',
    sample_only_scope: 'Phạm vi sample-only',
    unevaluated_solution_set: 'Tập chưa evaluate',
  };
  return labels[name] || name.replace(/_/g, ' ');
}

function verificationStatusLabel(status: string) {
  if (status === 'verified') return 'Đã kiểm chứng';
  if (status === 'partially_verified') return 'Kiểm chứng một phần';
  if (status === 'failed') return 'Kiểm chứng thất bại';
  if (status === 'skipped') return 'Bỏ qua kiểm chứng';
  return status;
}

function statusTitle(status: AlgebraSolveResponse['status']) {
  if (status === 'solved') return 'Đã giải được';
  if (status === 'partial') return 'Kết quả một phần';
  if (status === 'unsupported') return 'Chưa hỗ trợ dạng này';
  return 'Không thể giải';
}
