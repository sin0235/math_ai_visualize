/**
 * Kiểm chứng toán học phía client cho Simulation (Phase 2b).
 * Không gọi backend — tách biệt Render/Algebra/Analyzer.
 */

import { compileExpression } from '../../utils/calculusExpression';
import { integrate, riemannBetween, validateBounds, type RiemannRule } from '../../utils/calculusNumerics';
import { normalizeAngleRad, safeCot, safeTan } from '../../utils/trigonometryNumerics';

export type VerifySeverity = 'ok' | 'approx' | 'error';

export type VerifyResult = {
  severity: VerifySeverity;
  message: string;
  exact?: number;
  approx?: number;
  absError?: number;
};

export function verifyAreaBetweenCurves(input: {
  f: string;
  g: string;
  a: number;
  b: number;
  n: number;
  rule?: RiemannRule;
}): VerifyResult {
  const boundsError = validateBounds(input.a, input.b);
  if (boundsError) return { severity: 'error', message: boundsError };
  try {
    const f = compileExpression(input.f);
    const g = compileExpression(input.g);
    const rects = riemannBetween(f, g, input.a, input.b, input.n, input.rule ?? 'mid');
    if (rects.some((r) => !Number.isFinite(r.area))) {
      return { severity: 'error', message: 'Một phần đoạn nằm ngoài miền xác định — không kiểm chứng được.' };
    }
    const approx = rects.reduce((sum, r) => sum + r.area, 0);
    const exact = integrate((x) => Math.abs(f.evaluate(x) - g.evaluate(x)), input.a, input.b);
    if (!Number.isFinite(exact) || !Number.isFinite(approx)) {
      return { severity: 'error', message: 'Không tính được tích phân hoặc tổng Riemann.' };
    }
    const absError = Math.abs(approx - exact);
    const rel = exact === 0 ? absError : absError / Math.abs(exact);
    if (rel < 1e-3 || absError < 1e-4) {
      return {
        severity: 'ok',
        message: 'Tổng Riemann khớp tốt với tích phân (sai số rất nhỏ).',
        exact,
        approx,
        absError,
      };
    }
    return {
      severity: 'approx',
      message: 'Kết quả Riemann là xấp xỉ số; tăng n để giảm sai số so với tích phân.',
      exact,
      approx,
      absError,
    };
  } catch (error) {
    return { severity: 'error', message: error instanceof Error ? error.message : 'Biểu thức không hợp lệ.' };
  }
}

export function verifyUnitCircleIdentity(theta: number): VerifyResult {
  const t = normalizeAngleRad(theta);
  const s = Math.sin(t);
  const c = Math.cos(t);
  const err = Math.abs(s * s + c * c - 1);
  if (err < 1e-10) {
    return { severity: 'ok', message: 'Định danh cos²θ + sin²θ = 1 được thỏa (sai số máy).', absError: err };
  }
  return { severity: 'error', message: 'Định danh lượng giác cơ bản không thỏa — kiểm tra lại góc.', absError: err };
}

export function verifyTanCotRelation(theta: number): VerifyResult {
  const tan = safeTan(theta);
  const cot = safeCot(theta);
  if (tan.undefined || cot.undefined) {
    return { severity: 'approx', message: 'tan hoặc cot không xác định tại góc này (tiệm cận).' };
  }
  const product = tan.value * cot.value;
  const err = Math.abs(product - 1);
  if (err < 1e-8) {
    return { severity: 'ok', message: 'tan θ · cot θ = 1 (trong miền xác định).', absError: err };
  }
  return { severity: 'error', message: 'Quan hệ tan·cot không khớp.', absError: err };
}

export function formatVerifyTone(severity: VerifySeverity): string {
  if (severity === 'ok') return 'Khớp';
  if (severity === 'approx') return 'Xấp xỉ';
  return 'Lỗi';
}
