import assert from 'node:assert/strict';

import { objectReferenceIdsV3, relationDependenciesV3 } from './sceneInspectorV3State.ts';

const base = { source: 'construction', locked: false, user_edited: false, metadata: {} };
const point = (id) => ({ ...base, id, type: 'point_2d', x: 0, y: 0 });
const segment = { ...base, id: 's', type: 'segment', point_ids: ['a', 'b'], hidden: false };
const scene = {
  scene_id: 'inspector', schema_version: '3.0', revision: 1, problem_text: '', grade: null,
  topic: 'coordinate_2d', renderer: 'geogebra_2d', objects: [point('a'), point('b'), segment],
  relations: [{ id: 'r', type: 'equal_length', operands: [{ role: 'segment', ref_id: 's', ref_kind: 'segment' }], args: {}, source: 'given', metadata: {} }],
  annotations: [], derived_facts: [], parameters: [], view: { dimension: '2d' },
  interpretation: { object_ids: [], relation_ids: [], values: [], missing_data: [], assumptions: [] },
  construction_steps: [], audit: { created_by: 'test' },
};
const response = { scene };

assert.deepEqual(objectReferenceIdsV3(segment), ['a', 'b']);
assert.deepEqual(relationDependenciesV3(response).get('a'), ['s']);
assert.deepEqual(relationDependenciesV3(response).get('s'), ['r']);
assert.equal(relationDependenciesV3(response).has('missing'), false);

console.log('scene inspector v3 state: ok');