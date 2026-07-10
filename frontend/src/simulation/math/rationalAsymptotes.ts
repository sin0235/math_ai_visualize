import { compileExpression, type CompiledExpression } from '../../utils/calculusExpression';
import { safeEval } from '../../utils/calculusNumerics';

export type RationalModel = {
  num: CompiledExpression;
  den: CompiledExpression;
  f: CompiledExpression;
  vertical: Array<{ x: number; multiplicityHint: string }>;
  horizontal: number | null;
  oblique: { m: number; b: number } | null;
  holes: number[];
  degreeDiff: number | null;
  notes: string[];
};

/** Phân tích tiệm cận cho f = num/den với num, den đa thức (nhập biểu thức). */
export function analyzeRational(numSrc: string, denSrc: string, window: { a: number; b: number }): RationalModel {
  const num = compileExpression(numSrc);
  const den = compileExpression(denSrc);
  const f: CompiledExpression = {
    source: `(${num.source})/(${den.source})`,
    evaluate: (x) => {
      const d = den.evaluate(x);
      const n = num.evaluate(x);
      if (!Number.isFinite(n) || !Number.isFinite(d)) return NaN;
      if (Math.abs(d) < 1e-12) return NaN;
      return n / d;
    },
  };

  const vertical = findVerticalAsymptotes(num, den, window.a, window.b);
  const holes = findHoles(num, den, window.a, window.b);
  // remove holes from vertical list
  const pureVertical = vertical.filter((v) => !holes.some((h) => Math.abs(h - v.x) < 1e-4));

  const { horizontal, oblique, degreeDiff, notes } = endBehavior(num, den);

  return {
    num,
    den,
    f,
    vertical: pureVertical,
    horizontal,
    oblique,
    holes,
    degreeDiff,
    notes,
  };
}

function findVerticalAsymptotes(num: CompiledExpression, den: CompiledExpression, a: number, b: number) {
  const roots = findRoots(den, a, b, 600);
  const out: Array<{ x: number; multiplicityHint: string }> = [];
  for (const x of roots) {
    const n0 = Math.abs(safeEval(num, x));
    // if num also ~0 → possible hole
    if (n0 < 1e-5) continue;
    // check blow up
    const left = safeEval(
      { source: 'f', evaluate: (t) => safeEval(num, t) / safeEval(den, t) },
      x - 1e-3,
    );
    const right = safeEval(
      { source: 'f', evaluate: (t) => safeEval(num, t) / safeEval(den, t) },
      x + 1e-3,
    );
    if (Math.abs(left) > 20 || Math.abs(right) > 20 || !Number.isFinite(left) || !Number.isFinite(right)) {
      out.push({ x, multiplicityHint: 'nghiệm mẫu → TC đứng (nếu không triệt tiêu tử)' });
    }
  }
  return out;
}

function findHoles(num: CompiledExpression, den: CompiledExpression, a: number, b: number) {
  const denRoots = findRoots(den, a, b, 600);
  const holes: number[] = [];
  for (const x of denRoots) {
    if (Math.abs(safeEval(num, x)) < 1e-5) holes.push(x);
  }
  return holes;
}

function findRoots(fn: CompiledExpression, a: number, b: number, samples: number) {
  const h = (b - a) / samples;
  const roots: number[] = [];
  let prevX = a;
  let prevY = safeEval(fn, prevX);
  const push = (x: number) => {
    if (!Number.isFinite(x)) return;
    if (roots.some((r) => Math.abs(r - x) < h * 0.5)) return;
    roots.push(x);
  };
  if (Number.isFinite(prevY) && Math.abs(prevY) < 1e-8) push(prevX);
  for (let i = 1; i <= samples; i += 1) {
    const x = a + i * h;
    const y = safeEval(fn, x);
    if (Number.isFinite(y) && Math.abs(y) < 1e-8) push(x);
    if (Number.isFinite(prevY) && Number.isFinite(y) && prevY * y < 0) {
      push(bisect(fn, prevX, x));
    }
    prevX = x;
    prevY = y;
  }
  return roots.sort((l, r) => l - r);
}

