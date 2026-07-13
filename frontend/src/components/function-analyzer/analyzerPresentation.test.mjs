import {
  analyzerCriticalPointLabel,
  analyzerLineKindLabel,
  analyzerMethodLabel,
  analyzerStatusLabel,
  analyzerToolError,
  mathListTex,
  mathTex,
  pointTex,
  toolRequestFingerprint,
} from './analyzerPresentation.ts';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(mathTex('x**2 + sqrt(2)') === 'x^2 + \\sqrt{2}', 'exact expression must become LaTeX');
assert(mathTex('ignored', '\\frac{1}{2}') === '\\frac{1}{2}', 'backend LaTeX must win');
assert(pointTex('1/2', 'sqrt(2)').includes('\\frac{1}{2}'), 'rational coordinates must use LaTeX fractions');
assert(pointTex('1/2', 'sqrt(2)').includes('\\sqrt{2}'), 'point coordinates must use LaTeX');
assert(mathListTex(['-1', '2']) === '\\left\\{-1,\\;2\\right\\}', 'math list must use set notation');
assert(analyzerCriticalPointLabel('min', 'CT') === 'Cực tiểu', 'critical point label must not expose abbreviation');
assert(analyzerStatusLabel('complete') === 'Đầy đủ', 'status must be localized');
assert(analyzerStatusLabel('exact') === 'Chính xác', 'verification status must be localized');
assert(analyzerLineKindLabel('vertical') === 'Đường thẳng đứng', 'line kind must use its own labels');
assert(analyzerMethodLabel('symbolic_range') === 'Biến đổi đại số chính xác', 'method must be localized');

const limited = analyzerToolError({
  message: '[ANALYZER_RATE_LIMITED] Analyzer đang quá tải. Hãy thử lại sau.',
  code: 'ANALYZER_RATE_LIMITED',
  retryAfterSeconds: 9,
});
assert(limited.message === 'Công cụ tạm nghỉ. Có thể thử lại sau 9 giây.', 'rate-limit must hide technical code');
assert(limited.rateLimited && limited.retryAfterSeconds === 9, 'rate-limit cooldown must be preserved');

const invalidDelay = analyzerToolError({
  message: 'Analyzer đang quá tải.',
  code: 'ANALYZER_RATE_LIMITED',
  retryAfterSeconds: Number.POSITIVE_INFINITY,
});
assert(invalidDelay.retryAfterSeconds === 15, 'invalid cooldown must use bounded fallback');

const left = toolRequestFingerprint('analysis-1', { line: { b: 2, k: 1 } });
const right = toolRequestFingerprint('analysis-1', { line: { k: 1, b: 2 } });
assert(left === right, 'request fingerprint must ignore object key order');

console.log('Analyzer presentation checks passed.');