import type { RenderResponse } from '../types/scene';

export function downstreamGateMessage(response: RenderResponse, operation: string, allowPartial = false): string | null {
  if (response.status === 'failed') return `Scene dựng hình thất bại nên chưa thể ${operation}.`;
  if (!response.user_confirmed && (response.status === 'fallback' || response.status === 'needs_confirmation' || response.requires_user_confirmation || response.source.fallback_used)) {
    return `Scene cần được xác nhận hoặc dựng lại trước khi ${operation}.`;
  }
  const failed = response.verification_report.relations.filter((item) => item.status === 'failed' || item.status === 'error');
  if (failed.length > 0) return `Scene có ${failed.length} quan hệ kiểm chứng thất bại nên chưa thể ${operation}.`;
  if (!allowPartial) {
    const partial = partialVerificationCount(response);
    if (partial > 0) return `Scene còn ${partial} quan hệ chưa kiểm chứng đầy đủ nên chưa thể ${operation}.`;
  }
  return null;
}

export function partialVerificationWarning(response: RenderResponse, operation: string): string | null {
  const partial = partialVerificationCount(response);
  if (partial === 0) return null;
  return `Scene còn ${partial} quan hệ chưa kiểm chứng đầy đủ; vẫn có thể ${operation}, nhưng nên kiểm tra lại hình trước khi chia sẻ.`;
}

function partialVerificationCount(response: RenderResponse): number {
  return response.verification_report.relations.filter((item) => item.status === 'unsupported' || item.status === 'unverifiable').length;
}
