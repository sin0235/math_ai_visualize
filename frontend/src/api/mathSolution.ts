export type MathSolutionExactness = 'exact' | 'symbolic_checked' | 'numeric_checked' | 'partial' | 'unverified';

export interface MathCapabilitySnapshot {
  registry_version: string;
  capability_ids: string[];
  skill_ids: string[];
  statuses: Array<'supported' | 'partial' | 'planned' | 'unsupported'>;
  accepted: boolean;
  reason?: string | null;
  limits: Record<string, number | string | boolean>;
  prerequisites: string[];
  verifier_methods: string[];
  metadata: Record<string, unknown>;
}

export interface MathVerificationEvidence {
  policy_methods: string[];
  status: 'pass' | 'fail' | 'warn' | 'skip';
  method: string;
  detail?: string | null;
  error_bound?: number | null;
}

export interface MathSolutionIr {
  schema_version: 'math-solution-ir-v1';
  capability_version: string;
  capability: MathCapabilitySnapshot;
  problem: {
    task: string;
    goal: string;
    givens: string[];
    constraints: string[];
    curriculum: {
      version: string;
      skill_ids: string[];
      grade_min?: number | null;
      grade_max?: number | null;
    };
  };
  status: 'solved_verified' | 'solved_partial' | 'needs_clarification' | 'unsupported' | 'invalid' | 'timeout';
  exactness: MathSolutionExactness;
  warnings: string[];
  unsupported_reason?: string | null;
  verification: MathVerificationEvidence[];
  artifacts: Record<string, unknown>;
}