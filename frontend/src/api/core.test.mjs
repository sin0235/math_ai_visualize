import { parseApiError } from './core.ts';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const rateLimited = await parseApiError(new Response(JSON.stringify({
  detail: {
    code: 'ANALYZER_RATE_LIMITED',
    message: 'Analyzer đang quá tải. Hãy thử lại sau.',
    retryable: true,
  },
}), {
  status: 429,
  headers: {
    'Content-Type': 'application/json',
    'Retry-After': '7',
  },
}), 'Không chạy được Analyzer.');

assert(rateLimited.code === 'ANALYZER_RATE_LIMITED', 'structured error code must be preserved');
assert(rateLimited.message === 'Analyzer đang quá tải. Hãy thử lại sau.', 'technical code must not leak into message');
assert(rateLimited.retryable === true, 'retryable metadata must be preserved');
assert(rateLimited.retryAfterSeconds === 7, 'Retry-After seconds must be preserved');

const retryAt = new Date(Date.now() + 2_000).toUTCString();
const dated = await parseApiError(new Response(JSON.stringify({
  detail: { code: 'ANALYZER_RATE_LIMITED', message: 'Tạm quá tải.' },
}), {
  status: 429,
  headers: { 'Content-Type': 'application/json', 'Retry-After': retryAt },
}), 'Không chạy được Analyzer.');

assert(
  typeof dated.retryAfterSeconds === 'number'
    && dated.retryAfterSeconds >= 1
    && dated.retryAfterSeconds <= 2,
  'HTTP-date Retry-After must become bounded seconds',
);

console.log('API core checks passed.');