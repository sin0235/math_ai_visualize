import assert from 'node:assert/strict';

import { visibleWorkspaceIssues } from './workspaceNotice.ts';

assert.deepEqual(visibleWorkspaceIssues({
  status: 'verified',
  requires_user_confirmation: false,
  issues: [{ stage: 'repair', code: 'REPAIRED', message: 'Đã sửa annotation.', severity: 'warning' }],
}), []);

assert.deepEqual(visibleWorkspaceIssues({
  status: 'needs_confirmation',
  requires_user_confirmation: true,
  issues: [{
    stage: 'verify',
    code: 'CONSTRAINT_UNVERIFIABLE',
    message: 'Verifier không hỗ trợ relation.',
    severity: 'warning',
  }],
}), ['Một quan hệ hình học chưa đủ căn cứ để kiểm chứng tự động; hãy xác nhận hình trước khi giải hoặc xuất.']);

assert.deepEqual(visibleWorkspaceIssues({
  status: 'failed',
  requires_user_confirmation: true,
  issues: [{ stage: 'topology', code: 'REFERENCE_NOT_FOUND', message: 'Khối thiếu cạnh AB.', severity: 'error' }],
}), ['Khối thiếu cạnh AB.']);

console.log('workspace notice: ok');
