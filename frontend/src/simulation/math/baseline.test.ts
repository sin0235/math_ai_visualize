/**
 * Baseline math tests for Simulation Phase 0/2b.
 * Run: npm run test:simulation
 */
import { compileExpression } from '../../utils/calculusExpression';
import {
  integrate,
  riemannBetween,
  riemannSampleX,
  validateBounds,
} from '../../utils/calculusNumerics';
import {
  normalizeAngleRad,
  safeCot,
  safeTan,
  SPECIAL_ANGLES,
} from '../../utils/trigonometryNumerics';
import { listSimulations, getSimulation } from '../catalog';
import {
  verifyAreaBetweenCurves,
  verifyTanCotRelation,
  verifyUnitCircleIdentity,
} from './verify';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

function approxEqual(a: number, b: number, tol = 1e-3) {
  return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= tol;
}

export function runSimulationBaselineTests() {
  // Bounds
  assert(validateBounds(0, 1) === null, 'bounds 0<1 ok');
  assert(validateBounds(1, 1) !== null, 'bounds a>=b fail');

  // Integrate x on [0,1] = 1/2
  const half = integrate((x) => x, 0, 1);
  assert(approxEqual(half, 0.5, 1e-4), `integrate x failed: ${half}`);

  // Riemann mid for f=x, g=0 on [0,1]
  const f = compileExpression('x');
  const g = compileExpression('0');
  const mid = riemannBetween(f, g, 0, 1, 100, 'mid');
  const midSum = mid.reduce((s, r) => s + r.area, 0);
  assert(approxEqual(midSum, 0.5, 5e-3), `mid riemann failed: ${midSum}`);

  const leftSum = riemannBetween(f, g, 0, 1, 200, 'left').reduce((s, r) => s + r.area, 0);
  const rightSum = riemannBetween(f, g, 0, 1, 200, 'right').reduce((s, r) => s + r.area, 0);
  assert(leftSum < midSum && midSum < rightSum, `left/mid/right order: ${leftSum}, ${midSum}, ${rightSum}`);

  assert(riemannSampleX(0, 1, 'left') === 0, 'sample left');
  assert(riemannSampleX(0, 1, 'right') === 1, 'sample right');
  assert(riemannSampleX(0, 1, 'mid') === 0.5, 'sample mid');

  // Area verify
  const areaOk = verifyAreaBetweenCurves({ f: 'x', g: '0', a: 0, b: 1, n: 80, rule: 'mid' });
  assert(areaOk.severity !== 'error', areaOk.message);
  assert(approxEqual(areaOk.exact ?? NaN, 0.5, 1e-3), 'exact area');

  // Trig identities
  for (const angle of SPECIAL_ANGLES) {
    const id = verifyUnitCircleIdentity(angle.radian);
    assert(id.severity === 'ok', `identity at ${angle.degree}°: ${id.message}`);
  }
  assert(verifyUnitCircleIdentity(Math.PI / 7).severity === 'ok', 'identity random');
  assert(safeTan(Math.PI / 2).undefined, 'tan pi/2 undefined');
  assert(safeCot(0).undefined, 'cot 0 undefined');
  assert(verifyTanCotRelation(Math.PI / 6).severity === 'ok', 'tan cot product');
  assert(verifyTanCotRelation(Math.PI / 2).severity === 'approx', 'tan asymptote');

  assert(Math.abs(normalizeAngleRad(-0.1) - (2 * Math.PI - 0.1)) < 1e-9, 'normalize negative');

  // Catalog integrity
  const all = listSimulations();
  assert(all.length >= 4, 'catalog has seeds');
  for (const item of all) {
    assert(Boolean(getSimulation(item.id)), `get ${item.id}`);
    assert(item.learningOutcomes.length > 0, `outcomes ${item.id}`);
    assert(item.checkpoints.length > 0, `checkpoints ${item.id}`);
    assert(item.predictPrompt.length > 0, `predict ${item.id}`);
  }
  assert(getSimulation('missing') === undefined, 'missing id');

  return { passed: true, count: all.length };
}

// Direct execution via `tsx` / `vite-node` (npm run test:simulation)
const argv1 = (globalThis as { process?: { argv?: string[] } }).process?.argv?.[1];
if (typeof argv1 === 'string' && argv1.includes('baseline.test')) {
  const result = runSimulationBaselineTests();
  console.log('Simulation baseline tests OK', result);
}