function bisect(fn: CompiledExpression, lo: number, hi: number) {
  let a = lo;
  let b = hi;
  let fa = safeEval(fn, a);
  for (let i = 0; i < 40; i += 1) {
    const m = (a + b) / 2;
    const fm = safeEval(fn, m);
    if (!Number.isFinite(fm) || Math.abs(fm) < 1e-10) return m;
    if (fa * fm <= 0) b = m;
    else {
      a = m;
      fa = fm;
    }
  }
  return (a + b) / 2;
}

/**
 * Hành vi vô cùng: so sánh tăng trưởng |num| vs |den| bằng tỉ lệ tại x lớn.
 * horizontal nếu f→L; oblique nếu f ~ mx+b với m≠0.
 */
function endBehavior(num: CompiledExpression, den: CompiledExpression) {
  const notes: string[] = [];
  const xs = [20, 40, 80, 160];
  const vals = xs.map((x) => {
    const d = safeEval(den, x);
    const n = safeEval(num, x);
    return Number.isFinite(n) && Number.isFinite(d) && Math.abs(d) > 1e-12 ? n / d : NaN;
  });
  const finite = vals.filter(Number.isFinite);
  let horizontal: number | null = null;
  let oblique: { m: number; b: number } | null = null;
  let degreeDiff: number | null = null;

  if (finite.length >= 3) {
    const last = finite[finite.length - 1];
    const prev = finite[finite.length - 2];
    if (Math.abs(last - prev) < 0.02 * Math.max(1, Math.abs(last))) {
      horizontal = last;
      notes.push('deg(tử) ≤ deg(mẫu) (ước lượng): có tiệm cận ngang y = L.');
      degreeDiff = Math.abs(last) < 0.05 ? -1 : 0; // rough
    } else {
      // fit mx+b from two large x
      const x1 = 50;
      const x2 = 100;
      const y1 = safeEval(num, x1) / safeEval(den, x1);
      const y2 = safeEval(num, x2) / safeEval(den, x2);
      if (Number.isFinite(y1) && Number.isFinite(y2)) {
        const m = (y2 - y1) / (x2 - x1);
        const b = y1 - m * x1;
        const y3 = safeEval(num, 200) / safeEval(den, 200);
        const pred = m * 200 + b;
        if (Number.isFinite(m) && Math.abs(m) > 0.02 && Math.abs(y3 - pred) < 0.5 * Math.max(1, Math.abs(y3))) {
          oblique = { m, b };
          notes.push('deg(tử) = deg(mẫu)+1 (ước lượng): tiệm cận xiên y = mx + c.');
          degreeDiff = 1;
          horizontal = null;
        } else if (Math.abs(m) < 0.02) {
          horizontal = (y1 + y2) / 2;
          notes.push('Tỉ lệ f(x) ổn định → tiệm cận ngang.');
          degreeDiff = 0;
        } else {
          notes.push('Tăng nhanh hơn đường thẳng — có thể deg(tử) ≥ deg(mẫu)+2 (không có TC ngang/xiên chuẩn).');
          degreeDiff = 2;
        }
      }
    }
  }

  // also check −∞
  const yNeg = safeEval(num, -80) / safeEval(den, -80);
  if (horizontal !== null && Number.isFinite(yNeg) && Math.abs(yNeg - horizontal) > 0.5) {
    notes.push('Hành vi +∞ và −∞ có thể khác (hàm không chẵn/lẻ). Kiểm tra cả hai phía.');
  }

  return { horizontal, oblique, degreeDiff, notes };
}

export function sampleRational(
  f: CompiledExpression,
  a: number,
  b: number,
  count = 360,
  skipNear: number[] = [],
) {
  const dx = (b - a) / Math.max(1, count - 1);
  return Array.from({ length: count }, (_, i) => {
    const x = a + i * dx;
    if (skipNear.some((p) => Math.abs(x - p) < dx * 1.2)) {
      return { x, y: NaN, valid: false };
    }
    const y = f.evaluate(x);
    const valid = Number.isFinite(y) && Math.abs(y) < 80;
    return { x, y: valid ? y : NaN, valid };
  });
}
