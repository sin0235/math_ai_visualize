export type TrigFunctionKey = 'sin' | 'cos' | 'tan' | 'cot';

export type TrigValue = {
  value: number;
  undefined: boolean;
};

export type SpecialAngle = {
  degree: number;
  radian: number;
  radianLabel: string;
  sin: string;
  cos: string;
  tan: string;
  cot: string;
};

export type WavePoint = {
  x: number;
  y: number;
  valid: boolean;
};

export type SineTransform = {
  A: number;
  B: number;
  C: number;
  D: number;
};

const TAU = Math.PI * 2;
const ASYMPTOTE_EPSILON = 1e-4;

export const SPECIAL_ANGLES: SpecialAngle[] = [
  { degree: 0, radian: 0, radianLabel: '0', sin: '0', cos: '1', tan: '0', cot: 'Không xác định' },
  { degree: 30, radian: Math.PI / 6, radianLabel: 'π/6', sin: '1/2', cos: '√3/2', tan: '√3/3', cot: '√3' },
  { degree: 45, radian: Math.PI / 4, radianLabel: 'π/4', sin: '√2/2', cos: '√2/2', tan: '1', cot: '1' },
  { degree: 60, radian: Math.PI / 3, radianLabel: 'π/3', sin: '√3/2', cos: '1/2', tan: '√3', cot: '√3/3' },
  { degree: 90, radian: Math.PI / 2, radianLabel: 'π/2', sin: '1', cos: '0', tan: 'Không xác định', cot: '0' },
  { degree: 120, radian: (2 * Math.PI) / 3, radianLabel: '2π/3', sin: '√3/2', cos: '-1/2', tan: '-√3', cot: '-√3/3' },
  { degree: 135, radian: (3 * Math.PI) / 4, radianLabel: '3π/4', sin: '√2/2', cos: '-√2/2', tan: '-1', cot: '-1' },
  { degree: 150, radian: (5 * Math.PI) / 6, radianLabel: '5π/6', sin: '1/2', cos: '-√3/2', tan: '-√3/3', cot: '-√3' },
  { degree: 180, radian: Math.PI, radianLabel: 'π', sin: '0', cos: '-1', tan: '0', cot: 'Không xác định' },
  { degree: 210, radian: (7 * Math.PI) / 6, radianLabel: '7π/6', sin: '-1/2', cos: '-√3/2', tan: '√3/3', cot: '√3' },
  { degree: 225, radian: (5 * Math.PI) / 4, radianLabel: '5π/4', sin: '-√2/2', cos: '-√2/2', tan: '1', cot: '1' },
  { degree: 240, radian: (4 * Math.PI) / 3, radianLabel: '4π/3', sin: '-√3/2', cos: '-1/2', tan: '√3', cot: '√3/3' },
  { degree: 270, radian: (3 * Math.PI) / 2, radianLabel: '3π/2', sin: '-1', cos: '0', tan: 'Không xác định', cot: '0' },
  { degree: 300, radian: (5 * Math.PI) / 3, radianLabel: '5π/3', sin: '-√3/2', cos: '1/2', tan: '-√3', cot: '-√3/3' },
  { degree: 315, radian: (7 * Math.PI) / 4, radianLabel: '7π/4', sin: '-√2/2', cos: '√2/2', tan: '-1', cot: '-1' },
  { degree: 330, radian: (11 * Math.PI) / 6, radianLabel: '11π/6', sin: '-1/2', cos: '√3/2', tan: '-√3/3', cot: '-√3' },
  { degree: 360, radian: TAU, radianLabel: '2π', sin: '0', cos: '1', tan: '0', cot: 'Không xác định' },
];

export function degToRad(degree: number) {
  return (degree * Math.PI) / 180;
}

export function radToDeg(radian: number) {
  return (radian * 180) / Math.PI;
}

export function normalizeAngleRad(radian: number) {
  const normalized = radian % TAU;
  return normalized < 0 ? normalized + TAU : normalized;
}

export function nearestSpecialAngle(radian: number) {
  const normalized = normalizeAngleRad(radian);
  return SPECIAL_ANGLES.reduce((closest, angle) => {
    const distance = circularDistance(normalized, normalizeAngleRad(angle.radian));
    const closestDistance = circularDistance(normalized, normalizeAngleRad(closest.radian));
    return distance < closestDistance ? angle : closest;
  }, SPECIAL_ANGLES[0]);
}

export function safeTan(radian: number): TrigValue {
  const cos = Math.cos(radian);
  if (Math.abs(cos) < ASYMPTOTE_EPSILON) return { value: NaN, undefined: true };
  return { value: Math.sin(radian) / cos, undefined: false };
}

export function safeCot(radian: number): TrigValue {
  const sin = Math.sin(radian);
  if (Math.abs(sin) < ASYMPTOTE_EPSILON) return { value: NaN, undefined: true };
  return { value: Math.cos(radian) / sin, undefined: false };
}

export function trigValueAt(fn: TrigFunctionKey, x: number) {
  if (fn === 'sin') return { value: Math.sin(x), undefined: false };
  if (fn === 'cos') return { value: Math.cos(x), undefined: false };
  if (fn === 'tan') return safeTan(x);
  return safeCot(x);
}

export function sampleTrigWave(fn: TrigFunctionKey, min: number, max: number, count = 360): WavePoint[] {
  const safeCount = Math.max(2, Math.floor(count));
  const dx = (max - min) / (safeCount - 1);
  return Array.from({ length: safeCount }, (_, index) => {
    const x = min + dx * index;
    const result = trigValueAt(fn, x);
    const y = Math.abs(result.value) > 6 ? NaN : result.value;
    return { x, y, valid: !result.undefined && Number.isFinite(y) };
  });
}

export function sampleTransformedSine(transform: SineTransform, min: number, max: number, count = 360): WavePoint[] {
  const safeCount = Math.max(2, Math.floor(count));
  const dx = (max - min) / (safeCount - 1);
  return Array.from({ length: safeCount }, (_, index) => {
    const x = min + dx * index;
    const y = evaluateTransformedSine(x, transform);
    return { x, y, valid: Number.isFinite(y) };
  });
}

export function evaluateTransformedSine(x: number, transform: SineTransform) {
  return transform.A * Math.sin(transform.B * x + transform.C) + transform.D;
}

export function formatTrigNumber(value: number, digits = 3) {
  if (!Number.isFinite(value)) return 'Không xác định';
  if (Math.abs(value) < 1e-10) return '0';
  return value.toFixed(digits).replace(/\.?0+$/, '').replace('.', ',');
}

export function formatAngleLabel(radian: number, degreeMode: boolean) {
  if (degreeMode) return `${Math.round(radToDeg(normalizeAngleRad(radian)))}°`;
  const nearest = nearestSpecialAngle(radian);
  if (circularDistance(normalizeAngleRad(radian), normalizeAngleRad(nearest.radian)) < 1e-5) return nearest.radianLabel;
  return `${formatTrigNumber(radian, 2)} rad`;
}

export function quadrantForAngle(radian: number) {
  const degree = radToDeg(normalizeAngleRad(radian));
  if (degree === 0 || degree === 90 || degree === 180 || degree === 270 || degree === 360) return 'Trên trục';
  if (degree < 90) return 'Phần tư I';
  if (degree < 180) return 'Phần tư II';
  if (degree < 270) return 'Phần tư III';
  return 'Phần tư IV';
}

function circularDistance(a: number, b: number) {
  const diff = Math.abs(a - b);
  return Math.min(diff, TAU - diff);
}
