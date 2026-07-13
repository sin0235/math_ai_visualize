import assert from 'node:assert/strict';

// Inline pure-logic mirrors for CI without TS transpile of Notification stubs.
function truncateNotifyBody(text, max = 120) {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}

function isImportantWorkflowNotification(title, kind) {
  if (kind === 'error' || kind === 'warning') return true;
  const lower = title.toLowerCase();
  const hints = ['dựng hình', 'giải', 'lời giải', 'không giải', 'thất bại', 'lỗi', 'cần xác nhận', 'chưa đủ', 'lưu ý', 'gợi ý'];
  return hints.some((hint) => lower.includes(hint));
}

assert.equal(truncateNotifyBody('  hello   world  '), 'hello world');
assert.equal(truncateNotifyBody('a'.repeat(200)).endsWith('…'), true);
assert.equal(truncateNotifyBody('a'.repeat(200)).length, 120);
assert.equal(isImportantWorkflowNotification('Dựng hình xong', 'info'), true);
assert.equal(isImportantWorkflowNotification('Đăng nhập', 'info'), false);
assert.equal(isImportantWorkflowNotification('Đăng nhập', 'error'), true);
assert.equal(isImportantWorkflowNotification('Lưu ý khi giải', 'warning'), true);

// force=true must bypass importance filter (mirror canShowBrowserNotify logic).
function canShowBrowserNotifyMirror({ force = false, title = '', kind = 'info', important }) {
  if (!force && title && kind && !important(title, kind)) return false;
  return true;
}
assert.equal(
  canShowBrowserNotifyMirror({
    force: true,
    title: 'Thông báo đã bật',
    kind: 'info',
    important: isImportantWorkflowNotification,
  }),
  true,
);
assert.equal(
  canShowBrowserNotifyMirror({
    force: false,
    title: 'Thông báo đã bật',
    kind: 'info',
    important: isImportantWorkflowNotification,
  }),
  false,
);
console.log('browserNotify pure helpers ok');
