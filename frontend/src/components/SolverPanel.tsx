import { useMemo, useRef, useState } from 'react';
import { solveProblem, type ConstructionAction, type SolveResponse, type SolveStep } from '../api/client';
import { useInterpretationPreflight } from './nlp/InterpretationPanel';
import { committedSceneRefV3, downstreamGateMessageV3 } from '../hooks/sceneWorkspaceV3State';
import type { RuntimeSettings } from '../types/settings';
import type { MathSceneV3, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import { isDocumentHidden, showBrowserNotify } from '../utils/browserNotify';
import { KatexSpan, normalizeLatexForKatex, sympyToLatex } from './KatexSpan';

type ToastKind = 'error' | 'warning' | 'info';

interface SolverPanelProps {
  workspace: SceneWorkspaceResponseV3;
  runtimeSettings?: RuntimeSettings;
  onHighlight: (objectIds: string[], constructionActions?: ConstructionAction[]) => void;
  /** Optional popup/toast for warnings — keep result panel answer+steps only. */
  onToast?: (title: string, message: string, kind?: ToastKind, details?: string[]) => void;
}

function normalizeSolverLatex(input?: string | null): string {
  if (!input) return '';
  return normalizeLatexForKatex(input).replace(/°/g, '^\\circ');
}

// Question normalization is authoritative on the backend (geometry.parser).
// FE only trims and uses NLP canonical text when the user accepts preflight.

function normalizeComparableText(input?: string | null): string {
  return (input ?? '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

/**
 * Soft-clean step prose: convert common LaTeX to unicode/readable text instead of
 * deleting commands (which left "Lập , , pháp tuyến \\" on distance cards).
 */
function normalizeExplanationText(explanation: string): string {
  let text = (explanation || '').trim();
  if (!text) return text;
  if (!text.includes('\\')) return text;

  // Structural math first (repeat for light nesting).
  for (let i = 0; i < 6; i += 1) {
    const next = text
      .replace(/\\sqrt\{([^{}]+)\}/g, '√($1)')
      .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1)/($2)');
    if (next === text) break;
    text = next;
  }
  text = text
    .replace(/\\overrightarrow\{([^{}]+)\}/g, 'vector $1')
    .replace(/\\vec\s*\{([^{}]+)\}/g, '$1')
    .replace(/\\vec\s*([A-Za-z])/g, '$1')
    .replace(/\\angle\(([^)]+)\)/g, 'góc($1)')
    .replace(/\\(?:left|right)\\?([|()[\]])/g, '$1')
    .replace(/\\\|/g, '||')
    .replace(/\\times/g, '×')
    .replace(/\\cdot/g, '·')
    .replace(/\\pm/g, '±')
    .replace(/\\approx/g, '≈')
    .replace(/\\le/g, '≤')
    .replace(/\\ge/g, '≥')
    .replace(/\\ne/g, '≠')
    .replace(/\\infty/g, '∞')
    .replace(/\\pi/g, 'π')
    .replace(/\\[,;!\s]/g, ' ')
    .replace(/\\[a-zA-Z]+\s*\{([^{}]*)\}/g, '$1')
    .replace(/\\[a-zA-Z]+/g, ' ')
    .replace(/[{}]/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\.\s*\./g, '.')
    .trim();
  return text;
}

function AnswerValue({ answer }: { answer: string }) {
  const match = answer.match(/^(.+?)\s*=\s*(.+)$/s);
  if (match) {
    const [, left, right] = match;
    if (/\\[a-zA-Z]+|√|π|∞/.test(right)) {
      return (
        <>
          {left.trim()} = <KatexSpan tex={normalizeSolverLatex(right)} />
        </>
      );
    }
  }
  if (/\\[a-zA-Z]+/.test(answer)) {
    return <KatexSpan tex={normalizeSolverLatex(answer)} />;
  }
  return <>{answer}</>;
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

function resolveStepObjectIds(scene: MathSceneV3, step: SolveStep): string[] {
  if (step.highlight_object_ids?.length) return step.highlight_object_ids;
  const labels = new Set(step.highlight);
  return scene.objects
    .filter((object) => labels.has(object.label || object.id))
    .map((object) => object.id);
}

export function SolverPanel({ workspace, runtimeSettings, onHighlight, onToast }: SolverPanelProps) {
  const scene = workspace.scene;
  const [question, setQuestion] = useState('');
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
      input_mode: 'natural',
      input_format: 'auto',
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
    // Use NLP canonical question when user/system accepted interpretation; keep original otherwise.
    const solvedQuestion = accepted
      ? accepted.candidate.canonical_text?.trim() || accepted.response.normalized_text.trim() || trimmedQuestion
      : trimmedQuestion;
    await handleSolve(solvedQuestion);
  }

  async function handleSolve(trimmedQuestion: string) {
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
        notifySolverSideChannel(cached, onToast);
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
      notifySolverSideChannel(res, onToast);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Lỗi không xác định.';
      setError(message);
      onToast?.('Không giải được', message, 'error');
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
      onHighlight(resolveStepObjectIds(scene, step), step.construction_actions ?? []);
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
          <option value="oxyz">Dùng tọa độ</option>
          <option value="classical">Dùng quan hệ hình học</option>
        </select>
      </div>

      {gateMessage && <div className="sp-warning" role="note">{gateMessage}</div>}

      <div className="sp-composer-wrap">
        <label className="field-label solver-vietnamese-input">
          Câu hỏi bằng tiếng Việt
          <textarea
            value={question}
            onChange={(event) => { setQuestion(event.target.value); preflight.reset(); }}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') void requestSolve();
            }}
            rows={4}
            maxLength={2000}
            disabled={loading}
            placeholder="Ví dụ: Tính khoảng cách từ A đến mặt phẳng (BCD)"
          />
        </label>
        <button
          id="solver-submit-btn"
          type="button"
          className="sp-btn-primary sp-composer-submit"
          onClick={() => void requestSolve()}
          disabled={loading || Boolean(gateMessage) || !question.trim()}
        >
          {loading ? <span className="sp-spinner" aria-hidden="true" /> : null}
          {loading ? 'Đang giải…' : 'Giải bài'}
        </button>
      </div>

      <div className="sp-input-help">Gõ câu hỏi bằng tiếng Việt. Hệ thống dùng hình đã dựng để trả lời và hướng dẫn từng bước.</div>

      {/* Error */}
      {error && (
        <div className="sp-error" role="alert">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
          {error}
        </div>
      )}

      {/* Result: chỉ kết quả + bước. Warning / trạng thái → popup toast. */}
      {result && (
        <div className="sp-result">
          <div className="sp-answer">
            <span className="sp-answer-label">Kết quả</span>
            <span className="sp-answer-value">
              <AnswerValue answer={result.answer} />
            </span>
          </div>

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


/** Side-channel only: warnings / insufficient data / theorems → toast popup, not result body. */
function notifySolverSideChannel(
  result: SolveResponse,
  onToast?: (title: string, message: string, kind?: ToastKind, details?: string[]) => void,
) {
  if (!onToast) return;
  const confidence = result.confidence ?? 'verified';
  const warnings = (result.warnings ?? [])
    .map((item) => toLearnerIssue(item))
    .filter((item) => item && !isInternalSolverNoise(item));
  const dataIssues = (result.data_issues ?? [])
    .map((item) => toLearnerIssue(item))
    .filter((item) => item && !isInternalSolverNoise(item));
  const details = [...dataIssues, ...warnings].slice(0, 6);

  if (confidence === 'insufficient') {
    onToast(
      'Chưa đủ dữ kiện',
      result.answer && result.answer !== 'Không đủ dữ kiện'
        ? result.answer
        : 'Hình hoặc câu hỏi chưa đủ để tính. Hãy bổ sung dữ kiện hoặc nêu rõ hơn.',
      'warning',
      details,
    );
    return;
  }
  if (confidence === 'partial') {
    onToast(
      'Kết quả gợi ý',
      'Đã có đáp án nhưng còn điểm cần lưu ý.',
      'warning',
      details,
    );
    return;
  }
  if (details.length > 0) {
    onToast('Lưu ý khi giải', details[0], 'warning', details.slice(1));
    return;
  }
  // Clean success: panel has answer+steps; OS notify only when tab hidden.
  if (result.steps.length > 0 && isDocumentHidden()) {
    showBrowserNotify({
      title: 'Đã giải xong',
      body: (result.answer || 'Có lời giải từng bước.').slice(0, 120),
      kind: 'info',
      tag: 'solve-done',
    });
  }
}

function isInternalSolverNoise(text: string) {
  const value = text.toLowerCase();
  return (
    value.includes('d(a,b)')
    || value.includes('s(abc)')
    || value.includes('v(s.abcd)')
    || value.includes('capability')
    || value.includes('kiểm chứng')
    || value.includes('verifier')
    || value.includes('phạm vi')
    || value.includes('đã kiểm')
    || value.includes('chưa nhận diện được dạng bài. hãy thử hỏi cụ thể hơn')
  );
}

function toLearnerIssue(text: string) {
  if (!text.trim()) return '';
  if (isInternalSolverNoise(text)) {
    return 'Hãy nêu rõ đại lượng cần tìm (khoảng cách, góc, diện tích, thể tích, …) và các điểm/mặt liên quan.';
  }
  return text.trim();
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
  // Always soft-convert residual LaTeX; do not delete command tokens (avoids "Lập , ,").
  const explanationText = normalizeExplanationText(step.explanation);

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
        {(step.claim || step.theorem || step.depends_on?.length || step.relation_ids?.length) && (
          <div className="sp-step-proof-note">
            {step.claim && <p><strong>Luận điểm:</strong> {step.claim}</p>}
            {step.theorem && <p><strong>Định lý dùng:</strong> {step.theorem}{step.theorem_id ? ` (${step.theorem_id})` : ''}</p>}
            {step.depends_on && step.depends_on.length > 0 && <p><strong>Phụ thuộc:</strong> {step.depends_on.join(', ')}</p>}
            {step.relation_ids && step.relation_ids.length > 0 && <p><strong>Quan hệ nguồn:</strong> {step.relation_ids.join(', ')}</p>}
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
