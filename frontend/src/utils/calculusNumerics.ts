import type { CompiledExpression } from './calculusExpression';

export type SamplePoint = { x: number; y: number; valid: boolean };
export type RectSample = { x: number; midX: number; top: number; bottom: number; height: number; width: number; area: number };

export function sampleFunction(fn: CompiledExpression, a: number, b: number, count = 240): SamplePoint[] {
  const safeCount = Math.max(2, Math.floor(count));
  const dx = (b - a) / (safeCount - 1);
  return Array.from({ length: safeCount }, (_, index) => {
    const x = a + dx * index;
    const y = safeEval(fn, x);
    return { x, y, valid: Number.isFinite(y) };
  });
}

export function integrate(fn: (x: number) => number, a: number, b: number, intervals = 800): number {
  if (!(a < b)) return NaN;
  const n = Math.max(2, Math.floor(intervals / 2) * 2);
  const h = (b - a) / n;
  let sum = safeFinite(fn(a)) + safeFinite(fn(b));
  if (!Number.isFinite(sum)) return trapezoid(fn, a, b, n);
  for (let i = 1; i < n; i += 1) {
    const value = safeFinite(fn(a + i * h));
    if (!Number.isFinite(value)) return trapezoid(fn, a, b, n);
    sum += value * (i % 2 === 0 ? 2 : 4);
  }
  return (sum * h) / 3;
}

export function riemannBetween(f: CompiledExpression, g: CompiledExpression, a: number, b: number, n: number): RectSample[] {
  const count = Math.max(1, Math.floor(n));
  const width = (b - a) / count;
  return Array.from({ length: count }, (_, index) => {
    const x = a + index * width;
    const midX = x + width / 2;
    const fy = safeEval(f, midX);
    const gy = safeEval(g, midX);
    const top = Math.max(fy, gy);
    const bottom = Math.min(fy, gy);
    const height = Number.isFinite(top - bottom) ? top - bottom : 0;
    return { x, midX, top, bottom, height, width, area: height * width };
  });
}

export function findIntersections(f: CompiledExpression, g: CompiledExpression, a: number, b: number, samples = 420) {
  const roots: Array<{ x: number; y: number }> = [];
  const h = (b - a) / samples;
  let prevX = a;
  let prevY = diff(f, g, prevX);
  for (let i = 1; i <= samples; i += 1) {
    const x = a + i * h;
    const y = diff(f, g, x);
    if (Number.isFinite(prevY) && Number.isFinite(y)) {
      if (Math.abs(y) < 1e-5) addRoot(roots, x, safeEval(f, x));
      if (prevY * y < 0) {
        const rootX = bisect((value) => diff(f, g, value), prevX, x);
        addRoot(roots, rootX, safeEval(f, rootX));
      }
    }
    prevX = x;
    prevY = y;
  }
  return roots;
}

export function safeEval(fn: CompiledExpression, x: number) {
  try {
    const value = fn.evaluate(x);
    return Number.isFinite(value) ? value : NaN;
  } catch {
    return NaN;
  }
}

export function formatNumber(value: number, digits = 4) {
  if (!Number.isFinite(value)) return 'Không xác định';
  const abs = Math.abs(value);
  const fixed = abs >= 1000 ? value.toFixed(2) : abs >= 10 ? value.toFixed(3) : value.toFixed(digits);
  return fixed.replace(/\.?0+$/, '').replace('.', ',');
}

export function validateBounds(a: number, b: number) {
  if (!Number.isFinite(a) || !Number.isFinite(b)) return 'Cận a, b phải là số hữu hạn.';
  if (a >= b) return 'Cận trái a phải nhỏ hơn cận phải b.';
  return null;
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function sampleRange(points: SamplePoint[], extra: number[] = []) {
  const xs = points.filter((p) => p.valid).map((p) => p.x);
  const ys = [...points.filter((p) => p.valid).map((p) => p.y), ...extra.filter(Number.isFinite), 0];
  if (xs.length === 0 || ys.length === 0) return { minX: -1, maxX: 1, minY: -1, maxY: 1 };
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const yPad = Math.max((maxY - minY) * 0.14, 0.5);
  return { minX, maxX, minY: minY - yPad, maxY: maxY + yPad };
}

function trapezoid(fn: (x: number) => number, a: number, b: number, n: number) {
  const h = (b - a) / n;
  let sum = 0;
  let valid = 0;
  for (let i = 0; i <= n; i += 1) {
    const value = safeFinite(fn(a + i * h));
    if (!Number.isFinite(value)) continue;
    sum += value * (i === 0 || i === n ? 0.5 : 1);
    valid += 1;
  }
  return valid > n * 0.9 ? sum * h : NaN;
}

function safeFinite(value: number) {
  return Number.isFinite(value) ? value : NaN;
}

function diff(f: CompiledExpression, g: CompiledExpression, x: number) {
  return safeEval(f, x) - safeEval(g, x);
}

function bisect(fn: (x: number) => number, left: number, right: number) {
  let lo = left;
  let hi = right;
  let flo = fn(lo);
  for (let i = 0; i < 36; i += 1) {
    const mid = (lo + hi) / 2;
    const fm = fn(mid);
    if (!Number.isFinite(fm) || Math.abs(fm) < 1e-8) return mid;
    if (flo * fm <= 0) hi = mid;
    else {
      lo = mid;
      flo = fm;
    }
  }
  return (lo + hi) / 2;
}

function addRoot(roots: Array<{ x: number; y: number }>, x: number, y: number) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  if (roots.some((root) => Math.abs(root.x - x) < 1e-3)) return;
  roots.push({ x, y });
}
