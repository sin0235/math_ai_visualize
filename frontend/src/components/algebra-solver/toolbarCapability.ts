/**
 * Capability registry for algebra toolbar buttons.
 * Only actions listed as supported are shown in the math snippet toolbar.
 */
export type ToolbarSupport = 'supported' | 'hidden';

/** Actions the algebra pipeline can meaningfully parse/solve. */
export const ALGEBRA_TOOLBAR_SUPPORT: Record<string, ToolbarSupport> = {
  // Algebra
  frac: 'supported',
  nthRoot: 'supported',
  power: 'supported',
  log: 'supported',
  ln: 'supported',
  abs: 'supported',
  factorial: 'supported',
  combination: 'supported',
  permutation: 'supported',
  // Calculus & equations
  derivative: 'supported',
  integral: 'supported',
  limit: 'supported',
  system2: 'supported',
  system3: 'supported',
  equation: 'supported',
  // Trig
  sin: 'supported',
  cos: 'supported',
  tan: 'supported',
  cot: 'supported',
  asin: 'supported',
  acos: 'supported',
  atan: 'supported',
  acot: 'supported',
  // Relations / arithmetic
  gt: 'supported',
  lt: 'supported',
  ge: 'supported',
  le: 'supported',
  eq: 'supported',
  ne: 'supported',
  plus: 'supported',
  minus: 'supported',
  pm: 'supported',
  times: 'supported',
  divide: 'supported',
  pi: 'supported',
  e: 'supported',
  infty: 'supported',
  posInfty: 'supported',
  negInfty: 'supported',
  // Degree is supported via angle_unit=degree (toolbar insert ° still hidden;
  // unit is chosen in the angle-unit select to avoid ambiguous mixes).
  degree: 'hidden',
  // Hidden until backend supports them well
  sum: 'hidden',
  product: 'hidden',
  vector: 'hidden',
  approx: 'hidden',
  in: 'hidden',
  notin: 'hidden',
  subset: 'hidden',
  cup: 'hidden',
  cap: 'hidden',
  emptyset: 'hidden',
  forall: 'hidden',
  exists: 'hidden',
  Rightarrow: 'hidden',
  Leftrightarrow: 'hidden',
};

export function isToolbarActionSupported(action: string): boolean {
  return ALGEBRA_TOOLBAR_SUPPORT[action] === 'supported';
}
