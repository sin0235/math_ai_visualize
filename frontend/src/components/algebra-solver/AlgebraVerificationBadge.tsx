import type { AlgebraVerificationStatus } from '../../api/client';

const LABELS: Record<AlgebraVerificationStatus, string> = {
  verified: 'Đã kiểm chứng symbolic',
  partially_verified: 'Kiểm chứng một phần',
  failed: 'Kiểm chứng thất bại',
  skipped: 'Chưa kiểm chứng',
};

export function AlgebraVerificationBadge({ status }: { status: AlgebraVerificationStatus }) {
  return <span className={`algebra-verify-badge ${status}`}>{LABELS[status]}</span>;
}
