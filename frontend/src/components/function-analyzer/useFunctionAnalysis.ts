import { useEffect, useRef, useState } from 'react';
import {
  createAnalyzerSession,
  extractFunctionImageFile,
  openAnalyzerHistory,
  runAnalyzerIntervalTool,
  runAnalyzerLineTool,
  runAnalyzerTangentTool,
  runAnalyzerTransformTool,
  type AnalyzeLineMode,
  type AnalyzeOptions,
  type AnalyzeResponse,
  type AnalyzeTransformType,
  type AnalyzerSessionResponse,
  type CurriculumProfile,
  type FunctionOcrExtraction,
} from '../../api/client';

type AnalysisState = 'editing' | 'loading' | 'current' | 'stale' | 'error';

type ToolKey = 'interval' | 'line' | 'transform';

export interface ParameterSnapshot {
  value: string;
  result: AnalyzerSessionResponse;
}

type AnalyzeOptionOverrides = Partial<AnalyzeOptions & {
  intervalA: number;
  intervalB: number;
  intervalOpenA: boolean;
  intervalOpenB: boolean;
  enableInterval: boolean;
  lineK: number;
  lineB: number;
  lineMode: AnalyzeLineMode;
  lineX0: number;
  enableLine: boolean;
  transformType: AnalyzeTransformType;
  transformValue: number;
  enableTransform: boolean;
}>;

const ANALYZER_PREFILL_KEY = 'math_ai_analyzer_prefill';

function readAnalyzerPrefill(fallback: string) {
  try {
    const value = sessionStorage.getItem(ANALYZER_PREFILL_KEY);
    if (value) {
      sessionStorage.removeItem(ANALYZER_PREFILL_KEY);
      return value;
    }
  } catch {
    // ignore storage failures
  }
  return fallback;
}

