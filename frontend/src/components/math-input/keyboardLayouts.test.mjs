import assert from 'node:assert/strict';

import { getKeyboardLayouts } from './keyboardLayouts.ts';

const supported = new Set([
  'frac', 'nthRoot', 'power', 'times', 'divide', 'sin', 'cos', 'tan', 'log',
  'eq', 'ne', 'abs', 'pi', 'infty', 'le', 'ge', 'derivative', 'integral', 'limit',
  'e', 'ln', 'plus', 'minus',
]);
const algebraLayouts = getKeyboardLayouts('algebra', supported);
const geometryLayouts = getKeyboardLayouts('geometry');

assert.deepEqual(algebraLayouts.map((layout) => typeof layout === 'string' ? layout : layout.id), [
  'solver-algebra',
  'solver-calculus',
]);
assert.deepEqual(geometryLayouts.map((layout) => typeof layout === 'string' ? layout : layout.id), [
  'solver-geometry',
  'numeric',
]);

const serialized = JSON.stringify({ algebraLayouts, geometryLayouts });
assert.match(serialized, /d\\\\left\(A/);
assert.match(serialized, /\\\\frac/);
assert.match(serialized, /\\\\int/);
assert.doesNotMatch(serialized, /\\\\sum/);
assert.doesNotMatch(serialized, /\\\\prod/);

const restricted = JSON.stringify(getKeyboardLayouts('algebra', new Set(['frac'])));
assert.match(restricted, /\\\\frac/);
assert.doesNotMatch(restricted, /\\\\int/);
assert.doesNotMatch(restricted, /\\\\sin/);

console.log('math keyboard layouts: ok');