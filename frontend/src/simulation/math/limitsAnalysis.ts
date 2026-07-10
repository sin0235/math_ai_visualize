import type { CompiledExpression } from '../../utils/calculusExpression';
import { compileExpression } from '../../utils/calculusExpression';
import { safeEval } from '../../utils/calculusNumerics';

export type LimitSide = {
  values: Array<{ h: number; x: number; y: number }>;
  estimate: number;
  diverges: boolean;
};

export type ContinuityKind =
  | 'liên tục'
  | 'gián đoạn khử được'
  | 'gián đoạn nhảy'
  | 'gián đoạn vô hạn'
  | 'không xác định';

export function parseFn(source: string): CompiledExpression {
  return compileExpression(source);
}

/** Bảng giá trị tiến tới a từ một phía: x = a + sign * h. */
export function approachTable(fn: CompiledExpression, a: number, side: 1 | -1, hs: number[]): LimitSide {
  const values = hs.map((h) => {
    const x = a + side * h;
    const y = safeEval(fn, x);
    return { h, x, y };
  });
  const finite = values.map((v) => v.y).filter(Number.isFinite);
  if (finite.length < Math.ceil(hs.length * 0.5)) {
    return { values, estimate: NaN, diverges: true };
  }
  // estimate = last few average of finite
  const tail = finite.slice(-3);
  const estimate = tail.reduce((s, v) => s + v, 0) / tail.length;
  const spread = Math.max(...tail) - Math.min(...tail);
  const diverges = spread > Math.max(2, Math.abs(estimate) * 0.35) || Math.abs(estimate) > 1e6;
  return { values, estimate: diverges ? NaN : estimate, diverges };
}

export function twoSidedLimit(fn: CompiledExpression, a: number, hs = [0.5, 0.2, 0.1, 0.05, 0.01, 0.001]) {
  const left = approachTable(fn, a, -1, hs);
  const right = approachTable(fn, a, 1, hs);
  const fa = safeEval(fn, a);
  let L: number | null = null;
  if (!left.diverges && !right.diverges && Number.isFinite(left.estimate) && Number.isFinite(right.estimate)) {
    if (Math.abs(left.estimate - right.estimate) < 0.05 * Math.max(1, Math.abs(left.estimate))) {
      L = (left.estimate + right.estimate) / 2;
    }
  }
  return { left, right, fa, L };
}

export function classifyContinuity(fn: CompiledExpression, a: number): {
  kind: ContinuityKind;
  detail: string;
  left: number;
  right: number;
  fa: number;
  L: number | null;
} {
  const { left, right, fa, L } = twoSidedLimit(fn, a);
  const l = left.estimate;
  const r = right.estimate;
  if (left.diverges || right.diverges) {
    return {
      kind: 'gián đoạn vô hạn',
      detail: 'Ít nhất một phía |f|→∞ hoặc không ổn định.',
      left: l,
      right: r,
      fa,
      L,
    };
  }
  if (!Number.isFinite(l) || !Number.isFinite(r)) {
    return { kind: 'không xác định', detail: 'Không ước lượng được giới hạn một phía.', left: l, right: r, fa, L };
  }
  if (Math.abs(l - r) > 0.08 * Math.max(1, Math.abs(l), Math.abs(r))) {
    return {
      kind: 'gián đoạn nhảy',
      detail: `lim⁻ ≈ ${fmt(l)}, lim⁺ ≈ ${fmt(r)} khác nhau.`,
      left: l,
      right: r,
      fa,
      L: null,
    };
  }
  const lim = (l + r) / 2;
  if (!Number.isFinite(fa)) {
    return {
      kind: 'gián đoạn khử được',
      detail: `Giới hạn ≈ ${fmt(lim)} nhưng f(a) không xác định — có thể khử bằng gán f(a)=L.`,
      left: l,
      right: r,
      fa,
      L: lim,
    };
  }
  if (Math.abs(fa - lim) > 0.08 * Math.max(1, Math.abs(lim))) {
    return {
      kind: 'gián đoạn khử được',
      detail: `lim f ≈ ${fmt(lim)} ≠ f(a)=${fmt(fa)} — đổi giá trị tại a để liên tục.`,
      left: l,
      right: r,
      fa,
      L: lim,
    };
  }
  return {
    kind: 'liên tục',
    detail: 'lim f(a) tồn tại, f(a) xác định và bằng giới hạn (trong sai số số).',
    left: l,
    right: r,
    fa,
    L: lim,
  };
}

/** Hàm mẫu có tham số k: (x^2-1)/(x-1) với lỗ tại 1; piecewise jump; 1/x; k*x+1 continuous family. */
export function presetExpression(key: string, k: number): string {
  switch (key) {
    case 'hole':
      return '(x^2-1)/(x-1)';
    case 'jump':
      // approximate jump via logistic isn't available — use two expressions in UI instead
      return 'x';
    case 'pole':
      return '1/x';
    case 'sinx_x':
      return 'sin(x)/x';
    case 'linear':
      return `${k}*x+1`;
    case 'quad':
      return `x^2+${k}`;
    default:
      return 'x';
  }
}

function fmt(n: number) {
  if (!Number.isFinite(n)) return '?';
  return (Math.round(n * 1000) / 1000).toString().replace('.', ',');
}
