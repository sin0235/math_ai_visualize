import { useEffect, useRef, useState } from 'react';
import { analyzeFunction, analyzeFunctionImage, type AnalyzeOptions, type AnalyzeResponse } from '../../api/client';

type ToolKey = 'interval' | 'line' | 'transform';

type AnalyzeOptionOverrides = Partial<AnalyzeOptions & {
  intervalA: number;
  intervalB: number;
  enableInterval: boolean;
  lineK: number;
  lineB: number;
  enableLine: boolean;
  transformType: string;
  transformValue: number;
  enableTransform: boolean;
}>;

export function useFunctionAnalysis(initialExpression: string, onWarnings?: (warnings: string[]) => void) {
  const [expression, setExpression] = useState(initialExpression);
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [intervalA, setIntervalA] = useState(-2);
  const [intervalB, setIntervalB] = useState(2);
  const [enableInterval, setEnableInterval] = useState(false);
  const [lineK, setLineK] = useState(1);
  const [lineB, setLineB] = useState(0);
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
    const nextEnableLine = overrides?.enableLine ?? enableLine;
    const nextLineK = overrides?.lineK ?? lineK;
    const nextLineB = overrides?.lineB ?? lineB;
    const nextEnableTransform = overrides?.enableTransform ?? enableTransform;
    const nextTransformType = overrides?.transformType ?? transformType;
    const nextTransformValue = overrides?.transformValue ?? transformValue;
    return {
      ...(nextEnableInterval ? { interval: { a: nextIntervalA, b: nextIntervalB } } : {}),
      ...(nextEnableLine ? { line: { k: nextLineK, b: nextLineB } } : {}),
      ...(nextEnableTransform ? { transform: { type: nextTransformType, value: nextTransformValue } } : {}),
    };
  }

  function scheduleToolAnalyze(overrides?: AnalyzeOptionOverrides) {
    const expr = expression.trim();
    if (!expr || !result) return;
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    sliderDebounceRef.current = window.setTimeout(() => {
      void runAnalyze(expr, { slider: true, requestOptions: buildAnalyzeOptions(overrides) });
    }, 220);
  }

  async function runAnalyze(expr: string, options?: { slider?: boolean; clearResult?: boolean; requestOptions?: AnalyzeOptions }) {
    const requestId = ++analyzeRequestRef.current;
    if (!options?.slider) setLoading(true);
    setError(null);
    if (options?.clearResult) setResult(null);
    try {
      const res = await analyzeFunction(expr, options?.requestOptions ?? {});
      if (requestId !== analyzeRequestRef.current) return;
      if (res.error) setError(res.error);
      else {
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
      const res = await analyzeFunctionImage(await readFileAsDataUrl(file));
      if (requestId !== analyzeRequestRef.current) return;
      if (res.ocr_expression) setExpression(res.ocr_expression);
      if (res.error) setError(res.error);
      else {
        setResult(res);
        onWarnings?.(res.warnings);
      }
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current) setError(e instanceof Error ? e.message : 'Lỗi OCR không xác định.');
    } finally {
      if (requestId === analyzeRequestRef.current) setOcrLoading(false);
    }
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

    scheduleToolAnalyze({
      enableInterval: nextEnableInterval,
      enableLine: nextEnableLine,
      enableTransform: nextEnableTransform,
    });
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
    enableInterval,
    lineK,
    lineB,
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
    setLineK,
    setLineB,
    setTransformType,
    setTransformValue,
    setIsAnimatingTransform,
    scheduleToolAnalyze,
  };
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Không đọc được ảnh.'));
    reader.readAsDataURL(file);
  });
}
