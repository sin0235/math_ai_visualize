import assert from 'node:assert/strict';

import { buildAlgebraNotice, visibleAlgebraWarnings } from './algebraNotice.ts';

const verified = {
  status: 'solved',
  answer: 'Đạo hàm: 1/x',
  warnings: [
    'Đã diễn giải đề tiếng Việt thành biểu thức chuẩn trước khi giải.',
    'Đạo hàm chỉ được kiểm chứng một phần (symbolic/numeric).',
  ],
  errors: [],
  verification: {
    status: 'partially_verified',
    checks: [
      { name: 'symbolic', status: 'pass', detail: 'Kiểm tra symbolic đạt.' },
      { name: 'numeric', status: 'warn', detail: 'Không lấy được mẫu numeric.' },
    ],
  },
};

assert.equal(buildAlgebraNotice(verified), null);
assert.deepEqual(visibleAlgebraWarnings(verified), []);

assert.deepEqual(visibleAlgebraWarnings({ warnings: [
  'Đã bỏ toàn bộ diễn giải AI vì không field nào vượt qua grounding validation.',
  'Không gọi được LLM diễn giải, đang dùng lời giải deterministic: provider unavailable',
] }), []);

const approximate = {
  ...verified,
  warnings: ['Kết quả xấp xỉ do dữ liệu ghép nhóm.'],
};
assert.deepEqual(buildAlgebraNotice(approximate), {
  title: 'Lưu ý khi giải',
  message: 'Kết quả xấp xỉ do dữ liệu ghép nhóm.',
  kind: 'warning',
  details: [],
});

const failed = {
  ...verified,
  warnings: [],
  verification: {
    status: 'failed',
    checks: [
      { name: 'substitution', status: 'fail', detail: 'Thay nghiệm vào đề gốc không khớp.' },
    ],
  },
};
assert.deepEqual(buildAlgebraNotice(failed), {
  title: 'Cần rà lại kết quả',
  message: 'Thay nghiệm vào đề gốc không khớp.',
  kind: 'warning',
  details: [],
});

console.log('algebra notice: ok');
