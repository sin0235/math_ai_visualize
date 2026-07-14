import type { PipelineIssueV3, SceneWorkspaceResponseV3 } from '../types/sceneV3';

export function visibleWorkspaceIssues(
  workspace: Pick<SceneWorkspaceResponseV3, 'status' | 'issues' | 'requires_user_confirmation'>,
): string[] {
  if (workspace.status === 'verified' && !workspace.requires_user_confirmation) return [];

  const messages: string[] = [];
  for (const issue of workspace.issues ?? []) {
    if (issue.severity === 'info') continue;
    const message = learnerIssueMessage(issue);
    if (message && !messages.includes(message)) messages.push(message);
  }
  return messages.slice(0, 6);
}

function learnerIssueMessage(issue: PipelineIssueV3): string {
  if (issue.code === 'CONSTRAINT_UNVERIFIABLE') {
    return 'Một quan hệ hình học chưa đủ căn cứ để kiểm chứng tự động; hãy xác nhận hình trước khi giải hoặc xuất.';
  }
  if (issue.code === 'REPAIR_CONFIRMATION_REQUIRED') {
    const lower = issue.message.toLowerCase();
    if (lower.includes('thiếu dữ kiện')) return 'Đề còn thiếu dữ kiện cần thiết để xác nhận toàn bộ hình.';
    if (lower.includes('giả định')) return 'Hình có sử dụng một giả định cần bạn xác nhận.';
    return 'Hình đã được phục hồi nhưng cần bạn xác nhận trước khi giải hoặc xuất.';
  }
  if (issue.severity === 'warning' && isTechnicalIssue(issue)) return '';
  return issue.message.trim();
}

function isTechnicalIssue(issue: PipelineIssueV3): boolean {
  const text = `${issue.code} ${issue.message}`.toLowerCase();
  return /provider|router|pydantic|schema|validation|grounding|fallback|telemetry|repair succeeded|đã kiểm|đã sửa/.test(text);
}