export function useFunctionAnalysis(initialExpression: string, onWarnings?: (warnings: string[]) => void) {
  const [expression, setExpression] = useState(() => readAnalyzerPrefill(initialExpression));
  const [parameterMode, setParameterMode] = useState<'' | 'symbolic' | 'substitute'>('');
  const [parameterValue, setParameterValue] = useState('1');
  const [curriculumProfile, setCurriculumProfile] = useState<CurriculumProfile>({
    grade: 12,
    chapter: 'Khảo sát hàm số',
    explanation_level: 'standard',
  });
  const [loading, setLoading] = useState(false);
  const [analysisState, setAnalysisState] = useState<AnalysisState>('editing');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrCandidate, setOcrCandidate] = useState<FunctionOcrExtraction | null>(null);
  const [ocrPreviewUrl, setOcrPreviewUrl] = useState<string | null>(null);
  const [intervalA, setIntervalA] = useState(-2);
  const [intervalB, setIntervalB] = useState(2);
  const [intervalOpenA, setIntervalOpenA] = useState(false);
  const [intervalOpenB, setIntervalOpenB] = useState(false);
  const [enableInterval, setEnableInterval] = useState(false);
  const [lineK, setLineK] = useState(1);
  const [lineB, setLineB] = useState(0);
  const [lineMode, setLineMode] = useState<AnalyzeLineMode>('intersect');
  const [lineX0, setLineX0] = useState(0);
  const [enableLine, setEnableLine] = useState(false);
  const [enableTransform, setEnableTransform] = useState(false);
  const [transformType, setTransformType] = useState<AnalyzeTransformType>('vertical_shift');
  const [transformValue, setTransformValue] = useState(1);
  const [isAnimatingTransform, setIsAnimatingTransform] = useState(false);
  const [animationFps, setAnimationFps] = useState<30 | 60>(30);
  const [pageVisible, setPageVisible] = useState(() => typeof document === 'undefined' || !document.hidden);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [parameterSnapshots, setParameterSnapshots] = useState<ParameterSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const analyzeRequestRef = useRef(0);
  const baseAbortRef = useRef<AbortController | null>(null);
  const toolAbortRef = useRef<AbortController | null>(null);
  const ocrAbortRef = useRef<AbortController | null>(null);
  const sliderDebounceRef = useRef<number | null>(null);
  const animationRef = useRef<number | null>(null);
  const animationStartedRef = useRef<number | null>(null);
  const baseResultRef = useRef<AnalyzerSessionResponse | null>(null);

  useEffect(() => {
    return () => {
      baseAbortRef.current?.abort();
      toolAbortRef.current?.abort();
      ocrAbortRef.current?.abort();
      if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
      if (animationRef.current !== null) window.cancelAnimationFrame(animationRef.current);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (ocrPreviewUrl) URL.revokeObjectURL(ocrPreviewUrl);
    };
  }, [ocrPreviewUrl]);

  useEffect(() => {
    const syncVisibility = () => setPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', syncVisibility);
    return () => document.removeEventListener('visibilitychange', syncVisibility);
  }, []);

  useEffect(() => {
    if (!isAnimatingTransform || !enableTransform || !requiresTransformValue(transformType) || !pageVisible) {
      if (animationRef.current !== null) window.cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
      animationStartedRef.current = null;
      return;
    }
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) {
      setIsAnimatingTransform(false);
      return;
    }
    const frameDuration = 1000 / animationFps;
    const tick = (timestamp: number) => {
      const previous = animationStartedRef.current ?? timestamp;
      if (timestamp - previous >= frameDuration) {
        animationStartedRef.current = timestamp;
        setTransformValue((current) => {
          const next = current >= 3 ? -3 : Number((current + 0.1).toFixed(2));
          applyAnimatedTransform(next);
          return next;
        });
      }
      animationRef.current = window.requestAnimationFrame(tick);
    };
    animationRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (animationRef.current !== null) window.cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
      animationStartedRef.current = null;
    };
  }, [isAnimatingTransform, enableTransform, transformType, animationFps, pageVisible]);

  function buildAnalyzeOptions(overrides?: AnalyzeOptionOverrides): AnalyzeOptions {
    const nextEnableInterval = overrides?.enableInterval ?? enableInterval;
    const nextIntervalA = overrides?.intervalA ?? intervalA;
    const nextIntervalB = overrides?.intervalB ?? intervalB;
    const nextIntervalOpenA = overrides?.intervalOpenA ?? intervalOpenA;
    const nextIntervalOpenB = overrides?.intervalOpenB ?? intervalOpenB;
    
    const nextEnableLine = overrides?.enableLine ?? enableLine;
    const nextLineK = overrides?.lineK ?? lineK;
    const nextLineB = overrides?.lineB ?? lineB;
    const nextLineMode = overrides?.lineMode ?? lineMode;
    const nextLineX0 = overrides?.lineX0 ?? lineX0;
    
    const nextEnableTransform = overrides?.enableTransform ?? enableTransform;
    const nextTransformType = overrides?.transformType ?? transformType;
    const nextTransformValue = overrides?.transformValue ?? transformValue;
    return {
      curriculum_profile: curriculumProfile,
      ...(containsParameterM(expression) && parameterMode ? {
        parameter_mode: parameterMode,
        ...(parameterMode === 'substitute' ? { parameters: { m: parameterValue } } : {}),
      } : {}),
      ...(nextEnableInterval ? { interval: { a: nextIntervalA, b: nextIntervalB, open_a: nextIntervalOpenA, open_b: nextIntervalOpenB } } : {}),
      ...(nextEnableLine ? { line: { k: nextLineK, b: nextLineB, mode: nextLineMode, x0: nextLineX0, y0: nextLineB } } : {}),
      ...(nextEnableTransform ? {
        transform: requiresTransformValue(nextTransformType)
          ? { type: nextTransformType, value: nextTransformValue }
          : { type: nextTransformType },
      } : {}),
    };
  }

  function scheduleToolAnalyze(overrides?: AnalyzeOptionOverrides) {
    if (!baseResultRef.current || analysisState !== 'current') return;
    const requestOptions = buildAnalyzeOptions(overrides);
    if (!requestOptions.interval && !requestOptions.line && !requestOptions.transform) {
      toolAbortRef.current?.abort();
      setResult(baseResultRef.current);
      return;
    }
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    sliderDebounceRef.current = window.setTimeout(() => void runTool(requestOptions), 280);
  }

  async function runTool(options: AnalyzeOptions, baseOverride?: AnalyzerSessionResponse) {
    const base = baseOverride ?? baseResultRef.current;
    if (!base || (!baseOverride && analysisState !== 'current')) return false;
    toolAbortRef.current?.abort();
    const controller = new AbortController();
    toolAbortRef.current = controller;
    try {
      const response = options.interval
        ? await runAnalyzerIntervalTool(base.analysis_id, options.interval, controller.signal)
        : options.line?.mode === 'tangent_at'
          ? await runAnalyzerTangentTool(base.analysis_id, options.line.x0 ?? 0, controller.signal)
          : options.line
            ? await runAnalyzerLineTool(base.analysis_id, options.line, controller.signal)
            : options.transform
              ? await runAnalyzerTransformTool(base.analysis_id, options.transform, controller.signal)
              : null;
      if (!response || controller.signal.aborted) return false;
      setResult({
        ...base,
        interval_analysis: response.interval_analysis ?? null,
        line_analysis: response.line_analysis ?? null,
        transform_preview: response.transform_preview ?? null,
        geogebra_commands: response.transform_preview
          ? buildTransformCommands(base.geogebra_commands, response.transform_preview.expression)
          : base.geogebra_commands,
      });
      return true;
    } catch (error: unknown) {
      if (!isAbortError(error)) {
        setError(error instanceof Error ? error.message : 'Không chạy được công cụ phân tích.');
      }
      return false;
    }
  }

  async function runAnalyze(expr: string, options?: { clearResult?: boolean; requestOptions?: AnalyzeOptions }) {
    const requestId = ++analyzeRequestRef.current;
    baseAbortRef.current?.abort();
    toolAbortRef.current?.abort();
    const controller = new AbortController();
    baseAbortRef.current = controller;
    setLoading(true);
    setAnalysisState('loading');
    setError(null);
    if (options?.clearResult) setResult(null);
    try {
      const requestOptions = options?.requestOptions ?? {};
      const res = await createAnalyzerSession(expr, {
        parameters: requestOptions.parameters,
        parameter_mode: requestOptions.parameter_mode,
        provenance: requestOptions.provenance,
        curriculum_profile: requestOptions.curriculum_profile ?? curriculumProfile,
      }, controller.signal);
      if (requestId !== analyzeRequestRef.current || controller.signal.aborted) return false;
      if (res.error) {
        setError(formatAnalyzeError(res));
        setAnalysisState('error');
        return false;
      }
      baseResultRef.current = res;
      setResult(res);
      setAnalysisState('current');
      onWarnings?.(res.warnings);
      if (requestOptions.interval || requestOptions.line || requestOptions.transform) {
        await runTool(requestOptions, res);
      }
      return true;
    } catch (error: unknown) {
      if (requestId === analyzeRequestRef.current && !isAbortError(error)) {
        setError(error instanceof Error ? error.message : 'Lỗi không xác định.');
        setAnalysisState('error');
      }
      return false;
    } finally {
      if (requestId === analyzeRequestRef.current) setLoading(false);
    }
  }

  async function handleAnalyze() {
    if (ocrCandidate) return;
    const expr = expression.trim();
    if (!expr) return;
    await runAnalyze(expr, { clearResult: true, requestOptions: buildAnalyzeOptions() });
  }

  async function handleConfirmOcr() {
    const expr = expression.trim();
    if (!expr || !ocrCandidate) return;
    const provenance = { ...ocrCandidate.provenance, source: 'ocr_confirmed' as const };
    const succeeded = await runAnalyze(expr, {
      clearResult: true,
      requestOptions: { ...buildAnalyzeOptions(), provenance },
    });
    if (succeeded) {
      setOcrCandidate(null);
      setOcrPreviewUrl(null);
    }
  }

  function discardOcrCandidate() {
    analyzeRequestRef.current += 1;
    ocrAbortRef.current?.abort();
    setOcrCandidate(null);
    setOcrPreviewUrl(null);
    setExpression('');
    setError(null);
    setAnalysisState('editing');
  }

  async function handleImageChange(file?: File) {
    if (!file) return;
    const requestId = ++analyzeRequestRef.current;
    ocrAbortRef.current?.abort();
    const controller = new AbortController();
    ocrAbortRef.current = controller;
    baseAbortRef.current?.abort();
    toolAbortRef.current?.abort();
    setOcrLoading(true);
    setAnalysisState('loading');
    setError(null);
    setResult(null);
    setOcrCandidate(null);
    setOcrPreviewUrl(URL.createObjectURL(file));
    try {
      const candidate = await extractFunctionImageFile(file, controller.signal);
      if (requestId !== analyzeRequestRef.current || controller.signal.aborted) return;
      setExpression(candidate.expression);
      setOcrCandidate(candidate);
      setAnalysisState('editing');
      onWarnings?.(candidate.warnings);
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current && !isAbortError(e)) {
        setError(e instanceof Error ? e.message : 'Lỗi OCR không xác định.');
        setAnalysisState('error');
      }
    } finally {
      if (requestId === analyzeRequestRef.current) setOcrLoading(false);
    }
  }

  function applyAnimatedTransform(value: number) {
    const base = baseResultRef.current;
    const model = result?.transform_preview;
    if (!base || !model || !model.requires_value) return;
    const expression = instantiateTransformTemplate(model.expression_template, value);
    setResult({
      ...base,
      transform_preview: { ...model, value: formatToolNumber(value), expression, expression_latex: expression },
      geogebra_commands: buildTransformCommands(base.geogebra_commands, expression),
    });
  }

  function resetTransformAnimation() {
    setIsAnimatingTransform(false);
    setTransformValue(1);
    applyAnimatedTransform(1);
  }

  function setTransformTypeAndReset(value: AnalyzeTransformType) {
    setIsAnimatingTransform(false);
    setTransformType(value);
  }

  function invalidateCurrentAnalysis() {
    analyzeRequestRef.current += 1;
    baseAbortRef.current?.abort();
    toolAbortRef.current?.abort();
    ocrAbortRef.current?.abort();
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    setIsAnimatingTransform(false);
    baseResultRef.current = null;
    setResult(null);
    setError(null);
    setAnalysisState(result ? 'stale' : 'editing');
  }

  function setParameterModeAndInvalidate(value: '' | 'symbolic' | 'substitute') {
    if (value === parameterMode) return;
    invalidateCurrentAnalysis();
    setParameterMode(value);
  }

  function setParameterValueAndInvalidate(value: string) {
    if (value === parameterValue) return;
    invalidateCurrentAnalysis();
    setParameterValue(value);
  }

  function setCurriculumProfileAndInvalidate(value: CurriculumProfile) {
    if (
      value.grade === curriculumProfile.grade
      && value.chapter === curriculumProfile.chapter
      && value.explanation_level === curriculumProfile.explanation_level
    ) return;
    invalidateCurrentAnalysis();
    setCurriculumProfile(value);
  }

  async function openHistoryItem(id: string) {
    baseAbortRef.current?.abort();
    toolAbortRef.current?.abort();
    setLoading(true);
    setError(null);
    try {
      const detail = await openAnalyzerHistory(id);
      baseResultRef.current = detail.result;
      setExpression(detail.original_expression);
      setResult(detail.result);
      if (detail.result.curriculum_presentation?.profile) {
        setCurriculumProfile(detail.result.curriculum_presentation.profile);
      }
      setAnalysisState('current');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không mở được lịch sử analyzer.');
      setAnalysisState('error');
    } finally {
      setLoading(false);
    }
  }

  function saveParameterSnapshot() {
    const base = baseResultRef.current;
    const value = base?.parameters?.active_exact?.m;
    if (!base || base.parameter_mode !== 'substitute' || !value) return;
    setParameterSnapshots((current) => {
      const next = [...current.filter((item) => item.value !== value), { value, result: base }];
      // ponytail: snapshot cục bộ giới hạn 6 để tránh giữ payload lớn; M9 history thay bằng lưu trữ phân trang.
      return next.slice(-6);
    });
  }

  function removeParameterSnapshot(value: string) {
    setParameterSnapshots((current) => current.filter((item) => item.value !== value));
  }

  function setExpressionAndInvalidate(value: string) {
    if (value === expression) return;
    invalidateCurrentAnalysis();
    setParameterSnapshots([]);
    setExpression(value);
  }

  function updateToolEnabled(key: ToolKey, enabled: boolean) {
    const nextEnableInterval = key === 'interval' ? enabled : false;
    const nextEnableLine = key === 'line' ? enabled : false;
    const nextEnableTransform = key === 'transform' ? enabled : false;

    setEnableInterval(nextEnableInterval);
    setEnableLine(nextEnableLine);
    setEnableTransform(nextEnableTransform);
    if (key !== 'transform' || !enabled) setIsAnimatingTransform(false);

    const base = baseResultRef.current;
    if (base) setResult(base);
    const requestOptions = buildAnalyzeOptions({
      enableInterval: nextEnableInterval,
      enableLine: nextEnableLine,
      enableTransform: nextEnableTransform,
    });
    if (!requestOptions.interval && !requestOptions.line && !requestOptions.transform) {
      toolAbortRef.current?.abort();
      return;
    }
    void runTool(requestOptions);
  }

  function buildHistoryTools(): AnalyzeOptions {
    const options = buildAnalyzeOptions();
    return {
      parameters: options.parameters,
      parameter_mode: options.parameter_mode,
      interval: options.interval,
      line: options.line,
      transform: options.transform,
    };
  }

  return {
    expression,
    setExpression: setExpressionAndInvalidate,
    analysisState,
    parameterMode,
    parameterValue,
    curriculumProfile,
    setCurriculumProfile: setCurriculumProfileAndInvalidate,
    parameterDetected: containsParameterM(expression),
    setParameterMode: setParameterModeAndInvalidate,
    setParameterValue: setParameterValueAndInvalidate,
    loading,
    ocrLoading,
    ocrCandidate,
    ocrPreviewUrl,
    result,
    sessionResult: baseResultRef.current,
    historyTools: buildHistoryTools(),
    historyWindow: result?.graph_analysis_v2?.window,
    parameterSnapshots,
    saveParameterSnapshot,
    removeParameterSnapshot,
    clearParameterSnapshots: () => setParameterSnapshots([]),
    error,
    intervalA,
    intervalB,
    intervalOpenA,
    intervalOpenB,
    enableInterval,
    lineK,
    lineB,
    lineMode,
    lineX0,
    enableLine,
    enableTransform,
    transformType,
    transformValue,
    isAnimatingTransform,
    animationFps,
    handleAnalyze,
    openHistoryItem,
    handleConfirmOcr,
    discardOcrCandidate,
    handleImageChange,
    updateToolEnabled,
    setIntervalA,
    setIntervalB,
    setIntervalOpenA,
    setIntervalOpenB,
    setLineK,
    setLineB,
    setLineMode,
    setLineX0,
    setTransformType: setTransformTypeAndReset,
    setTransformValue,
    setAnimationFps,
    setIsAnimatingTransform,
    resetTransformAnimation,
    scheduleToolAnalyze,
  };
}

