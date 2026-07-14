import assert from 'node:assert/strict';

import { buildSolverNotice } from './solverNotice.ts';

const insufficient = buildSolverNotice({
  question: 'd(M,(PFB))',
  answer: 'Không đủ dữ kiện',
  steps: [],
  confidence: 'insufficient',
  warnings: [
    'Đề/scene hiện không có dữ kiện định lượng đã kiểm chứng cho đại lượng cần tính. Hệ thống không dùng tọa độ minh họa do AI tự chọn để kết luận số học.',
  ],
  data_issues: [
    'Đề/scene hiện không có dữ kiện định lượng đã kiểm chứng cho đại lượng cần tính. Hệ thống không dùng tọa độ minh họa do AI tự chọn để kết luận số học.',
  ],
});

assert.deepEqual(insufficient, {
  title: 'Chưa đủ dữ kiện',
  message: 'Đề chưa có số đo hoặc quan hệ định lượng đủ để tính chính xác; tọa độ AI chỉ dùng để minh họa.',
  kind: 'warning',
  details: [],
});

const partial = buildSolverNotice({
  question: 'd(A,B)',
  answer: 'd(A,B) = 3',
  steps: [],
  confidence: 'partial',
  warnings: ['Cần kiểm tra giả thiết phụ.'],
});
assert.equal(partial?.title, 'Kết quả gợi ý');
assert.deepEqual(partial?.details, ['Cần kiểm tra giả thiết phụ.']);

assert.equal(buildSolverNotice({
  question: 'd(A,B)',
  answer: 'd(A,B) = 3',
  steps: [],
  confidence: 'verified',
  warnings: [],
}), null);

assert.equal(buildSolverNotice({
  question: 'd(A,B)',
  answer: 'd(A,B) = 3',
  steps: [],
  confidence: 'verified',
  warnings: ['Không gọi được LLM diễn giải, đang dùng lời giải deterministic: provider unavailable'],
  data_issues: ['Grounding validation đã dùng fallback.'],
}), null);

console.log('solver notice: ok');
