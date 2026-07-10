import type { AlgebraSolveResponse } from '../../api/client';

const STORAGE_KEY = 'algebra_solver_history_v1';
const MAX_ITEMS = 20;

export interface AlgebraHistoryItem {
  id: string;
  savedAt: string;
  input: string;
  topic: string;
  status: string;
  answer: string;
  request_id?: string | null;
  /** Compact snapshot for re-display (not full steps to keep storage small). */
  snapshot: {
    normalized_input: string;
    answer_latex?: string | null;
    warnings: string[];
  };
}

export function loadAlgebraHistory(): AlgebraHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AlgebraHistoryItem[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_ITEMS) : [];
  } catch {
    return [];
  }
}

export function saveAlgebraHistoryItem(result: AlgebraSolveResponse): AlgebraHistoryItem[] {
  const item: AlgebraHistoryItem = {
    id: result.request_id || `local_${Date.now()}`,
    savedAt: new Date().toISOString(),
    input: result.input,
    topic: result.topic,
    status: result.status,
    answer: result.answer,
    request_id: result.request_id,
    snapshot: {
      normalized_input: result.normalized_input,
      answer_latex: result.answer_latex,
      warnings: (result.warnings || []).slice(0, 5),
    },
  };
  const prev = loadAlgebraHistory().filter((entry) => entry.id !== item.id);
  const next = [item, ...prev].slice(0, MAX_ITEMS);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // quota / private mode
  }
  return next;
}

export function clearAlgebraHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
