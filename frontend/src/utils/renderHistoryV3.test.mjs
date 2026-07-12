import assert from 'node:assert/strict';

import { decodeRenderHistoryDetail } from './renderHistoryV3.ts';

function historyV3(overrides = {}) {
  return {
    id: 'history-1',
    problem_text: 'Dựng AB',
    kind: 'math_scene_v3',
    snapshot_revision: 2,
    command_log: [],
    workspace: {
      trusted_for_downstream: true,
      scene: { schema_version: '3.0', scene_id: 'scene-1', revision: 2 },
      projection: { scene_id: 'scene-1', revision: 2 },
    },
    ...overrides,
  };
}

assert.equal(decodeRenderHistoryDetail(historyV3()).kind, 'math_scene_v3');
assert.throws(
  () => decodeRenderHistoryDetail(historyV3({ snapshot_revision: 1 })),
  /Snapshot revision không khớp/,
);
assert.throws(
  () => decodeRenderHistoryDetail(historyV3({
    workspace: {
      trusted_for_downstream: true,
      scene: { schema_version: '3.0', scene_id: 'scene-1', revision: 2 },
      projection: { scene_id: 'scene-1', revision: 3 },
    },
  })),
  /Projection revision không khớp/,
);
assert.throws(() => decodeRenderHistoryDetail({ id: 'legacy', problem_text: 'x', kind: 'unknown' }), /kind không được hỗ trợ/);

console.log('render history v3 decoder: ok');