import assert from 'node:assert/strict';

import { faceOpacity, planeOpacity, segmentAppearance } from './threeGeometryAppearance.ts';

const visible = segmentAppearance({ color: '#1d3557', line_width: 2, style: 'solid' }, false, false);
assert.deepEqual(visible, {
  color: '#1d3557',
  lineWidth: 2.6,
  dashed: false,
  dashSize: 0.18,
  gapSize: 0.11,
  opacity: 1,
});

const hidden = segmentAppearance({ color: '#1d3557', line_width: 5, style: 'solid' }, true, false);
assert.equal(hidden.color, '#748094');
assert.equal(hidden.lineWidth, 2);
assert.equal(hidden.dashed, true);
assert.equal(hidden.dashSize, 0.22);
assert.equal(hidden.opacity, 0.78);

const auxiliary = segmentAppearance({ color: '#7c3aed', line_width: 2.5, style: 'dashed' }, false, false);
assert.equal(auxiliary.color, '#7c3aed');
assert.equal(auxiliary.lineWidth, 2.5);
assert.equal(auxiliary.dashed, true);

const highlighted = segmentAppearance({ color: '#1d3557', line_width: 2, style: 'solid' }, false, true);
assert.equal(highlighted.color, '#f97316');
assert.equal(highlighted.lineWidth, 4);

assert.equal(faceOpacity(0.14), 0.2);
assert.equal(faceOpacity(0.24), 0.24);
assert.equal(faceOpacity(0.6), 0.6);
assert.ok(Math.abs(planeOpacity(0.16) - 0.088) < 1e-12);
assert.equal(planeOpacity(0.24), 0.24);

console.log('three geometry appearance: ok');
