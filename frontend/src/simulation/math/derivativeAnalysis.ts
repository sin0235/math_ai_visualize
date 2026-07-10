import type { CompiledExpression } from '../../utils/calculusExpression';
import { compileExpression } from '../../utils/calculusExpression';
import { clamp, sampleFunction, safeEval, type SamplePoint } from '../../utils/calculusNumerics';

export type CriticalPoint = {
  x: number;
  y: number;
  kind: 'cực đại' | 'cực tiểu' | 'điểm dừng' | 'uốn (f′=0)';
};

export type MonoInterval = {
  from: number;
  to: number;
  sign: 1 | -1 | 0;
  label: string;
};

export type AsymptoteInfo = {
  vertical: number[];
  horizontal: number | null;
  oblique: { m: number; b: number } | null;
};

/** Đạo hàm số trung tâm. */
export function numericalDerivative(fn: CompiledExpression, x: number, h = 1e-4): number {
  const left = safeEval(fn, x - h);
  const right = safeEval(fn, x + h);
  if (!Number.isFinite(left) || !Number.isFinite(right)) {
    const one = safeEval(fn, x + h);
    const base = safeEval(fn, x);
    if (!Number.isFinite(one) || !Number.isFinite(base)) return NaN;
    return (one - base) / h;
  }
  return (right - left) / (2 * h);
}

export function numericalSecondDerivative(fn: CompiledExpression, x: number, h = 1e-3): number {
  const f = (t: number) => numericalDerivative(fn, t, h * 0.5);
  const left = f(x - h);
  const right = f(x + h);
  if (!Number.isFinite(left) || !Number.isFinite(right)) return NaN;
  return (right - left) / (2 * h);
}

export function derivativeAsExpression(fn: CompiledExpression): CompiledExpression {
  return {
    source: `d/dx(${fn.source})`,
    evaluate: (x) => numericalDerivative(fn, x),
  };
}

export function sampleDerivative(fn: CompiledExpression, a: number, b: number, count = 280): SamplePoint[] {
  return sampleFunction(derivativeAsExpression(fn), a, b, count);
}

export function findCriticalPoints(fn: CompiledExpression, a: number, b: number, samples = 500): CriticalPoint[] {
  const h = (b - a) / samples;
  const roots: number[] = [];
  let prevX = a;
  let prevY = numericalDerivative(fn, prevX);
  const eps = 1e-5;

  const push = (x: number) => {
    if (!Number.isFinite(x) || x < a - 1e-9 || x > b + 1e-9) return;
    if (roots.some((r) => Math.abs(r - x) < h * 0.6)) return;
    roots.push(clamp(x, a, b));
  };

  if (Number.isFinite(prevY) && Math.abs(prevY) < eps) push(prevX);

  for (let i = 1; i <= samples; i += 1) {
    const x = a + i * h;
    const y = numericalDerivative(fn, x);
    if (Number.isFinite(y) && Math.abs(y) < eps) push(x);
    if (Number.isFinite(prevY) && Number.isFinite(y) && prevY * y < 0) {
      push(bisectDeriv(fn, prevX, x));
    }
    prevX = x;
    prevY = y;
  }

  return roots
    .sort((l, r) => l - r)
    .map((x) => {
      const y = safeEval(fn, x);
      const d2 = numericalSecondDerivative(fn, x);
      let kind: CriticalPoint['kind'] = 'điểm dừng';
      if (Number.isFinite(d2)) {
        if (d2 < -1e-4) kind = 'cực đại';
        else if (d2 > 1e-4) kind = 'cực tiểu';
        else kind = 'uốn (f′=0)';
      }
      return { x, y, kind };
    })
    .filter((p) => Number.isFinite(p.y));
}

function bisectDeriv(fn: CompiledExpression, left: number, right: number) {
  let lo = left;
  let hi = right;
  let flo = numericalDerivative(fn, lo);
  for (let i = 0; i < 40; i += 1) {
    const mid = (lo + hi) / 2;
    const fm = numericalDerivative(fn, mid);
    if (!Number.isFinite(fm) || Math.abs(fm) < 1e-8) return mid;
    if (flo * fm <= 0) hi = mid;
    else {
      lo = mid;
      flo = fm;
    }
  }
  return (lo + hi) / 2;
}

export function monotonicIntervals(fn: CompiledExpression, a: number, b: number, samples = 240): MonoInterval[] {
  const crit = findCriticalPoints(fn, a, b).map((p) => p.x);
  const cuts = [a, ...crit.filter((x) => x > a + 1e-6 && x < b - 1e-6), b]
    .sort((l, r) => l - r)
    .filter((x, i, arr) => i === 0 || Math.abs(x - arr[i - 1]) > 1e-6);

  const intervals: MonoInterval[] = [];
  for (let i = 0; i < cuts.length - 1; i += 1) {
    const from = cuts[i];
    const to = cuts[i + 1];
    const mid = (from + to) / 2;
    const d = numericalDerivative(fn, mid);
    const sign: 1 | -1 | 0 = !Number.isFinite(d) || Math.abs(d) < 1e-6 ? 0 : d > 0 ? 1 : -1;
    const label = sign > 0 ? 'đồng biến' : sign < 0 ? 'nghịch biến' : 'không đổi / suy biến';
    intervals.push({ from, to, sign, label });
  }
  return intervals;
}

