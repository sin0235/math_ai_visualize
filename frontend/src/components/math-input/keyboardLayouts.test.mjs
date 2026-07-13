import assert from 'node:assert/strict';

import { KEYBOARD_LAYOUTS } from './keyboardLayouts.ts';

assert.deepEqual(KEYBOARD_LAYOUTS.algebra.map((layout) => typeof layout === 'string' ? layout : layout.id), [
  'solver-algebra',
  'solver-calculus',
]);
assert.deepEqual(KEYBOARD_LAYOUTS.geometry.map((layout) => typeof layout === 'string' ? layout : layout.id), [
  'solver-geometry',
  'numeric',
]);

const serialized = JSON.stringify(KEYBOARD_LAYOUTS);
assert.match(serialized, /d\\\\left\(A/);
assert.match(serialized, /\\\\frac/);
assert.doesNotMatch(serialized, /\\\\sum/);
assert.doesNotMatch(serialized, /\\\\prod/);

console.log('math keyboard layouts: ok');