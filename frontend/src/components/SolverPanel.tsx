import { useMemo, useRef, useState } from 'react';
import { solveProblem, type SolveResponse, type SolveStep } from '../api/client';
import type { InterpretationCandidate, InterpretationResponse } from '../api/nlp';
import { InterpretationPanel, useInterpretationPreflight } from './nlp/InterpretationPanel';
import { committedSceneRefV3, downstreamGateMessageV3 } from '../hooks/sceneWorkspaceV3State';
import type { RuntimeSettings } from '../types/settings';
import type { MathSceneV3, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import { KatexSpan, normalizeLatexForKatex, sympyToLatex } from './KatexSpan';
import { MathInputComposer, type MathInputMode } from './math-input/MathInputComposer';

interface SolverPanelProps {
  workspace: SceneWorkspaceResponseV3;
  runtimeSettings?: RuntimeSettings;
  onHighlight: (names: string[]) => void;
}

function normalizeSolverLatex(input?: string | null): string {
  if (!input) return '';
  return normalizeLatexForKatex(input).replace(/°/g, '^\\circ');
}

function normalizeSolverQuestionInput(input: string): string {
  let question = input
    .trim()
    .replace(/[​-‍﻿]/g, '')
    .replace(/[（）]/g, (char) => char === '（' ? '(' : ')')
    .replace(/[，、]/g, ',')
    .replace(/[−–—]/g, '-')
    .replace(/[✕*]/g, '×')
    .replace(/[·•]/g, '.')
    .replace(/\s+/g, ' ');
  question = question.replace(/\b(?:k\/c|kc|khoang\s+cach|khoảng\s+cách)\b/gi, 'd');
  question = question.replace(/\b(?:den|đến|toi|tới|tu|từ|cua|của)\b/gi, ' ');
  question = question.replace(/\b(?:mp|mat\s+phang|mặt\s+phẳng)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})/gi, (_, value: string) => `(${compactPointSequenceText(value)})`);
  question = question.replace(/\b(?:dien\s+tich|diện\s+tích)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})/gi, (_, value: string) => `S(${compactPointSequenceText(value)})`);
  question = question.replace(/\b(?:the\s+tich|thể\s+tích)\s+([A-Za-z][A-Za-z0-9']*(?:\s*\.\s*)?[A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})/gi, (_, value: string) => `V(${compactSolidText(value)})`);
  question = question.replace(/\b([dDsSvV])\s*\(/g, (_, name: string) => `${name.toLowerCase() === 'd' ? 'd' : name.toUpperCase()}(`);
  question = normalizeParenthesizedGeometry(question);
  question = question.replace(/\bd\s+([A-Za-z](?:[0-9]+|')?)\s+(\([A-Za-z0-9'\s]+\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){1,})/gi, (_, point: string, target: string) => `d(${point.toUpperCase()},${normalizeDistanceTargetText(target)})`);
  question = question.replace(/\s+/g, ' ').trim();
  return question.replace(/\bgoc\b/gi, 'góc');
}

function compactPointSequenceText(value: string): string {
  return Array.from(value.matchAll(/[A-Za-z](?:[0-9]+|')?/g)).map((match) => match[0].toUpperCase()).join('');
}

function normalizeDistanceTargetText(value: string): string {
  const target = value.trim();
  if (target.startsWith('(') && target.endsWith(')')) return `(${compactPointSequenceText(target.slice(1, -1))})`;
  return compactPointSequenceText(target);
}

function compactSolidText(value: string): string {
  const cleaned = value.trim().replace(/\s+/g, '');
  if (cleaned.includes('.')) {
    const [left, right] = cleaned.split('.', 2);
    return `${compactPointSequenceText(left)}.${compactPointSequenceText(right)}`;
  }
  const compact = compactPointSequenceText(value);
  return compact.length >= 4 ? `${compact[0]}.${compact.slice(1)}` : compact;
}

function normalizeParenthesizedGeometry(input: string): string {
  let output = '';
  let index = 0;
  while (index < input.length) {
    if (input[index] !== '(') {
      output += input[index];
      index += 1;
      continue;
    }
    const end = findMatchingParen(input, index);
    if (end === -1) {
      output += input[index];
      index += 1;
      continue;
    }
    let inner = normalizeParenthesizedGeometry(input.slice(index + 1, end));
    if (/^[A-Za-z0-9'\s.]+$/.test(inner)) {
      inner = inner.includes('.') ? compactSolidText(inner) : compactPointSequenceText(inner);
    }
    output += `(${inner})`;
    index = end + 1;
  }
  return output;
}

function findMatchingParen(input: string, openIndex: number): number {
  let depth = 0;
  for (let index = openIndex; index < input.length; index += 1) {
    if (input[index] === '(') depth += 1;
    if (input[index] === ')') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function normalizeComparableText(input?: string | null): string {
  return (input ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function normalizeExplanationText(
  explanation: string,
  hasFormula: boolean,
  hasSubstitution: boolean,
): string {
  let text = explanation.trim();
  if (!text) return text;
  if ((hasFormula || hasSubstitution) && text.includes('\\')) {
    // Remove inline latex-heavy expression from prose when formula blocks exist.
    text = text.replace(/\b[A-Za-z][A-Za-z0-9(),.\s]*=\s*\\[a-zA-Z][^.]*(?:\.)?/g, '').trim();
    // Remove any remaining standalone LaTeX fragments (e.g. "\frac{...}{...}").
    text = text
      .replace(/\\[a-zA-Z]+(?:\{[^{}]*\}|\[[^\]]*\]|\([^)]*\)|\s|[^\s.,;:!?])*/g, ' ')
      .replace(/[{}]/g, ' ');
    text = text.replace(/\s{2,}/g, ' ').replace(/\.\s*\./g, '.').trim();
  }
  return text;
}

function buildExamples(scene: MathSceneV3) {
  const pointLabels = new Map(
    scene.objects
      .filter((object) => object.type === 'point_2d' || object.type === 'point_3d')
      .map((point) => [point.id, point.label || point.id]),
  );
  const pointNames = [...pointLabels.values()];
  const face = scene.objects.find(
    (object): object is Extract<MathSceneV3['objects'][number], { type: 'face' }> => object.type === 'face' && object.point_ids.length >= 3,
  );
  const base = face?.point_ids.map((id) => pointLabels.get(id) || id) ?? pointNames.slice(0, 4);
  const distanceBase = base.length >= 3 ? base.slice(0, 3) : pointNames.slice(0, 3);
  const distancePoint = pointNames.find((name) => !distanceBase.includes(name));
  const apex = pointNames.find((name) => !base.includes(name)) ?? pointNames[0];
  const edge = base.length >= 2 ? `${base[0]}${base[1]}` : '';
  const secondEdge = base.length >= 4 ? `${base[2]}${base[3]}` : edge;
  const plane = distanceBase.length >= 3 ? `(${distanceBase.join('')})` : '';
  const top = base.map((name) => `${name}'`);
  const hasMatchingTop = top.length >= 3 && top.every((name) => pointNames.includes(name));
  const volumeExample = hasMatchingTop
    ? `V(${top.join('')}.${base.join('')})`
    : apex && base.length >= 3 && !base.includes(apex) ? `V(${apex}.${base.join('')})` : '';
  const examples = [
    pointNames.length >= 2 ? `d(${pointNames[0]},${pointNames[1]})` : '',
    apex && edge && !edge.includes(apex) ? `d(${apex},${edge})` : '',
    distancePoint && plane ? `d(${distancePoint},${plane})` : '',
    edge && secondEdge && edge !== secondEdge ? `Góc giữa ${edge} và ${secondEdge}` : '',
    apex && edge && plane && !base.includes(apex) ? `Góc giữa ${apex}${base[0]} và ${plane}` : '',
    base.length >= 3 ? `S(${base.join('')})` : '',
    volumeExample,
  ].filter(Boolean);
  return Array.from(new Set(examples));
}

export function SolverPanel({ workspace, runtimeSettings, onHighlight }: SolverPanelProps) {
  const scene = workspace.scene;
  const [question, setQuestion] = useState('');
  const [inputMode, setInputMode] = useState<MathInputMode>('natural');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [geometryMethod, setGeometryMethod] = useState<'oxyz' | 'classical'>('oxyz');
  const [activeStep, setActiveStep] = useState<number | null>(null);
  const preflight = useInterpretationPreflight();
  const cacheRef = useRef<Map<string, SolveResponse>>(new Map());
  const sceneCacheKey = useMemo(() => JSON.stringify(scene), [scene]);
  const gateMessage = downstreamGateMessageV3(workspace, 'giải bài');

  async function requestSolve() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || gateMessage || loading) return;
    setError(null);
    const accepted = await preflight.check({
      text: trimmedQuestion,
      target: 'geometry_solve',
      input_mode: inputMode,
      input_format: inputMode === 'math' ? 'plain' : 'auto',
      context: {
        scene_id: scene.scene_id,
        scene_topic: scene.topic,
        method: geometryMethod,
        scene_objects: scene.objects.map((object) => ({
          id: object.id,
          label: object.label,
          type: object.type,
          ...('point_ids' in object ? { point_ids: object.point_ids } : {}),
          ...('from_point_id' in object ? { from_point_id: object.from_point_id, to_point_id: object.to_point_id } : {}),
        })),
      },
    });
    if (accepted) await handleSolve(accepted);
  }

  async function handleSolve(confirmed: { candidate: InterpretationCandidate; response: InterpretationResponse }) {
    const payloadQuestion = confirmed.candidate.canonical_payload?.question;
    const trimmedQuestion = typeof payloadQuestion === 'string'
      ? payloadQuestion.trim()
      : confirmed.candidate.canonical_text?.trim() || confirmed.response.normalized_text.trim();
    if (!trimmedQuestion || gateMessage) return;
    const cacheKey = `${sceneCacheKey}\n${geometryMethod}\n${trimmedQuestion}`;
    preflight.reset();
    setLoading(true);
    setError(null);
    setResult(null);
    setActiveStep(null);
    onHighlight([]);
    try {
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        setResult(cached);
        return;
      }
      const res = await solveProblem(
        committedSceneRefV3(workspace),
        trimmedQuestion,
        geometryMethod,
        runtimeSettings,
      );
      cacheRef.current.set(cacheKey, res);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi không xác định.');
    } finally {
      setLoading(false);
    }
  }

  function handleStepClick(step: SolveStep) {
    if (activeStep === step.index) {
      setActiveStep(null);
      onHighlight([]);
    } else {
      setActiveStep(step.index);
      onHighlight(step.highlight);
    }
  }

  return (
    <div className="sp-panel">
      {/* Header */}
      <div className="sp-header">
        <div className="sp-header-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </div>
        <div>
          <div className="sp-header-title">Giải toán từng bước</div>
          <div className="sp-header-sub">Click vào bước để highlight trên hình</div>
        </div>
      </div>

      {/* Method Selection */}
      <div className="sp-method-toggle" style={{ marginBottom: '12px', padding: '0 12px' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px', opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Phương pháp giải</div>
        <select 
          className="sp-input" 
          style={{ width: '100%', fontSize: '0.9rem', padding: '8px 12px', cursor: 'pointer', border: '1px solid var(--border)', borderRadius: '8px', backgroundColor: 'var(--paper)', color: 'var(--ink)', outline: 'none' }}
          value={geometryMethod}
          onChange={(e) => setGeometryMethod(e.target.value as 'oxyz' | 'classical')}
        >
          <option value="oxyz">Tọa độ hóa</option>
          <option value="classical">Tương quan hình học</option>
        </select>
      </div>

      {gateMessage && <div className="sp-warning" role="note">{gateMessage}</div>}

      <div className="sp-composer-wrap">
        <MathInputComposer
          value={question}
          mode={inputMode}
          onChange={(value) => { setQuestion(value); preflight.reset(); }}
          onModeChange={(mode) => { setInputMode(mode); preflight.reset(); }}
          keyboard="geometry"
          mathOutputFormat="ascii-math"
          disabled={loading || preflight.state.phase === 'loading'}
          label="Câu hỏi hình học"
          naturalPlaceholder="Ví dụ: Tính khoảng cách từ A đến mặt phẳng (BCD)"
          onSubmit={() => void requestSolve()}
        />
        <button
          id="solver-submit-btn"
          type="button"
          className="sp-btn-primary sp-composer-submit"
          onClick={() => void requestSolve()}
          disabled={loading || preflight.state.phase === 'loading' || Boolean(gateMessage) || !question.trim()}
        >
          {loading ? <span className="sp-spinner" aria-hidden="true" /> : null}
          {loading ? 'Đang giải…' : 'Giải bài'}
        </button>
      </div>

      <div className="sp-input-help">Hỗ trợ câu viết tự nhiên hoặc công thức: d(A,B), d(A,(BCD)), S(ABC), V(S.ABCD).</div>

      <InterpretationPanel
        controller={preflight}
        title="Cách hệ thống hiểu câu hỏi hình học"
        confirmLabel="Xác nhận và giải"
        onConfirm={(confirmed) => handleSolve(confirmed)}
      />

      {/* Error */}
      {error && (
        <div className="sp-error" role="alert">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="sp-result">
          {/* Answer */}
          <div className="sp-answer">
            <span className="sp-answer-label">Kết quả</span>
            <span className="sp-answer-value">{result.answer}</span>
          </div>

          <SolverTrustPanel result={result} />

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="sp-warnings">
              {result.warnings.map((w, i) => <div key={i} className="sp-warning">{w}</div>)}
            </div>
          )}

          {/* Steps */}
          {result.steps.length > 0 && (
            <div className="sp-steps">
              <div className="sp-steps-meta">
                {result.steps.length} bước giải
              </div>
              {result.steps.map((step, idx) => (
                <SolverStepItem
                  key={step.index}
                  step={step}
                  isActive={activeStep === step.index}
                  isLast={idx === result.steps.length - 1}
                  onStepClick={handleStepClick}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SolverTrustPanel({ result }: { result: SolveResponse }) {
  const confidence = result.confidence ?? 'verified';
  const usedFacts = result.used_facts ?? [];
  const dataIssues = result.data_issues ?? [];
  const methodLabel = result.method === 'classical' ? 'Tương quan hình học' : 'Tọa độ hóa';
  return (
    <div className={`sp-trust sp-trust--${confidence}`}>
      <div className="sp-trust-head">
        <span className="sp-trust-badge">{confidenceLabel(confidence)}</span>
        <span className="sp-trust-method">{methodLabel}</span>
      </div>
      {usedFacts.length > 0 && (
        <div className="sp-trust-section">
          <div className="sp-trust-title">Dữ kiện đã dùng</div>
          <div className="sp-trust-facts">
            {usedFacts.slice(0, 6).map((fact, index) => (
              <div key={`${fact.source}-${index}`} className="sp-trust-fact">
                <span>{factSourceLabel(fact.source)}</span>
                <p>{fact.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {dataIssues.length > 0 && (
        <div className="sp-trust-section">
          <div className="sp-trust-title">Vấn đề dữ kiện</div>
          <div className="sp-trust-issues">
            {dataIssues.slice(0, 4).map((issue, index) => <p key={index}>{issue}</p>)}
          </div>
        </div>
      )}
    </div>
  );
}

function confidenceLabel(confidence: string) {
  if (confidence === 'insufficient') return 'Không đủ dữ kiện';
  if (confidence === 'partial') return 'Cần kiểm tra';
  return 'Đủ dữ kiện';
}

function factSourceLabel(source: string) {
  if (source === 'given') return 'Đề cho';
  if (source === 'inferred') return 'Suy ra';
  if (source === 'verified') return 'Đã kiểm';
  if (source === 'parameter_default') return 'Mặc định';
  if (source === 'construction_only') return 'Minh họa';
  return 'Dữ kiện';
}

function SolverStepItem({
  step,
  isActive,
  isLast,
  onStepClick,
  isSubStep = false,
}: {
  step: SolveStep;
  isActive: boolean;
  isLast: boolean;
  onStepClick: (step: SolveStep) => void;
  isSubStep?: boolean;
}) {
  const formulaLatex = normalizeSolverLatex(step.formula_latex);
  const substitutionLatex = normalizeSolverLatex(step.substitution_latex);
  const resultLatex = normalizeSolverLatex(step.result_latex);
  const explanationComparable = normalizeComparableText(step.explanation);
  const formulaComparable = normalizeComparableText(formulaLatex);
  const substitutionComparable = normalizeComparableText(substitutionLatex);
  const showFormula = Boolean(formulaLatex) && formulaComparable !== explanationComparable;
  const showSubstitution = Boolean(substitutionLatex) && substitutionComparable !== explanationComparable && substitutionComparable !== formulaComparable;
  const explanationText = normalizeExplanationText(step.explanation, showFormula, showSubstitution);

  return (
    <div
      id={`solver-step-${step.index}`}
      className={`sp-step${isActive ? ' sp-step--on' : ''} ${isSubStep ? 'sp-sub-step' : ''}`}
    >
      <div className="sp-step-num-col">
        <span className="sp-step-num">{step.index}</span>
        {!isLast && <span className="sp-step-line" aria-hidden="true" />}
      </div>

      <div className="sp-step-content" onClick={() => onStepClick(step)} style={{ cursor: 'pointer' }} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onStepClick(step)}>
        <div className="sp-step-head">
          <span className="sp-step-title">{step.title}</span>
          {step.highlight.length > 0 && (
            <span className="sp-step-tag" title="Các điểm được highlight">
              {step.highlight.join(' · ')}
            </span>
          )}
        </div>
        {explanationText && <p className="sp-step-text">{explanationText}</p>}
        {(step.claim || step.theorem) && (
          <div className="sp-step-proof-note">
            {step.claim && <p><strong>Luận điểm:</strong> {step.claim}</p>}
            {step.theorem && <p><strong>Định lý dùng:</strong> {step.theorem}</p>}
          </div>
        )}
        {showFormula && (
          <div className="sp-step-formula">
            <KatexSpan tex={formulaLatex} className="sp-step-formula-math" />
          </div>
        )}
        {showSubstitution && (
          <div className="sp-step-formula">
            <span className="sp-step-formula-label">Thế số:</span>
            <KatexSpan tex={substitutionLatex} className="sp-step-formula-math" />
          </div>
        )}
        {resultLatex && (
          <div className="sp-step-result">
            <span>Kết quả: </span>
            <KatexSpan tex={resultLatex} />
          </div>
        )}
        {!step.formula_latex && step.expression && (
          <div className="sp-step-formula">
            <KatexSpan tex={sympyToLatex(step.expression)} className="sp-step-formula-math" />
          </div>
        )}
        {!step.result_latex && step.result && (
          <div className="sp-step-result">
            <KatexSpan tex={`= ${sympyToLatex(step.result)}`} />
          </div>
        )}

        {step.sub_steps && step.sub_steps.length > 0 && (
          <div className="sp-sub-steps-container" style={{ marginTop: '0.75rem' }} onClick={(e) => e.stopPropagation()}>
            {step.sub_steps.map((sub, sIdx) => (
              <SolverStepItem
                key={`sub-${sub.index}`}
                step={sub}
                isActive={false}
                isLast={sIdx === step.sub_steps!.length - 1}
                onStepClick={onStepClick}
                isSubStep={true}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
