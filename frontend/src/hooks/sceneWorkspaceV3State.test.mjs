import assert from 'node:assert/strict';

import {
  emptySceneWorkspaceStateV3,
  previewPointMove,
  rebaseSceneCommand,
  sceneWorkspaceReducerV3,
  workspaceDisplayScene,
  workspaceIsTrusted,
} from './sceneWorkspaceV3State.ts';

const scene = (revision) => ({
  scene_id: 'scene-state',
  schema_version: '3.0',
  revision,
  problem_text: 'state test',
  grade: null,
  topic: 'coordinate_2d',
  renderer: 'geogebra_2d',
  objects: [],
  relations: [],
  annotations: [],
  derived_facts: [],
  parameters: [],
  view: { dimension: '2d' },
  interpretation: { object_ids: [], relation_ids: [], values: [], missing_data: [], assumptions: [] },
  construction_steps: [],
  audit: { created_by: 'manual' },
});

const response = (revision, inverseCommand = null, status = 'verified') => ({
  status,
  scene: scene(revision),
  verification: [],
  issues: [],
  requires_user_confirmation: status !== 'verified',
  inverse_command: inverseCommand,
  changed_object_ids: [],
  affected_relation_ids: [],
});

const command = (id, revision) => ({
  type: 'move_point',
  command_id: id,
  scene_id: 'scene-state',
  base_revision: revision,
  point_id: 'p',
  position: [1, 2, 0],
});

let state = sceneWorkspaceReducerV3(emptySceneWorkspaceStateV3, { type: 'load', response: response(1) });
const original = command('move-1', 1);
const inverse = command('undo:move-1', 2);
state = sceneWorkspaceReducerV3(state, { type: 'begin', command: original, mode: 'normal' });
state = sceneWorkspaceReducerV3(state, { type: 'commit', response: response(2, inverse) });
assert.deepEqual(state.undoStack, [inverse]);
assert.deepEqual(state.redoStack, []);

const redoCommand = command('undo:undo:move-1', 3);
state = sceneWorkspaceReducerV3(state, { type: 'begin', command: inverse, mode: 'undo' });
state = sceneWorkspaceReducerV3(state, { type: 'commit', response: response(3, redoCommand) });
assert.deepEqual(state.undoStack, []);
assert.deepEqual(state.redoStack, [redoCommand]);

const undoAgain = command('undo:undo:undo:move-1', 4);
state = sceneWorkspaceReducerV3(state, { type: 'begin', command: redoCommand, mode: 'redo' });
state = sceneWorkspaceReducerV3(state, { type: 'commit', response: response(4, undoAgain) });
assert.deepEqual(state.undoStack, [undoAgain]);
assert.deepEqual(state.redoStack, []);

const preview = { ...scene(4), problem_text: 'preview only' };
state = sceneWorkspaceReducerV3(state, { type: 'preview', scene: preview });
assert.equal(workspaceDisplayScene(state).problem_text, 'preview only');
state = sceneWorkspaceReducerV3(state, { type: 'reject', message: 'rejected' });
assert.equal(workspaceDisplayScene(state).problem_text, 'state test');
assert.equal(state.committed.scene.revision, 4);

state = sceneWorkspaceReducerV3(state, { type: 'load', response: response(5, null, 'needs_confirmation') });
assert.equal(workspaceIsTrusted(state), false);
state = sceneWorkspaceReducerV3(state, { type: 'confirm' });
assert.equal(workspaceIsTrusted(state), true);
assert.equal(rebaseSceneCommand(command('rebased', 1), scene(9)).base_revision, 9);

const pointScene = {
  ...scene(9),
  objects: [
    { id: 'p2', type: 'point_2d', x: 0, y: 0, source: 'user_created', locked: false, user_edited: false, metadata: {} },
    { id: 'p3', type: 'point_3d', x: 0, y: 0, z: 0, source: 'user_created', locked: false, user_edited: false, metadata: {} },
  ],
};
const moved2d = previewPointMove(pointScene, 'p2', [3, 4, 99]);
assert.deepEqual([moved2d.objects[0].x, moved2d.objects[0].y], [3, 4]);
const moved3d = previewPointMove(pointScene, 'p3', [5, 6, 7]);
assert.deepEqual([moved3d.objects[1].x, moved3d.objects[1].y, moved3d.objects[1].z], [5, 6, 7]);
assert.deepEqual([pointScene.objects[1].x, pointScene.objects[1].y, pointScene.objects[1].z], [0, 0, 0]);

console.log('scene workspace v3 state: ok');