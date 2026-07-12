import assert from 'node:assert/strict';

import { threeSceneFromProjectionV3 } from './renderProjectionV3.ts';

const projection = {
  scene_id: 'projection',
  revision: 2,
  renderer: 'threejs_3d',
  dimension: '3d',
  object_names: { p1: 'A', p2: 'B', s1: 'AB' },
  points: [
    { object_id: 'p1', name: 'A', label: 'Điểm A', position: [0, 0, 0], visible: true },
    { object_id: 'p2', name: 'B', label: null, position: [2, 0, 0], visible: true },
  ],
  linear: [{
    object_id: 's1',
    name: 'AB',
    kind: 'segment',
    point_ids: ['p1', 'p2'],
    positions: [[0, 0, 0], [2, 0, 0]],
    visible: true,
    color: '#000000',
    line_width: 2,
    style: 'solid',
    extent: null,
  }],
  circles: [],
  functions: [],
  surfaces: [],
  spheres: [],
  annotations: [{
    annotation_id: 'ann1',
    type: 'length',
    target_ids: ['s1'],
    label: '2',
    color: null,
    provenance: 'verified',
    relation_id: 'r1',
    metadata: {},
  }],
  bounds: { minimum: [0, 0, 0], maximum: [2, 0, 0], center: [1, 0, 0], radius: 1 },
  view: { dimension: '3d', show_axes: true, show_grid: true, show_coordinates: false },
};

const scene = threeSceneFromProjectionV3(projection);
assert.deepEqual(Object.keys(scene.points), ['p1', 'p2']);
assert.equal(scene.points.p1.object_id, 'p1');
assert.equal(scene.points.p1.label, 'Điểm A');
assert.deepEqual(scene.segments[0].points, ['p1', 'p2']);
assert.equal(scene.annotations[0].target, 'p1-p2');
assert.equal(scene.annotations[0].metadata.relation_id, 'r1');
assert.deepEqual(scene.relations, []);

console.log('render projection v3 decoder: ok');