import { useEffect, useRef, useState } from 'react';
import { analyzeFunction, analyzeFunctionImageFile, type AnalyzeOptions, type AnalyzeResponse } from '../../api/client';

type ToolKey = 'interval' | 'line' | 'transform';

type AnalyzeOptionOverrides = Partial<AnalyzeOptions & {
  intervalA: number;
  intervalB: number;
  intervalOpenA: boolean;
  intervalOpenB: boolean;
  enableInterval: boolean;
  lineK: number;
  lineB: number;
  lineMode: string;
  lineX0: number;
  enableLine: boolean;
  transformType: string;
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
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [intervalA, setIntervalA] = useState(-2);
  const [intervalB, setIntervalB] = useState(2);
  const [intervalOpenA, setIntervalOpenA] = useState(false);
  const [intervalOpenB, setIntervalOpenB] = useState(false);
  const [enableInterval, setEnableInterval] = useState(false);
  const [lineK, setLineK] = useState(1);
  const [lineB, setLineB] = useState(0);
  const [lineMode, setLineMode] = useState('intersect');
  const [lineX0, setLineX0] = useState(0);
  const [enableLine, setEnableLine] = useState(false);
  const [enableTransform, setEnableTransform] = useState(false);
  const [transformType, setTransformType] = useState('vertical_shift');
  const [transformValue, setTransformValue] = useState(1);
  const [isAnimatingTransform, setIsAnimatingTransform] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const analyzeRequestRef = useRef(0);
  const sliderDebounceRef = useRef<number | null>(null);
  const animationRef = useRef<number | null>(null);
  const baseResultRef = useRef<AnalyzeResponse | null>(null);

  useEffect(() => {
    return () => {
      if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
    };
  }, []);

  useEffect(() => {
    if (!isAnimatingTransform) {
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
      animationRef.current = null;
      return;
    }
    animationRef.current = window.setInterval(() => {
      setTransformValue((current) => {
        const next = current >= 3 ? -3 : Number((current + 0.1).toFixed(2));
        scheduleToolAnalyze({ transformValue: next, enableTransform: true });
        return next;
      });
    }, 160);
    return () => {
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
      animationRef.current = null;
    };
  }, [isAnimatingTransform, expression, enableInterval, intervalA, intervalB, enableLine, lineK, lineB, transformType]);

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
      ...(nextEnableInterval ? { interval: { a: nextIntervalA, b: nextIntervalB, open_a: nextIntervalOpenA, open_b: nextIntervalOpenB } } : {}),
      ...(nextEnableLine ? { line: { k: nextLineK, b: nextLineB, mode: nextLineMode, x0: nextLineX0 } } : {}),
      ...(nextEnableTransform ? { transform: { type: nextTransformType, value: nextTransformValue } } : {}),
    };
  }

  function scheduleToolAnalyze(overrides?: AnalyzeOptionOverrides) {
    const expr = expression.trim();
    if (!expr || !result) return;
    const requestOptions = buildAnalyzeOptions(overrides);
    if (requestOptions.transform && !requestOptions.interval && !requestOptions.line) {
      applyLocalTransform(requestOptions.transform);
      return;
    }
    if (!requestOptions.interval && !requestOptions.line && !requestOptions.transform) {
      analyzeRequestRef.current += 1;
      setResult(baseResultRef.current ?? stripToolArtifacts(result));
      return;
    }
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    sliderDebounceRef.current = window.setTimeout(() => {
      void runAnalyze(expr, { slider: true, requestOptions });
    }, 280);
  }

  async function runAnalyze(expr: string, options?: { slider?: boolean; clearResult?: boolean; requestOptions?: AnalyzeOptions }) {
    const requestId = ++analyzeRequestRef.current;
    if (!options?.slider) setLoading(true);
    setError(null);
    if (options?.clearResult) setResult(null);
    try {
      const res = await analyzeFunction(expr, options?.requestOptions ?? {});
      if (requestId !== analyzeRequestRef.current) return;
      if (res.error) setError(formatAnalyzeError(res));
      else {
        if (!options?.slider) baseResultRef.current = stripToolArtifacts(res);
        setResult(res);
        if (!options?.slider) onWarnings?.(res.warnings);
      }
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current) setError(e instanceof Error ? e.message : 'Lỗi không xác định.');
    } finally {
      if (requestId === analyzeRequestRef.current && !options?.slider) setLoading(false);
    }
  }

  async function handleAnalyze() {
    const expr = expression.trim();
    if (!expr) return;
    await runAnalyze(expr, { clearResult: true, requestOptions: buildAnalyzeOptions() });
  }

  async function handleImageChange(file?: File) {
    if (!file) return;
    const requestId = ++analyzeRequestRef.current;
    setOcrLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyzeFunctionImageFile(file);
      if (requestId !== analyzeRequestRef.current) return;
      if (res.ocr_expression) setExpression(res.ocr_expression);
      if (res.error) setError(formatAnalyzeError(res));
      else {
        baseResultRef.current = stripToolArtifacts(res);
        setResult(res);
        onWarnings?.(res.warnings);
      }
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current) setError(e instanceof Error ? e.message : 'Lỗi OCR không xác định.');
    } finally {
      if (requestId === analyzeRequestRef.current) setOcrLoading(false);
    }
  }

  function applyLocalTransform(transform: NonNullable<AnalyzeOptions['transform']>, baseOverride?: AnalyzeResponse | null) {
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    analyzeRequestRef.current += 1;
    const base = baseOverride ?? baseResultRef.current ?? (result ? stripToolArtifacts(result) : null);
    if (!base) return;
    const preview = buildLocalTransformPreview(transform.type, transform.value);
    setResult({
      ...base,
      transform_preview: preview,
      geogebra_commands: buildLocalTransformCommands(base.geogebra_commands, preview.expression),
    });
  }

  function updateToolEnabled(key: ToolKey, enabled: boolean) {
    const nextEnableInterval = key === 'interval' ? enabled : false;
    const nextEnableLine = key === 'line' ? enabled : false;
    const nextEnableTransform = key === 'transform' ? enabled : false;

    setEnableInterval(nextEnableInterval);
    setEnableLine(nextEnableLine);
    setEnableTransform(nextEnableTransform);
    if (key === 'transform') {
      if (!enabled) setIsAnimatingTransform(false);
    } else {
      setIsAnimatingTransform(false);
    }

    const baseResult = baseResultRef.current ?? (result ? stripToolArtifacts(result) : null);
    if (baseResult) setResult(baseResult);

    const requestOptions = buildAnalyzeOptions({
      enableInterval: nextEnableInterval,
      enableLine: nextEnableLine,
      enableTransform: nextEnableTransform,
    });
    if (requestOptions.transform && !requestOptions.interval && !requestOptions.line) {
      applyLocalTransform(requestOptions.transform, baseResult);
      return;
    }
    if (!requestOptions.interval && !requestOptions.line && !requestOptions.transform) {
      analyzeRequestRef.current += 1;
      return;
    }

    const expr = expression.trim();
    if (!expr) return;
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    void runAnalyze(expr, { slider: true, requestOptions });
  }

  return {
    expression,
    setExpression,
    loading,
    ocrLoading,
    result,
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
    handleAnalyze,
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
    setTransformType,
    setTransformValue,
    setIsAnimatingTransform,
    scheduleToolAnalyze,
  };
}