function containsParameterM(expression: string) {
  return /(^|[^A-Za-z0-9_])m([^A-Za-z0-9_]|$)/.test(expression);
}

function formatAnalyzeError(response: AnalyzeResponse): string {
  if (!response.error_code) return response.error ?? 'Không thể phân tích hàm số.';
  return `${response.error ?? 'Không thể phân tích hàm số.'} Mã lỗi: ${response.error_code}.`;
}

function buildTransformCommands(baseCommands: string[], expression: string) {
  return [
    ...stripToolCommands(baseCommands),
    `h(x)=${expression}`,
    'SetColor(f, "#94a3b8")',
    'SetLineThickness(f, 2)',
    'SetColor(h, "#111827")',
    'SetLineThickness(h, 5)',
  ];
}

function stripToolCommands(commands: string[]) {
  return commands.filter((command) => !/^\s*(h\(x\)\s*=|g\(x\)\s*=|Set(Color|LineThickness)\((f|g|h),)/i.test(command));
}

function requiresTransformValue(type: AnalyzeTransformType) {
  return ['vertical_shift', 'horizontal_shift', 'vertical_scale', 'horizontal_scale'].includes(type);
}

function instantiateTransformTemplate(template: string, value: number) {
  const expression = template.replace(/^g\(x\)=/, '');
  return expression.replace(/\ba\b/g, `(${formatToolNumber(value)})`);
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function formatToolNumber(value: number) {
  if (!Number.isFinite(value)) return '0';
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}
