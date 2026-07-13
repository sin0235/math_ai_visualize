import { requestJson } from './core';

export type MathCapabilityStatus = 'supported' | 'partial' | 'planned' | 'unsupported';

export interface MathCapability {
  capability_id: string;
  skill_id: string;
  strand: string;
  grades: number[];
  status: MathCapabilityStatus;
  accepted_input_kinds: Array<'expression' | 'function_analysis' | 'geometry_scene'>;
  tasks: string[];
  solvers: string[];
  verifier_methods: string[];
  minimum_exactness: 'exact' | 'symbolic_checked' | 'numeric_checked' | 'partial';
  limits: Record<string, number | string | boolean>;
  examples: Array<{ label: string; input: string }>;
}

export interface AlgebraTopicCapability {
  topic: string;
  label: string;
  skill_ids: string[];
  status: MathCapabilityStatus;
}

export interface MathCapabilityRegistry {
  version: string;
  curriculum_version: string;
  capabilities: MathCapability[];
  ui: {
    algebra_topics: AlgebraTopicCapability[];
    keyboard_actions: Record<string, string[]>;
  };
}

let capabilityRequest: Promise<MathCapabilityRegistry> | null = null;

export function getMathCapabilities(): Promise<MathCapabilityRegistry> {
  if (capabilityRequest) return capabilityRequest;
  capabilityRequest = requestJson<MathCapabilityRegistry>(
    '/api/math/capabilities',
    { method: 'GET', credentials: 'include' },
    'Không tải được danh mục khả năng toán.',
  ).catch((error) => {
    capabilityRequest = null;
    throw error;
  });
  return capabilityRequest;
}