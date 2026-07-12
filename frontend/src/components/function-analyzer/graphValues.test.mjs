import { decimalGraphNumber, featureCoordinate } from './graphValues.ts';

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(decimalGraphNumber('-1.25') === -1.25, 'decimal coordinate must parse');
assert(decimalGraphNumber('2/3') === null, 'exact fraction must not be coerced by Number');
assert(decimalGraphNumber('sqrt(2)') === null, 'symbolic exact value must require backend approx');
assert(featureCoordinate({ exact: '2/3', latex: '\\frac{2}{3}', approx: 2 / 3, precision: 15, method: 'sympy' }, '2/3', undefined, 'x_value') === 2 / 3, 'verified approx must win');
assert(featureCoordinate(null, '2/3', { x_value: { approx: 0.666 } }, 'x_value') === 0.666, 'V2 approx must win over exact legacy');

console.log('Function graph value checks passed.');