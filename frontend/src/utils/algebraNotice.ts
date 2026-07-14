import type { AlgebraSolveResponse } from '../api/algebra';

export type AlgebraNoticeKind = 'error' | 'warning' | 'info';

export interface AlgebraNotice {
  title: string;
  message: string;
  kind: AlgebraNoticeKind;
  details: string[];
}

export function buildAlgebraNotice(result: AlgebraSolveResponse): AlgebraNotice | null {
  const warnings = visibleAlgebraWarnings(result);
  const errors = uniqueText(result.errors ?? []);

  if (result.status === 'error' || result.status === 'unsupported') {
    const title = result.status === 'unsupported' ? 'Chưa hỗ trợ dạng này' : 'Không giải được';
    const message = result.answer?.trim() || errors[0] || 'Không thể giải bài này.';
    return {
      title,
      message,
      kind: result.status === 'unsupported' ? 'warning' : 'error',
      details: uniqueText([...errors, ...warnings]).filter((item) => item !== message).slice(0, 5),
    };
  }

  const failedChecks = (result.verification?.checks ?? [])
    .filter((check) => check.status === 'fail')
    .map((check) => check.detail || check.name)
    .filter(Boolean);
  if (result.verification?.status === 'failed' || failedChecks.length > 0) {
    return {
      title: 'Cần rà lại kết quả',
      message: failedChecks[0] || 'Một phép kiểm tra lời giải chưa đạt.',
      kind: 'warning',
      details: uniqueText(failedChecks.slice(1)),
    };
  }

  if (warnings.length > 0) {
    return {
      title: 'Lưu ý khi giải',
      message: warnings[0],
      kind: 'warning',
      details: warnings.slice(1, 6),
    };
  }

  if (result.status === 'partial') {
    return {
      title: 'Kết quả một phần',
      message: 'Hệ thống chưa kiểm chứng đủ để kết luận đầy đủ cho bài này.',
      kind: 'warning',
      details: [],
    };
  }

  return null;
}

export function visibleAlgebraWarnings(result: Pick<AlgebraSolveResponse, 'warnings'>): string[] {
  return uniqueText(result.warnings ?? []).filter(isActionableWarning);
}

function isActionableWarning(value: string): boolean {
  const text = value.toLowerCase();
  if (isRoutineInternalNotice(text)) return false;
  return /mơ hồ|thiếu|không hợp lệ|không áp dụng|xấp xỉ|làm tròn|mâu thuẫn|thất bại|không khớp|không thể|bị cắt|đã cắt|bỏ qua kiểm chứng|vượt quá|quá thời gian/.test(text);
}

function isRoutineInternalNotice(value: string): boolean {
  return (
    value.includes('đã diễn giải đề tiếng việt')
    || value.includes('đầu vào gồm cả mô tả tự nhiên')
    || value.includes('miền r đang là mặc định')
    || value.includes('rule-based')
    || value.includes('nlp:')
    || value.includes('mathcore')
    || value.includes('provider')
    || value.includes('router9')
    || value.includes('openrouter')
    || value.includes('grounding')
    || value.includes('deterministic')
    || value.includes('pydantic')
    || value.includes('schema validation')
    || value.includes('ai diễn giải')
    || value.includes('llm diễn giải')
    || value.includes('fallback')
    || value.includes('consistency replay')
    || value.includes('chỉ được kiểm chứng một phần')
    || value.includes('nghiệm đã được lọc theo khoảng')
  );
}

function uniqueText(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const text = value.trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
  }
  return result;
}