function formatAnalyzeError(response: AnalyzeResponse): string {
  if (!response.error_code) return response.error ?? 'Không thể phân tích hàm số.';
  return `${response.error ?? 'Không thể phân tích hàm số.'} Mã lỗi: ${response.error_code}.`;
}

function stripToolArtifacts(result: AnalyzeResponse): AnalyzeResponse {
  return {
    ...result,
    interval_analysis: null,
    line_analysis: null,
    transform_preview: null,
    geogebra_commands: stripToolCommands(result.geogebra_commands),
    graph_scene: result.graph_scene
      ? {
          ...result.graph_scene,
          objects: result.graph_scene.objects.map((object) => object.type === 'function_graph' ? { ...object, domain: null } : object),
        }
      : result.graph_scene,
  };
}

function stripToolCommands(commands: string[]) {
  return commands.filter((command) => !/^\s*(h\(x\)\s*=|g\(x\)\s*=|Set(Color|LineThickness)\((f|g|h),)/i.test(command));
}

function buildLocalTransformPreview(type: string, value: number): NonNullable<AnalyzeResponse['transform_preview']> {
  const a = formatToolNumber(value);
  const meta = localTransformMeta(type, a);
  return {
    type,
    value: a,
    label: meta.label,
    expression: meta.expression,
    expression_latex: meta.expressionLatex,
    pedagogical_steps: meta.steps,
  };
}

function buildLocalTransformCommands(baseCommands: string[], expression: string) {
  return [
    ...stripToolCommands(baseCommands),
    `h(x)=${expression}`,
    'SetColor(f, "#94a3b8")',
    'SetLineThickness(f, 2)',
    'SetColor(h, "#111827")',
    'SetLineThickness(h, 5)',
  ];
}

function localTransformMeta(type: string, a: string) {
  const signedA = signedToolNumber(a);
  switch (type) {
    case 'horizontal_shift':
      return { label: `f(x${signedA})`, expression: `f(x${signedA})`, expressionLatex: `f(x${signedA})`, steps: [`Dịch đồ thị theo phương ngang với tham số a = ${a}.`] };
    case 'vertical_scale':
      return { label: `${a}f(x)`, expression: `${a}*f(x)`, expressionLatex: `${a}f(x)`, steps: [`Kéo dãn/co đồ thị theo phương thẳng đứng với hệ số ${a}.`] };
    case 'horizontal_scale':
      return { label: `f(${a}x)`, expression: `f(${a}*x)`, expressionLatex: `f(${a}x)`, steps: [`Kéo dãn/co đồ thị theo phương ngang với hệ số ${a}.`] };
    case 'reflect_x':
      return { label: '-f(x)', expression: '-f(x)', expressionLatex: '-f(x)', steps: ['Lấy đối xứng toàn bộ đồ thị qua trục hoành.'] };
    case 'reflect_y':
      return { label: 'f(-x)', expression: 'f(-x)', expressionLatex: 'f(-x)', steps: ['Lấy đối xứng toàn bộ đồ thị qua trục tung.'] };
    case 'absolute_all':
      return { label: '|f(x)|', expression: 'abs(f(x))', expressionLatex: '|f(x)|', steps: ['Giữ phần phía trên trục hoành, đối xứng phần phía dưới lên trên.'] };
    case 'absolute_x':
      return { label: 'f(|x|)', expression: 'f(abs(x))', expressionLatex: 'f(|x|)', steps: ['Giữ nửa phải đồ thị rồi đối xứng qua trục tung.'] };
    default:
      return { label: `f(x)${signedA}`, expression: `f(x)${signedA}`, expressionLatex: `f(x)${signedA}`, steps: [`Tịnh tiến đồ thị theo phương thẳng đứng với a = ${a}.`] };
  }
}

function signedToolNumber(value: string) {
  return value.startsWith('-') ? value : `+${value}`;
}

function formatToolNumber(value: number) {
  if (!Number.isFinite(value)) return '0';
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}
