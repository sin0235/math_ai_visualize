import type { SolveResponse } from '../api/render';

export type SolverNoticeKind = 'error' | 'warning' | 'info';

export interface SolverNotice {
  title: string;
  message: string;
  kind: SolverNoticeKind;
  details: string[];
}

export function buildSolverNotice(result: SolveResponse): SolverNotice | null {
  const confidence = result.confidence ?? 'verified';
  const issues = uniqueIssues([
    ...(result.data_issues ?? []),
    ...(result.warnings ?? []),
  ]).slice(0, 6);

  if (confidence === 'insufficient') {
    const answer = result.answer?.trim();
    const message = answer && answer !== 'Không đủ dữ kiện'
      ? answer
      : issues[0] ?? 'Hình hoặc câu hỏi chưa đủ để tính. Hãy bổ sung số đo hoặc quan hệ còn thiếu.';
    return {
      title: 'Chưa đủ dữ kiện',
      message,
      kind: 'warning',
      details: issues.filter((item) => item !== message).slice(0, 5),
    };
  }
  if (confidence === 'partial') {
    return {
      title: 'Kết quả gợi ý',
      message: 'Đã có đáp án nhưng còn điểm cần lưu ý.',
      kind: 'warning',
      details: issues,
    };
  }
  if (issues.length > 0) {
    return {
      title: 'Lưu ý khi giải',
      message: issues[0],
      kind: 'warning',
      details: issues.slice(1),
    };
  }
  return null;
}

function uniqueIssues(values: string[]): string[] {
  const result: string[] = [];
  for (const value of values) {
    const issue = toLearnerIssue(value);
    if (issue && !result.includes(issue)) result.push(issue);
  }
  return result;
}

function toLearnerIssue(text: string): string {
  const value = text.trim();
  if (!value) return '';
  const lower = value.toLowerCase();
  if (lower.includes('đề/scene hiện không có dữ kiện định lượng') || lower.includes('không dùng tọa độ minh họa')) {
    return 'Đề chưa có số đo hoặc quan hệ định lượng đủ để tính chính xác; tọa độ AI chỉ dùng để minh họa.';
  }
  if (lower.includes('dữ kiện độ dài/góc') && (lower.includes('không khớp') || lower.includes('mâu thuẫn'))) {
    return 'Các số đo trong đề đang mâu thuẫn với quan hệ hình học đã kiểm tra; hãy kiểm tra lại dữ kiện.';
  }
  if (lower.includes('missing premise')) {
    return 'Còn thiếu giả thiết hình học cần thiết để hoàn thành phép tính.';
  }
  if (isInternalSolverNoise(lower)) return '';
  return value;
}

function isInternalSolverNoise(value: string): boolean {
  return (
    value.includes('d(a,b)')
    || value.includes('s(abc)')
    || value.includes('v(s.abcd)')
    || value.includes('capability')
    || value.includes('verifier')
    || value.includes('phạm vi')
    || value.includes('đã kiểm')
    || value.includes('chưa nhận diện được dạng bài. hãy thử hỏi cụ thể hơn')
  );
}
