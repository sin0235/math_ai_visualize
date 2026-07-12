import type { ExactApproxValue } from '../../api/client';

export function decimalGraphNumber(value: string | number | null | undefined) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function featureCoordinate(
  value: ExactApproxValue | null | undefined,
  legacy: string | null | undefined,
  v2: Record<string, unknown> | undefined,
  v2Key: string,
) {
  if (value?.approx !== null && value?.approx !== undefined && Number.isFinite(value.approx)) return value.approx;
  const nested = v2?.[v2Key];
  if (nested && typeof nested === 'object') {
    const approx = numericRecordValue(nested as Record<string, unknown>, 'approx');
    if (approx !== null) return approx;
  }
  return decimalGraphNumber(legacy);
}

export function isFiniteGraphNumber(value: number | null): value is number {
  return value !== null && Number.isFinite(value);
}

function numericRecordValue(record: Record<string, unknown>, key: string) {
  const value = record[key];
  const numeric = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : Number.NaN;
  return Number.isFinite(numeric) ? numeric : null;
}