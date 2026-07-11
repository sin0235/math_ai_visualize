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
  const rawMathGlyph = /[∫√π∞≤≥≠≈∑²³₀₁₂₃₄₅₆₇₈₉′∩∪∥⊥]/;
  assert(all.length >= 4, 'catalog has seeds');
  for (const item of all) {
    assert(Boolean(getSimulation(item.id)), `get ${item.id}`);
    assert(item.learningOutcomes.length > 0, `outcomes ${item.id}`);
    assert(item.checkpoints.length > 0, `checkpoints ${item.id}`);
    assert(item.predictPrompt.length > 0, `predict ${item.id}`);
    assert(!rawMathGlyph.test(`${item.title} ${item.subtitle}`), `raw math glyph in card ${item.id}`);
    assert(
      item.stepMissions?.every((mission) => !rawMathGlyph.test(`${mission.title} ${mission.instruction}`)) ?? true,
      `raw math glyph in mission ${item.id}`,
    );
  }
  assert(getSimulation('missing') === undefined, 'missing id');

  // G12 tool-trip meta
  const g12 = listSimulations({ grade: 12 });
  assert(g12.length >= 9, `expected >=9 g12 labs, got ${g12.length}`);
  for (const item of g12) {
    assert(Boolean(item.stepMissions && item.stepMissions.length === item.steps), `missions ${item.id}`);
    assert(item.toolTripReady === true, `toolTripReady ${item.id}`);
    assert(item.checkpoints.every((c) => (c.unlockAtStep ?? 1) >= 1), `unlock ${item.id}`);
  }

  // Golden: shell volume style 2π∫x f for f=1 on [0,1] → π
  const shellF = compileExpression('1');
  const shellVol = integrate((x) => 2 * Math.PI * Math.abs(x) * Math.abs(shellF.evaluate(x)), 0, 1);
  assert(approxEqual(shellVol, Math.PI, 1e-3), `shell unit ${shellVol}`);

  // Golden: disk π∫f² for f=1 on [0,1] → π
  const diskVol = integrate((x) => Math.PI * shellF.evaluate(x) ** 2, 0, 1);
  assert(approxEqual(diskVol, Math.PI, 1e-3), `disk unit ${diskVol}`);

  // Golden: Bayes PPV classic prior 0.01, sens 0.99, spec 0.95
  const prior = 0.01;
  const sens = 0.99;
  const spec = 0.95;
  const pPos = sens * prior + (1 - spec) * (1 - prior);
  const ppv = (sens * prior) / pPos;
  assert(approxEqual(ppv, 0.1667, 5e-3), `bayes ppv ${ppv}`);

  // Golden: derivative of x^2 at 1 ≈ 2
  const quad = compileExpression('x^2');
  const h = 1e-4;
  const dApprox = (quad.evaluate(1 + h) - quad.evaluate(1 - h)) / (2 * h);
  assert(approxEqual(dApprox, 2, 1e-3), `deriv x^2 ${dApprox}`);

  return { passed: true, count: all.length, g12: g12.length };
}

// Direct execution via `tsx` / `vite-node` (npm run test:simulation)
const argv1 = (globalThis as { process?: { argv?: string[] } }).process?.argv?.[1];
if (typeof argv1 === 'string' && argv1.includes('baseline.test')) {
  const result = runSimulationBaselineTests();
  console.log('Simulation baseline tests OK', result);
}
