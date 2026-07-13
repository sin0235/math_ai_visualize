import type { MathSolutionIr } from '../api/mathSolution';

export function MathCapabilitySummary({ solution }: { solution?: MathSolutionIr | null }) {
  if (!solution) return null;
  const { capability, problem } = solution;
  const grades = [problem.curriculum.grade_min, problem.curriculum.grade_max]
    .filter((value): value is number => typeof value === 'number');
  const gradeLabel = grades.length === 0
    ? 'Không xác định'
    : grades.length === 1 || grades[0] === grades[1]
      ? `Lớp ${grades[0]}`
      : `Lớp ${grades[0]}–${grades[1]}`;
  const limits = Object.entries(capability.limits);

  return (
    <details className="math-capability-summary">
      <summary>
        <span>Phạm vi và kiểm chứng</span>
        <strong>{statusLabel(solution.status)}</strong>
      </summary>
      <dl>
        <div><dt>Skill</dt><dd>{capability.skill_ids.join(', ') || 'Chưa ánh xạ'}</dd></div>
        <div><dt>Khối lớp</dt><dd>{gradeLabel}</dd></div>
        <div><dt>Mục tiêu</dt><dd>{problem.goal || problem.task}</dd></div>
        <div><dt>Độ chính xác</dt><dd>{exactnessLabel(solution.exactness)}</dd></div>
        <div><dt>Verifier</dt><dd>{capability.verifier_methods.join(', ') || 'Chưa có'}</dd></div>
        {problem.givens.length > 0 && <div><dt>Dữ kiện</dt><dd>{problem.givens.join('; ')}</dd></div>}
        {capability.prerequisites.length > 0 && <div><dt>Kiến thức trước</dt><dd>{capability.prerequisites.join(', ')}</dd></div>}
        {limits.length > 0 && <div><dt>Giới hạn</dt><dd>{limits.map(([key, value]) => `${key}=${String(value)}`).join(', ')}</dd></div>}
        {solution.unsupported_reason && <div><dt>Chưa hỗ trợ</dt><dd>{solution.unsupported_reason}</dd></div>}
      </dl>
      {solution.verification.length > 0 && (
        <ul aria-label="Bằng chứng kiểm chứng">
          {solution.verification.map((item, index) => (
            <li key={`${item.method}-${index}`} data-status={item.status}>
              <strong>{item.method}</strong>: {item.detail || item.status}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

function statusLabel(status: MathSolutionIr['status']) {
  if (status === 'solved_verified') return 'Đã kiểm chứng';
  if (status === 'solved_partial') return 'Kiểm chứng một phần';
  if (status === 'unsupported') return 'Chưa hỗ trợ';
  if (status === 'needs_clarification') return 'Cần làm rõ';
  if (status === 'timeout') return 'Quá thời gian';
  return 'Dữ liệu không hợp lệ';
}

function exactnessLabel(exactness: MathSolutionIr['exactness']) {
  return {
    exact: 'Chính xác',
    symbolic_checked: 'Đã kiểm tra ký hiệu',
    numeric_checked: 'Đã kiểm tra số',
    partial: 'Một phần',
    unverified: 'Chưa kiểm tra',
  }[exactness];
}