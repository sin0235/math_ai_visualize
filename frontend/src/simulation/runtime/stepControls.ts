/**
 * Gate control theo bước tool-trip.
 * freeMode = true → mọi control mở (chế độ tự do).
 */
export function isControlEnabled(step: number, minStep: number, freeMode = false): boolean {
  if (freeMode) return true;
  return step >= minStep;
}

export function isControlVisible(step: number, minStep: number, freeMode = false): boolean {
  return isControlEnabled(step, minStep, freeMode);
}

/** maxStep inclusive */
export function isControlInRange(
  step: number,
  minStep: number,
  maxStep: number,
  freeMode = false,
): boolean {
  if (freeMode) return true;
  return step >= minStep && step <= maxStep;
}

export function controlClassName(enabled: boolean, extra = ''): string {
  return [extra, enabled ? '' : 'is-step-locked'].filter(Boolean).join(' ');
}
