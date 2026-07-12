import type { RenderHistoryDetail } from '../api/render';

export function decodeRenderHistoryDetail(value: unknown): RenderHistoryDetail {
  const detail = record(value, 'Chi tiết lịch sử không phải object.');
  if (typeof detail.id !== 'string' || typeof detail.problem_text !== 'string') {
    throw new Error('Chi tiết lịch sử thiếu id hoặc problem_text.');
  }
  if (detail.kind === 'math_scene_v2') {
    record(detail.scene, 'Lịch sử v2 thiếu scene.');
    record(detail.payload, 'Lịch sử v2 thiếu payload.');
    if (!Array.isArray(detail.warnings)) throw new Error('Lịch sử v2 có warnings không hợp lệ.');
    return detail as unknown as RenderHistoryDetail;
  }
  if (detail.kind !== 'math_scene_v3') throw new Error('Lịch sử có kind không được hỗ trợ.');

  const workspace = record(detail.workspace, 'Lịch sử v3 thiếu workspace.');
  const scene = record(workspace.scene, 'Workspace v3 thiếu scene.');
  const projection = record(workspace.projection, 'Workspace v3 thiếu projection.');
  if (scene.schema_version !== '3.0' || typeof scene.scene_id !== 'string' || !isRevision(scene.revision)) {
    throw new Error('Lịch sử v3 có scene contract không hợp lệ.');
  }
  if (!isRevision(detail.snapshot_revision) || detail.snapshot_revision !== scene.revision) {
    throw new Error('Snapshot revision không khớp committed scene.');
  }
  if (projection.scene_id !== scene.scene_id || projection.revision !== scene.revision) {
    throw new Error('Projection revision không khớp committed scene.');
  }
  if (typeof workspace.trusted_for_downstream !== 'boolean' || !Array.isArray(detail.command_log)) {
    throw new Error('Lịch sử v3 thiếu capability hoặc command log.');
  }
  return detail as unknown as RenderHistoryDetail;
}

function record(value: unknown, message: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(message);
  return value as Record<string, unknown>;
}

function isRevision(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 1;
}