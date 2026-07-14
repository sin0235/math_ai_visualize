import assert from 'node:assert/strict';

import { segmentAppearance } from './threeGeometryAppearance.ts';

const visible = segmentAppearance({ color: '#1d3557', line_width: 2, style: 'solid' }, false, false);
assert.deepEqual(visible, {
  color: '#1d3557',
  lineWidth: 2,
  dashed: false,
  dashSize: 0.18,
  gapSize: 0.11,
  opacity: 1,
});

const hidden = segmentAppearance({ color: '#1d3557', line_width: 5, style: 'solid' }, true, false);
assert.equal(hidden.color, '#9aa4b2');
assert.equal(hidden.lineWidth, 1.4);
assert.equal(hidden.dashed, true);
assert.equal(hidden.dashSize, 0.26);
assert.equal(hidden.opacity, 0.62);

const auxiliary = segmentAppearance({ color: '#7c3aed', line_width: 2.5, style: 'dashed' }, false, false);
assert.equal(auxiliary.color, '#7c3aed');
assert.equal(auxiliary.lineWidth, 2.5);
assert.equal(auxiliary.dashed, true);

const highlighted = segmentAppearance({ color: '#1d3557', line_width: 2, style: 'solid' }, false, true);
assert.equal(highlighted.color, '#f97316');
assert.equal(highlighted.lineWidth, 4);

console.log('three geometry appearance: ok');
