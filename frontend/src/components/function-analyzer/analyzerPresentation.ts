export interface AnalyzerErrorLike {
  message: string;
  code?: string;
  retryAfterSeconds?: number;
}

export function mathTex(exact: string | number | null | undefined, latex?: string | null): string {
  const preferred = latex?.trim();
  if (preferred) return preferred;
  if (exact == null) return String.raw`\text{chưa xác định}`;
  const value = String(exact).trim();
  return value ? analyzerExactToLatex(value) : String.raw`\text{chưa xác định}`;
}

export function pointTex(
  x: string | number | null | undefined,
  y: string | number | null | undefined,
  xLatex?: string | null,
  yLatex?: string | null,
): string {
  return String.raw`\left(${mathTex(x, xLatex)};\,${mathTex(y, yLatex)}\right)`;
}

export function mathListTex(values: string[], empty = String.raw`\varnothing`): string {
  const items = values.map((value) => value.trim()).filter(Boolean);
  return items.length ? String.raw`\left\{${items.join(',\\;')}\right\}` : empty;
}

export function mathUnionTex(values: string[]): string {
  const items = values.map((value) => mathTex(value)).filter(Boolean);
  return items.length ? items.join(String.raw`\cup`) : String.raw`\varnothing`;
}

export function analyzerCriticalPointLabel(kind: string | null | undefined, fallback?: string | null): string {
  return {
    max: 'Cực đại',
    min: 'Cực tiểu',
    inflection: 'Điểm uốn',
    stationary_inflection: 'Điểm uốn dừng',
    critical: 'Điểm dừng',
    unknown: 'Điểm dừng',
  }[kind ?? ''] ?? (fallback?.trim() || 'Điểm đặc biệt');
}

export function analyzerStatusLabel(status: string | null | undefined): string {
  return {
    complete: 'Đầy đủ',
    partial: 'Một phần',
    unknown: 'Chưa xác định',
    unavailable: 'Không khả dụng',
    unsupported: 'Chưa hỗ trợ',
    finite: 'Hữu hạn',
    infinite: 'Vô hạn',
    exact: 'Chính xác',
    sampled: 'Đã kiểm tra bằng mẫu',
    symbolic_exact: 'Chính xác đại số',
    numeric_verified: 'Đã kiểm tra số',
    regular_tangent: 'Tiếp tuyến xác định',
    vertical_tangent: 'Tiếp tuyến đứng',
    regular_normal: 'Pháp tuyến xác định',
    vertical_normal: 'Pháp tuyến đứng',
    nondifferentiable: 'Không khả vi',
    point_not_on_graph: 'Điểm không thuộc đồ thị',
  }[status ?? ''] ?? 'Chưa xác định';
}

export function analyzerLineKindLabel(kind: string | null | undefined): string {
  return {
    regular: 'Đường thẳng thông thường',
    vertical: 'Đường thẳng đứng',
    horizontal: 'Đường thẳng ngang',
    cusp: 'Điểm nhọn',
    corner_or_nondifferentiable: 'Góc hoặc điểm không khả vi',
    invalid_contact_point: 'Tiếp điểm không hợp lệ',
  }[kind ?? ''] ?? 'Chưa xác định';
}

export function analyzerMethodLabel(method: string | null | undefined): string {
  return {
    symbolic_range: 'Biến đổi đại số chính xác',
    symbolic_exact: 'Tính toán đại số chính xác',
    numeric_verified: 'Xấp xỉ đã kiểm tra',
    sampled: 'Lấy mẫu số',
    sympy: 'Tính toán đại số',
  }[method ?? ''] ?? 'Phương pháp nội bộ';
}

export function analyzerToolError(error: AnalyzerErrorLike): {
  message: string;
  rateLimited: boolean;
  retryAfterSeconds: number;
} {
  const rateLimited = error.code === 'ANALYZER_RATE_LIMITED' || /rate.?limit|quá tải/i.test(error.message);
  const requestedDelay = error.retryAfterSeconds;
  const retryAfterSeconds = typeof requestedDelay === 'number'
    && Number.isFinite(requestedDelay)
    && requestedDelay > 0
    ? Math.ceil(requestedDelay)
    : 15;
  if (rateLimited) {
    return {
      message: `Công cụ tạm nghỉ. Có thể thử lại sau ${retryAfterSeconds} giây.`,
      rateLimited,
      retryAfterSeconds,
    };
  }
  return {
    message: error.message.replace(/^\[[A-Z0-9_]+\]\s*/, '') || 'Không cập nhật được công cụ khảo sát.',
    rateLimited,
    retryAfterSeconds: 0,
  };
}

export function toolRequestFingerprint(analysisId: string, options: unknown): string {
  return `${analysisId}:${stableSerialize(options)}`;
}

function analyzerExactToLatex(value: string): string {
  return value
    .replace(/\*\*/g, '^')
    .replace(/\bsqrt\(([^)]+)\)/g, String.raw`\sqrt{$1}`)
    .replace(/\b(?:oo|zoo)\b/g, String.raw`\infty`)
    .replace(/-\\infty/g, String.raw`-\infty`)
    .replace(/(^|[^\w.])(-?)(\d+)\/(\d+)(?![\w.])/g, (_match, prefix, sign, numerator, denominator) => `${prefix}${sign}\\frac{${numerator}}{${denominator}}`)
    .replace(/\*/g, String.raw` \cdot `)
    .replace(/≤/g, String.raw`\le `)
    .replace(/≥/g, String.raw`\ge `)
    .replace(/≠/g, String.raw`\ne `)
    .trim();
}

function stableSerialize(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableSerialize).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableSerialize(item)}`)
      .join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}