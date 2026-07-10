/** Thống kê mô tả — lớp 12 (mẫu / ghép nhóm). */

export type RawPoint = { value: number; id: string };

export type GroupedBin = {
  from: number;
  to: number;
  mid: number;
  frequency: number;
};

export type DescriptiveResult = {
  n: number;
  sorted: number[];
  mean: number;
  median: number;
  mode: number[];
  q1: number;
  q3: number;
  iqr: number;
  range: number;
  variance: number;
  std: number;
  min: number;
  max: number;
  outliers: number[];
  bins: GroupedBin[];
  groupedMean: number;
  groupedVariance: number;
  groupedStd: number;
};

export function parseDataList(text: string): number[] {
  return text
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s.replace(',', '.')))
    .filter((n) => Number.isFinite(n));
}

export function percentileSorted(sorted: number[], p: number) {
  if (sorted.length === 0) return NaN;
  if (sorted.length === 1) return sorted[0];
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  const t = idx - lo;
  return sorted[lo] * (1 - t) + sorted[hi] * t;
}

export function computeDescriptive(values: number[], binWidth: number): DescriptiveResult {
  const n = values.length;
  const sorted = [...values].sort((a, b) => a - b);
  if (n === 0) {
    return {
      n: 0,
      sorted: [],
      mean: NaN,
      median: NaN,
      mode: [],
      q1: NaN,
      q3: NaN,
      iqr: NaN,
      range: NaN,
      variance: NaN,
      std: NaN,
      min: NaN,
      max: NaN,
      outliers: [],
      bins: [],
      groupedMean: NaN,
      groupedVariance: NaN,
      groupedStd: NaN,
    };
  }

  const mean = values.reduce((s, v) => s + v, 0) / n;
  const median = percentileSorted(sorted, 0.5);
  const q1 = percentileSorted(sorted, 0.25);
  const q3 = percentileSorted(sorted, 0.75);
  const iqr = q3 - q1;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / Math.max(1, n - 1); // mẫu
  const std = Math.sqrt(variance);
  const min = sorted[0];
  const max = sorted[n - 1];
  const range = max - min;

  // mode
  const freq = new Map<number, number>();
  for (const v of values) {
    const key = Math.round(v * 1e9) / 1e9;
    freq.set(key, (freq.get(key) ?? 0) + 1);
  }
  let maxF = 0;
  for (const f of freq.values()) maxF = Math.max(maxF, f);
  const mode = maxF <= 1 ? [] : [...freq.entries()].filter(([, f]) => f === maxF).map(([v]) => v);

  const fenceLow = q1 - 1.5 * iqr;
  const fenceHigh = q3 + 1.5 * iqr;
  const outliers = values.filter((v) => v < fenceLow || v > fenceHigh);

  const bins = buildBins(values, binWidth, min, max);
  const grouped = groupedStats(bins);

  return {
    n,
    sorted,
    mean,
    median,
    mode,
    q1,
    q3,
    iqr,
    range,
    variance,
    std,
    min,
    max,
    outliers,
    bins,
    groupedMean: grouped.mean,
    groupedVariance: grouped.variance,
    groupedStd: grouped.std,
  };
}

export function buildBins(values: number[], width: number, min: number, max: number): GroupedBin[] {
  const w = Math.max(width, 1e-6);
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  // expand a bit
  const start = Math.floor(min / w) * w;
  const end = Math.ceil((max + 1e-12) / w) * w;
  const bins: GroupedBin[] = [];
  for (let from = start; from < end - 1e-12; from += w) {
    const to = from + w;
    const frequency = values.filter((v) => v >= from && (to >= end - 1e-9 ? v <= to : v < to)).length;
    bins.push({ from, to, mid: (from + to) / 2, frequency });
  }
  return bins.length ? bins : [{ from: min, to: max + w, mid: (min + max) / 2, frequency: values.length }];
}

function groupedStats(bins: GroupedBin[]) {
  const n = bins.reduce((s, b) => s + b.frequency, 0);
  if (n === 0) return { mean: NaN, variance: NaN, std: NaN };
  const mean = bins.reduce((s, b) => s + b.mid * b.frequency, 0) / n;
  const variance = bins.reduce((s, b) => s + b.frequency * (b.mid - mean) ** 2, 0) / Math.max(1, n - 1);
  return { mean, variance, std: Math.sqrt(variance) };
}

export function removeOutliers(values: number[]): number[] {
  const r = computeDescriptive(values, 1);
  const set = new Set(r.outliers.map((v) => Math.round(v * 1e9) / 1e9));
  return values.filter((v) => !set.has(Math.round(v * 1e9) / 1e9));
}