export function globalExtremaOnInterval(fn: CompiledExpression, a: number, b: number) {
  const candidates = [a, b, ...findCriticalPoints(fn, a, b).map((p) => p.x)];
  let min = { x: a, y: Infinity };
  let max = { x: a, y: -Infinity };
  for (const x of candidates) {
    const y = safeEval(fn, x);
    if (!Number.isFinite(y)) continue;
    if (y < min.y) min = { x, y };
    if (y > max.y) max = { x, y };
  }
  if (!Number.isFinite(min.y)) min = { x: a, y: NaN };
  if (!Number.isFinite(max.y)) max = { x: a, y: NaN };
  return { min, max };
}

/** Tiệm cận thô cho một số dạng thường gặp + heuristic số. */
export function detectAsymptotes(fn: CompiledExpression, a: number, b: number): AsymptoteInfo {
  const vertical: number[] = [];
  const samples = 200;
  const h = (b - a) / samples;
  for (let i = 0; i <= samples; i += 1) {
    const x = a + i * h;
    const y = safeEval(fn, x);
    if (!Number.isFinite(y)) {
      // pole neighborhood
      const xl = safeEval(fn, x - h * 0.25);
      const xr = safeEval(fn, x + h * 0.25);
      if ((!Number.isFinite(xl) || Math.abs(xl) > 40) && (!Number.isFinite(xr) || Math.abs(xr) > 40)) {
        if (!vertical.some((v) => Math.abs(v - x) < h)) vertical.push(x);
      }
    }
  }

  const far = Math.max(20, Math.abs(a) * 2, Math.abs(b) * 2, 30);
  const yPos = safeEval(fn, far);
  const yNeg = safeEval(fn, -far);
  let horizontal: number | null = null;
  if (Number.isFinite(yPos) && Number.isFinite(yNeg) && Math.abs(yPos - yNeg) < 0.05) {
    horizontal = (yPos + yNeg) / 2;
  } else if (Number.isFinite(yPos) && Math.abs(yPos - safeEval(fn, far * 1.5)) < 0.05) {
    horizontal = yPos;
  }

  let oblique: AsymptoteInfo['oblique'] = null;
  const y1 = safeEval(fn, far);
  const y2 = safeEval(fn, far * 1.4);
  if (Number.isFinite(y1) && Number.isFinite(y2) && Math.abs(y1) < 1e6) {
    const m = (y2 - y1) / (far * 0.4);
    const b0 = y1 - m * far;
    if (Number.isFinite(m) && Math.abs(m) > 0.02 && Math.abs(m) < 50) {
      // only report if residual small
      const check = safeEval(fn, far * 1.2);
      const pred = m * far * 1.2 + b0;
      if (Number.isFinite(check) && Math.abs(check - pred) < 0.35 * Math.max(1, Math.abs(check))) {
        oblique = { m, b: b0 };
      }
    }
  }

  return { vertical, horizontal, oblique };
}

export function tangentLine(fn: CompiledExpression, x0: number) {
  const y0 = safeEval(fn, x0);
  const m = numericalDerivative(fn, x0);
  return {
    x0,
    y0,
    slope: m,
    /** y = m(x - x0) + y0 */
    evaluate: (x: number) => m * (x - x0) + y0,
    equation: Number.isFinite(m) && Number.isFinite(y0)
      ? `y = ${fmt(m)}(x − ${fmt(x0)}) + ${fmt(y0)}`
      : 'Không xác định',
  };
}

export function secantLine(fn: CompiledExpression, x0: number, h: number) {
  const x1 = x0 + h;
  const y0 = safeEval(fn, x0);
  const y1 = safeEval(fn, x1);
  const m = (y1 - y0) / h;
  return {
    x0,
    x1,
    y0,
    y1,
    slope: m,
    evaluate: (x: number) => y0 + m * (x - x0),
  };
}

export function parseUserFunction(source: string): CompiledExpression {
  return compileExpression(source);
}

function fmt(n: number) {
  if (!Number.isFinite(n)) return '?';
  const t = Math.round(n * 1000) / 1000;
  return String(t).replace('.', ',');
}

/** Bảng biến thiên dạng text có cấu trúc cho UI. */
export function buildVariationTable(fn: CompiledExpression, a: number, b: number) {
  const crit = findCriticalPoints(fn, a, b);
  const xs = [a, ...crit.map((c) => c.x), b]
    .sort((l, r) => l - r)
    .filter((x, i, arr) => i === 0 || Math.abs(x - arr[i - 1]) > 1e-5);
  const mono = monotonicIntervals(fn, a, b);
  return { xs, crit, mono };
}
