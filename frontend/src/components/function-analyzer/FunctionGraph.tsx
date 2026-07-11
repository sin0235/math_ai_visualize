import { Component, useCallback, useEffect, useId, useMemo, useRef, useState, type ErrorInfo, type ReactNode } from 'react';
import { GeoGebraView } from '../GeoGebraView';
import type { AnalyzeResponse, GraphAnalysisV2, GraphSegmentV2 } from '../../api/client';
import { sampleFunctionGraph } from '../../api/client';
import type { MathScene } from '../../types/scene';
import { reportClientError } from '../../utils/telemetry';

type RendererMode = 'auto' | 'geogebra' | 'svg';
type GeoGebraStatus = 'loading' | 'ready' | 'error';
type GraphTracePoint = { graphX: number; graphY: number; x: number; y: number };

export function FunctionGraph({ result }: { result: AnalyzeResponse }) {
  const legacyData = result.graph_points || [];
  const [sampledGraph, setSampledGraph] = useState<GraphAnalysisV2 | null>(null);
  const [fitMode, setFitMode] = useState<'auto' | 'domain' | 'manual'>('auto');
  const [showGrid, setShowGrid] = useState(true);
  const [showAxes, setShowAxes] = useState(true);
  const [showAsymptotes, setShowAsymptotes] = useState(true);
  const [showPoints, setShowPoints] = useState(true);
  const [showDerivative, setShowDerivative] = useState(false);
  const [showSecondDerivative, setShowSecondDerivative] = useState(false);
  const [showToolOverlay, setShowToolOverlay] = useState(true);
  const [overlayGraphs, setOverlayGraphs] = useState<Partial<Record<string, GraphAnalysisV2>>>({});
  const [tracePoint, setTracePoint] = useState<GraphTracePoint | null>(null);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const viewportTimerRef = useRef<number | null>(null);
  const viewportAbortRef = useRef<AbortController | null>(null);
  const overlayAbortRef = useRef<AbortController | null>(null);
  const viewportRequestRef = useRef(0);
  const segments = useMemo<GraphSegmentV2[]>(() => (
    sampledGraph?.segments ?? result.graph_analysis_v2?.segments ?? [legacySegment(legacyData)]
  ).filter((segment) => segment.points.length > 0), [legacyData, result.graph_analysis_v2, sampledGraph]);
  const graph = useMemo(() => buildSvgGraph(segments, result, fitMode === 'domain'), [fitMode, segments, result]);
  const svgId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);
  const [view, setView] = useState({ scale: 1, tx: 0, ty: 0 });
  const [rendererMode, setRendererMode] = useState<RendererMode>('geogebra');
  const [geogebraStatus, setGeogebraStatus] = useState<GeoGebraStatus>('loading');
  const [rendererAttempt, setRendererAttempt] = useState(0);
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const flatData = useMemo(() => segments.flatMap((segment) => segment.points), [segments]);
  const specialPoints = flatData.length >= 2 ? plotSpecialPoints(result, graph.project, SVG_WIDTH, SVG_HEIGHT, 28) : plotSpecialPoints(result, projectFallbackPoint, SVG_WIDTH, SVG_HEIGHT, 28);
  const visibleSpecialPoints = specialPoints.filter((point) => point.x >= 0 && point.x <= SVG_WIDTH && point.y >= 0 && point.y <= SVG_HEIGHT);
  const selectedPoint = visibleSpecialPoints.find((point) => point.key === selectedPointKey) ?? null;
  const asymptoteLines = useMemo(() => plotAsymptotes(result, graph.project, graph.bounds), [graph, result]);
  const derivativePaths = useMemo(() => projectOverlayPaths(overlayGraphs.derivative, graph.project, graph.bounds), [graph, overlayGraphs.derivative]);
  const secondDerivativePaths = useMemo(() => projectOverlayPaths(overlayGraphs.secondDerivative, graph.project, graph.bounds), [graph, overlayGraphs.secondDerivative]);
  const linePaths = useMemo(() => Object.entries(overlayGraphs)
    .filter(([key]) => key.startsWith('line-'))
    .flatMap(([, overlay]) => projectOverlayPaths(overlay, graph.project, graph.bounds)), [graph, overlayGraphs]);
  const intervalHighlights = useMemo(() => plotIntervalHighlights(result.interval_analysis, graph.project, graph.bounds), [graph, result.interval_analysis]);
  const verticalToolLine = useMemo(() => plotVerticalToolLine(result.line_analysis, graph.project), [graph, result.line_analysis]);
  const hasGeoGebra = result.geogebra_commands.length > 0;
  const commandSignature = result.geogebra_commands.join('\n');
  const activeRenderer = rendererMode === 'svg' || !hasGeoGebra || (rendererMode === 'auto' && geogebraStatus === 'error') ? 'svg' : 'geogebra';
  const derivativeExpression = result.derivative?.trim() || null;
  const secondDerivativeExpression = result.second_derivative?.trim() || null;
  const lineExpressions = useMemo(() => {
    const expressions = result.line_analysis?.graph_expressions?.length
      ? result.line_analysis.graph_expressions
      : result.line_analysis?.graph_expression ? [result.line_analysis.graph_expression] : [];
    return expressions.map((expression) => expression.trim()).filter(Boolean);
  }, [result.line_analysis?.graph_expression, result.line_analysis?.graph_expressions]);

  useEffect(() => {
    setRendererMode('geogebra');
    setGeogebraStatus('loading');
    setSampledGraph(null);
    setFitMode('auto');
    setView({ scale: 1, tx: 0, ty: 0 });
    setSelectedPointKey(null);
    setTracePoint(null);
    setOverlayGraphs({});
    setShowDerivative(false);
    setShowSecondDerivative(false);
    setShowToolOverlay(true);
    setExportStatus(null);
  }, [result.expression, commandSignature]);

  const handleGeoGebraStatus = useCallback((status: GeoGebraStatus, detail?: string) => {
    setGeogebraStatus(status);
    if (status === 'error') {
      reportClientError({
        message: detail || 'GeoGebra renderer failed',
        error_code: 'FUNCTION_GRAPH_GEOGEBRA_FAILED',
        component: 'FunctionGraph',
        metadata: { kind: 'renderer', feature: 'function_graph' },
      });
    }
  }, []);

  useEffect(() => {
    if (activeRenderer !== 'svg' || (view.scale === 1 && view.tx === 0)) return;
    if (viewportTimerRef.current !== null) window.clearTimeout(viewportTimerRef.current);
    viewportAbortRef.current?.abort();
    const requestId = ++viewportRequestRef.current;
    viewportTimerRef.current = window.setTimeout(() => {
      const controller = new AbortController();
      viewportAbortRef.current = controller;
      const plotWidth = SVG_WIDTH - 56;
      const toGraphX = (screenX: number) => {
        const untransformedX = (screenX - view.tx) / view.scale;
        return graph.bounds.left + ((untransformedX - 28) / plotWidth) * (graph.bounds.right - graph.bounds.left);
      };
      const xMin = toGraphX(28);
      const xMax = toGraphX(SVG_WIDTH - 28);
      if (!Number.isFinite(xMin) || !Number.isFinite(xMax) || xMin >= xMax) return;
      void sampleFunctionGraph(
        result.evaluated_expression || result.expression,
        { x_min: xMin, x_max: xMax },
        { max_points: result.graph_analysis_v2?.max_points ?? 500 },
        controller.signal,
      ).then((response) => {
        if (requestId !== viewportRequestRef.current) return;
        setSampledGraph(response.graph_analysis_v2);
        setView({ scale: 1, tx: 0, ty: 0 });
      }).catch((error: unknown) => {
        if (requestId !== viewportRequestRef.current || isAbortError(error)) return;
        reportClientError({
          message: error instanceof Error ? error.message : 'Graph viewport sampling failed',
          error_code: 'FUNCTION_GRAPH_SAMPLING_FAILED',
          component: 'FunctionGraph',
          metadata: { kind: 'sampling', feature: 'function_graph' },
        });
      });
    }, 350);
    return () => {
      if (viewportTimerRef.current !== null) window.clearTimeout(viewportTimerRef.current);
      viewportAbortRef.current?.abort();
    };
  }, [activeRenderer, graph.bounds.left, graph.bounds.right, result.evaluated_expression, result.expression, result.graph_analysis_v2?.max_points, view]);

  useEffect(() => {
    overlayAbortRef.current?.abort();
    setOverlayGraphs({});
    if (activeRenderer !== 'svg') return;
    const requested = [
      ...(showDerivative && derivativeExpression ? [['derivative', derivativeExpression] as const] : []),
      ...(showSecondDerivative && secondDerivativeExpression ? [['secondDerivative', secondDerivativeExpression] as const] : []),
      ...(showToolOverlay ? lineExpressions.map((expression, index) => [`line-${index}`, expression] as const) : []),
    ];
    if (!requested.length) {
      return;
    }
    const controller = new AbortController();
    overlayAbortRef.current = controller;
    const timer = window.setTimeout(() => {
      void Promise.allSettled(requested.map(async ([key, expression]) => {
        const response = await sampleFunctionGraph(
          expression,
          { x_min: graph.bounds.left, x_max: graph.bounds.right },
          { max_points: Math.min(result.graph_analysis_v2?.max_points ?? 500, 500) },
          controller.signal,
        );
        return [key, response.graph_analysis_v2] as const;
      })).then((results) => {
        if (controller.signal.aborted) return;
        const entries = results.flatMap((entry) => entry.status === 'fulfilled' ? [entry.value] : []);
        setOverlayGraphs(Object.fromEntries(entries));
        const failed = results.find((entry) => entry.status === 'rejected');
        if (failed?.status === 'rejected' && !isAbortError(failed.reason)) {
          reportClientError({
            message: failed.reason instanceof Error ? failed.reason.message : 'Graph overlay sampling failed',
            error_code: 'FUNCTION_GRAPH_OVERLAY_FAILED',
            component: 'FunctionGraph',
            metadata: { kind: 'sampling', feature: 'function_graph_overlay' },
          });
        }
      });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [activeRenderer, derivativeExpression, graph.bounds.left, graph.bounds.right, lineExpressions, result.graph_analysis_v2?.max_points, secondDerivativeExpression, showDerivative, showSecondDerivative, showToolOverlay]);

  useEffect(() => () => {
    viewportRequestRef.current += 1;
    viewportAbortRef.current?.abort();
    overlayAbortRef.current?.abort();
    if (viewportTimerRef.current !== null) window.clearTimeout(viewportTimerRef.current);
  }, []);

  if (result.requires_substitution_for_graph) {
    return <div className="info-box">Chọn một giá trị exact của m để dựng đồ thị.</div>;
  }

  if (activeRenderer === 'geogebra') {
    const scene = result.graph_scene ?? createFallbackGraphScene(result.expression);
    return (
      <div className="fa2-graph-card fa2-geogebra-graph-card">
        <GraphRendererToolbar
          active="geogebra"
          status={geogebraStatus}
          onSelect={setRendererMode}
          commands={result.geogebra_commands}
          onRetry={() => {
            setGeogebraStatus('loading');
            setRendererAttempt((attempt) => attempt + 1);
          }}
        />
        <RendererErrorBoundary
          key={rendererAttempt}
          onError={(error) => handleGeoGebraStatus('error', error.message)}
        >
          <GeoGebraView
            key={rendererAttempt}
            commands={result.geogebra_commands}
            renderer="geogebra_2d"
            scene={scene}
            view={scene.view}
            viewBounds={graph.bounds}
            onStatusChange={handleGeoGebraStatus}
            embedded
          />
        </RendererErrorBoundary>
      </div>
    );
  }
  if (flatData.length < 2) return <div className="info-box">Chưa đủ dữ liệu để vẽ đồ thị.</div>;

  const clipId = `${svgId}-clip`;
  const scaleMin = 0.7;
  const scaleMax = 5;

  function toLocalPoint(clientX: number, clientY: number) {
    const svg = svgRef.current;
    if (!svg) return { x: SVG_WIDTH / 2, y: SVG_HEIGHT / 2 };
    const rect = svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * SVG_WIDTH;
    const y = ((clientY - rect.top) / rect.height) * SVG_HEIGHT;
    return { x, y };
  }

  function zoomAt(multiplier: number, clientX?: number, clientY?: number) {
    setFitMode('manual');
    setView((current) => {
      const nextScale = Math.max(scaleMin, Math.min(scaleMax, current.scale * multiplier));
      if (Math.abs(nextScale - current.scale) < 1e-6) return current;
      const focus = clientX !== undefined && clientY !== undefined
        ? toLocalPoint(clientX, clientY)
        : { x: SVG_WIDTH / 2, y: SVG_HEIGHT / 2 };
      const ratio = nextScale / current.scale;
      return {
        scale: nextScale,
        tx: focus.x - (focus.x - current.tx) * ratio,
        ty: focus.y - (focus.y - current.ty) * ratio,
      };
    });
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    zoomAt(event.deltaY < 0 ? 1.14 : 1 / 1.14, event.clientX, event.clientY);
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      const local = toLocalPoint(event.clientX, event.clientY);
      setTracePoint(nearestTracePoint(segments, graph.project, view, local));
      return;
    }
    const deltaX = event.clientX - drag.x;
    const deltaY = event.clientY - drag.y;
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
    setFitMode('manual');
    setTracePoint(null);
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    setView((current) => ({
      ...current,
      tx: current.tx + (deltaX / rect.width) * SVG_WIDTH,
      ty: current.ty + (deltaY / rect.height) * SVG_HEIGHT,
    }));
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  }

  function handleGraphKeyDown(event: React.KeyboardEvent<SVGSVGElement>) {
    const panStep = 18;
    if (event.key === '+' || event.key === '=') {
      event.preventDefault();
      zoomAt(1.14);
    } else if (event.key === '-') {
      event.preventDefault();
      zoomAt(1 / 1.14);
    } else if (event.key.startsWith('Arrow')) {
      event.preventDefault();
      setFitMode('manual');
      setView((current) => ({
        ...current,
        tx: current.tx + (event.key === 'ArrowLeft' ? panStep : event.key === 'ArrowRight' ? -panStep : 0),
        ty: current.ty + (event.key === 'ArrowUp' ? panStep : event.key === 'ArrowDown' ? -panStep : 0),
      }));
    } else if (event.key === 'Home') {
      event.preventDefault();
      setFitMode('auto');
      setView({ scale: 1, tx: 0, ty: 0 });
    }
  }

  function selectFitMode(mode: 'auto' | 'domain') {
    viewportAbortRef.current?.abort();
    setSampledGraph(null);
    setFitMode(mode);
    setView({ scale: 1, tx: 0, ty: 0 });
  }

  async function exportSvg() {
    const svg = svgRef.current;
    if (!svg) return;
    downloadBlob(serializeGraphSvg(svg), `do-thi-${safeFileName(result.expression)}.svg`, 'image/svg+xml');
    setExportStatus('Đã tải SVG.');
  }

  async function exportPng() {
    const svg = svgRef.current;
    if (!svg) return;
    try {
      const source = serializeGraphSvg(svg);
      const image = await loadSvgImage(source);
      const canvas = document.createElement('canvas');
      canvas.width = SVG_WIDTH * 2;
      canvas.height = SVG_HEIGHT * 2;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Canvas 2D unavailable');
      context.scale(2, 2);
      context.drawImage(image, 0, 0, SVG_WIDTH, SVG_HEIGHT);
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('PNG encode failed')), 'image/png'));
      downloadExistingBlob(blob, `do-thi-${safeFileName(result.expression)}.png`);
      setExportStatus('Đã tải PNG.');
    } catch {
      setExportStatus('Không thể xuất PNG trên trình duyệt này.');
    }
  }

  return (
    <div className="fa2-graph-card">
      <div className="fa2-graph-primary-toolbar" aria-label="Điều khiển đồ thị">
        <button type="button" className="sp-btn-secondary" aria-pressed={fitMode === 'auto'} onClick={() => selectFitMode('auto')}>Tự căn</button>
        <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1.14)} aria-label="Phóng to">+</button>
        <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1 / 1.14)} aria-label="Thu nhỏ">−</button>
        <button type="button" className="sp-btn-secondary" onClick={() => selectFitMode('auto')}>Đặt lại</button>
        <details className="fa2-graph-settings">
          <summary>Tùy chỉnh đồ thị</summary>
          <div className="fa2-graph-settings-panel">
            <GraphRendererToolbar
              active="svg"
              status={geogebraStatus}
              onSelect={setRendererMode}
              commands={result.geogebra_commands}
              onRetry={() => {
                setGeogebraStatus('loading');
                setRendererMode('geogebra');
                setRendererAttempt((attempt) => attempt + 1);
              }}
            />
            <div className="fa2-graph-toolbar-actions" role="group" aria-label="Chế độ căn khung">
              <button type="button" className="sp-btn-secondary" aria-pressed={fitMode === 'domain'} onClick={() => selectFitMode('domain')}>Theo miền</button>
            </div>
            <div className="fa2-graph-toggle-list" role="group" aria-label="Lớp hiển thị">
              <GraphToggle label="Lưới" checked={showGrid} onChange={setShowGrid} />
              <GraphToggle label="Trục" checked={showAxes} onChange={setShowAxes} />
              <GraphToggle label="Tiệm cận" checked={showAsymptotes} onChange={setShowAsymptotes} />
              <GraphToggle label="Điểm" checked={showPoints} onChange={setShowPoints} />
              <GraphToggle label="f′" checked={showDerivative} onChange={setShowDerivative} disabled={!derivativeExpression} />
              <GraphToggle label="f″" checked={showSecondDerivative} onChange={setShowSecondDerivative} disabled={!secondDerivativeExpression} />
              <GraphToggle label="Công cụ" checked={showToolOverlay} onChange={setShowToolOverlay} disabled={!result.interval_analysis && !result.line_analysis} />
            </div>
            <div className="fa2-graph-toolbar-actions">
              <button type="button" className="sp-btn-secondary" onClick={exportSvg}>Tải SVG</button>
              <button type="button" className="sp-btn-secondary" onClick={() => void exportPng()}>Tải PNG</button>
            </div>
          </div>
        </details>
      </div>
      {exportStatus && <span className="fa2-graph-status" role="status">{exportStatus}</span>}
      <p id={`${svgId}-description`} className="sr-only">
        Đồ thị hàm {result.expression}. Dùng phím mũi tên để di chuyển, phím cộng hoặc trừ để thu phóng, phím Home để đặt lại. Trạng thái phân tích đồ thị: {result.graph_analysis_v2?.status ?? 'legacy'}.
      </p>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        role="img"
        tabIndex={0}
        aria-label={`Đồ thị y = ${result.expression}`}
        aria-describedby={`${svgId}-description`}
        className="fa2-svg-graph"
        onKeyDown={handleGraphKeyDown}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onPointerLeave={() => setTracePoint(null)}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" />
          </clipPath>
        </defs>
        <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" className="fa2-graph-bg" />
        <g clipPath={`url(#${clipId})`} transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
          {showGrid && graph.grid.map((line, i) => <line key={`grid-${i}`} {...line} className="fa2-graph-grid" />)}
          {showToolOverlay && intervalHighlights.map((highlight) => <rect key={highlight.key} {...highlight.rect} className="fa2-graph-interval-highlight" />)}
          {showAxes && <line x1={graph.xAxis.x1} y1={graph.xAxis.y1} x2={graph.xAxis.x2} y2={graph.xAxis.y2} className="fa2-graph-axis" />}
          {showAxes && <line x1={graph.yAxis.x1} y1={graph.yAxis.y1} x2={graph.yAxis.x2} y2={graph.yAxis.y2} className="fa2-graph-axis" />}
          {showAsymptotes && asymptoteLines.map((line) => <line key={line.key} {...line.coords} className="fa2-graph-asymptote" />)}
          {showDerivative && derivativePaths.map((path, index) => <path key={`derivative-${index}`} d={path} className="fa2-graph-overlay fa2-graph-derivative" />)}
          {showSecondDerivative && secondDerivativePaths.map((path, index) => <path key={`second-derivative-${index}`} d={path} className="fa2-graph-overlay fa2-graph-second-derivative" />)}
          {showToolOverlay && linePaths.map((path, index) => <path key={`line-tool-${index}`} d={path} className="fa2-graph-overlay fa2-graph-tool-line" />)}
          {showToolOverlay && verticalToolLine && <line {...verticalToolLine} className="fa2-graph-overlay fa2-graph-tool-line" />}
          {graph.paths.map((path, i) => <path key={`path-${i}`} d={path} className="fa2-graph-path" />)}
          {showPoints && graph.endpointMarkers.map((point) => (
            <circle
              key={point.key}
              cx={point.x}
              cy={point.y}
              r="4.5"
              className={`fa2-graph-endpoint ${point.open ? 'is-open' : 'is-closed'}`}
              aria-hidden="true"
            />
          ))}
          {showPoints && visibleSpecialPoints.map((point) => (
            <g
              key={point.key}
              className="fa2-graph-special-point"
              role="button"
              tabIndex={0}
              aria-label={`${point.label} ${point.coordsText}`}
              onClick={(event) => {
                event.stopPropagation();
                setSelectedPointKey(point.key);
              }}
              onPointerDown={(event) => event.stopPropagation()}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setSelectedPointKey(point.key);
                }
              }}
            >
              <circle cx={point.x} cy={point.y} r="6" className={`fa2-graph-point fa2-graph-point-${point.kind}`} />
              <text
                x={point.labelX}
                y={point.labelY}
                textAnchor={point.anchor}
                className="fa2-graph-label"
              >
                {point.label}
              </text>
            </g>
          ))}
          {showPoints && selectedPoint && (
            <g className="fa2-graph-point-popover" transform={`translate(${selectedPoint.popoverX} ${selectedPoint.popoverY})`}>
              <rect x="0" y="0" width={selectedPoint.popoverWidth} height="46" rx="10" />
              <text x="10" y="18" className="fa2-graph-popover-label">{selectedPoint.label}</text>
              <text x="10" y="36" className="fa2-graph-popover-coords">{selectedPoint.coordsText}</text>
            </g>
          )}
        </g>
        {tracePoint && (
          <g className="fa2-graph-trace" aria-hidden="true">
            <line x1={tracePoint.x} y1="28" x2={tracePoint.x} y2={SVG_HEIGHT - 28} />
            <line x1="28" y1={tracePoint.y} x2={SVG_WIDTH - 28} y2={tracePoint.y} />
            <circle cx={tracePoint.x} cy={tracePoint.y} r="4" />
            <text x={Math.min(tracePoint.x + 8, SVG_WIDTH - 150)} y={Math.max(tracePoint.y - 8, 18)}>{`(${shortNumber(tracePoint.graphX)}; ${shortNumber(tracePoint.graphY)})`}</text>
          </g>
        )}
        {showAxes && graph.xTicks.map((tick, idx) => (
          <text key={`xt-${idx}`} x={tick.x} y={SVG_HEIGHT - 6} className="fa2-graph-tick">{tick.label}</text>
        ))}
        {showAxes && graph.yTicks.map((tick, idx) => (
          <text key={`yt-${idx}`} x={6} y={tick.y + 4} className="fa2-graph-tick">{tick.label}</text>
        ))}
      </svg>
    </div>
  );
}

function GraphToggle({ label, checked, onChange, disabled = false }: { label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <label className={`fa2-graph-toggle ${disabled ? 'is-disabled' : ''}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function nearestTracePoint(
  segments: GraphSegmentV2[],
  project: (point: { x: number; y: number }) => { x: number; y: number },
  view: { scale: number; tx: number; ty: number },
  target: { x: number; y: number },
): GraphTracePoint | null {
  let nearest: GraphTracePoint | null = null;
  let nearestDistance = 18;
  for (const point of segments.flatMap((segment) => segment.points)) {
    if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) continue;
    const projected = project(point);
    const x = projected.x * view.scale + view.tx;
    const y = projected.y * view.scale + view.ty;
    const distance = Math.hypot(x - target.x, y - target.y);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearest = { graphX: point.x, graphY: point.y, x, y };
    }
  }
  return nearest;
}

function projectOverlayPaths(
  analysis: GraphAnalysisV2 | undefined,
  project: (point: { x: number; y: number }) => { x: number; y: number },
  bounds: { left: number; right: number },
) {
  if (!analysis) return [];
  return analysis.segments.flatMap((segment) => {
    const points = segment.points
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y) && point.x >= bounds.left && point.x <= bounds.right)
      .sort((left, right) => left.x - right.x);
    if (points.length < 2) return [];
    return [points.map((point, index) => {
      const screen = project(point);
      return `${index === 0 ? 'M' : 'L'} ${screen.x.toFixed(2)} ${screen.y.toFixed(2)}`;
    }).join(' ')];
  });
}

function plotIntervalHighlights(
  interval: AnalyzeResponse['interval_analysis'],
  project: (point: { x: number; y: number }) => { x: number; y: number },
  bounds: { left: number; right: number },
) {
  if (!interval?.domain_components?.length) return [];
  return interval.domain_components.flatMap((component, index) => {
    const left = component.start_approx ?? graphBoundaryNumber(component.start_exact, bounds.left, bounds.right);
    const right = component.end_approx ?? graphBoundaryNumber(component.end_exact, bounds.left, bounds.right);
    const clippedLeft = Math.max(bounds.left, left);
    const clippedRight = Math.min(bounds.right, right);
    if (!Number.isFinite(clippedLeft) || !Number.isFinite(clippedRight) || clippedLeft >= clippedRight) return [];
    const x1 = project({ x: clippedLeft, y: 0 }).x;
    const x2 = project({ x: clippedRight, y: 0 }).x;
    return [{ key: `interval-${index}-${component.start_exact}-${component.end_exact}`, rect: { x: Math.min(x1, x2), y: 28, width: Math.abs(x2 - x1), height: SVG_HEIGHT - 56 } }];
  });
}

function plotVerticalToolLine(
  line: AnalyzeResponse['line_analysis'],
  project: (point: { x: number; y: number }) => { x: number; y: number },
) {
  if (line?.kind !== 'vertical') return null;
  const x = Number(line.x0_exact ?? line.x0);
  if (!Number.isFinite(x)) return null;
  const screenX = project({ x, y: 0 }).x;
  return { x1: screenX, y1: 28, x2: screenX, y2: SVG_HEIGHT - 28 };
}

function graphBoundaryNumber(value: string, left: number, right: number) {
  if (value === '-oo' || value === '-∞') return left;
  if (value === 'oo' || value === '+∞' || value === '∞') return right;
  return Number(value);
}

function plotAsymptotes(
  result: AnalyzeResponse,
  project: (point: { x: number; y: number }) => { x: number; y: number },
  bounds: { left: number; right: number; bottom: number; top: number },
) {
  const vertical = (result.asymptotes_v2?.vertical ?? []).flatMap((item, index) => {
    const x = recordApprox(item, 'x_value', 'approx') ?? Number(result.vertical_asymptotes[index]?.x);
    if (!Number.isFinite(x)) return [];
    const projected = project({ x, y: 0 });
    return [{ key: `vertical-${index}-${x}`, coords: { x1: projected.x, y1: 28, x2: projected.x, y2: SVG_HEIGHT - 28 } }];
  });
  const horizontalValues = new Set<number>();
  const horizontal = (result.asymptotes_v2?.horizontal ?? []).flatMap((item, index) => {
    const y = recordApprox(item, 'value_v2', 'approx') ?? numericRecordValue(item, 'value_approx') ?? Number(result.horizontal_asymptotes[index]?.value);
    if (!Number.isFinite(y) || horizontalValues.has(y)) return [];
    horizontalValues.add(y);
    const projected = project({ x: 0, y });
    return [{ key: `horizontal-${index}-${y}`, coords: { x1: 28, y1: projected.y, x2: SVG_WIDTH - 28, y2: projected.y } }];
  });
  const oblique = (result.asymptotes_v2?.oblique ?? []).flatMap((item, index) => {
    const slope = recordApprox(item, 'slope_value', 'approx') ?? numericRecordValue(item, 'slope');
    const intercept = recordApprox(item, 'intercept_value', 'approx') ?? numericRecordValue(item, 'intercept');
    if (slope === null || intercept === null) return [];
    const start = project({ x: bounds.left, y: slope * bounds.left + intercept });
    const end = project({ x: bounds.right, y: slope * bounds.right + intercept });
    return [{ key: `oblique-${index}-${slope}-${intercept}`, coords: { x1: start.x, y1: start.y, x2: end.x, y2: end.y } }];
  });
  return [...vertical, ...horizontal, ...oblique];
}

function recordApprox(record: Record<string, unknown>, nestedKey: string, valueKey: string) {
  const nested = record[nestedKey];
  return nested && typeof nested === 'object' ? numericRecordValue(nested as Record<string, unknown>, valueKey) : null;
}

function numericRecordValue(record: Record<string, unknown>, key: string) {
  const value = record[key];
  const numeric = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : Number.NaN;
  return Number.isFinite(numeric) ? numeric : null;
}

function serializeGraphSvg(svg: SVGSVGElement) {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', String(SVG_WIDTH));
  clone.setAttribute('height', String(SVG_HEIGHT));
  const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  style.textContent = GRAPH_EXPORT_STYLE;
  clone.prepend(style);
  return new XMLSerializer().serializeToString(clone);
}

function loadSvgImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(new Blob([source], { type: 'image/svg+xml' }));
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('SVG load failed'));
    };
    image.src = url;
  });
}

function downloadBlob(content: string, filename: string, type: string) {
  downloadExistingBlob(new Blob([content], { type }), filename);
}

function downloadExistingBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function safeFileName(expression: string) {
  return expression.replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 48) || 'ham-so';
}

const GRAPH_EXPORT_STYLE = `
.fa2-graph-bg{fill:#fff;stroke:#d1d5db}.fa2-graph-grid{stroke:#e5e7eb}.fa2-graph-axis{stroke:#64748b;stroke-width:1.5}
.fa2-graph-path{fill:none;stroke:#111827;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.fa2-graph-asymptote{stroke:#dc2626;stroke-width:1.5;stroke-dasharray:7 5}
.fa2-graph-interval-highlight{fill:rgba(14,116,144,.1);stroke:#0e7490}.fa2-graph-overlay{fill:none;stroke-width:2}.fa2-graph-derivative{stroke:#2563eb}.fa2-graph-second-derivative{stroke:#7c3aed;stroke-dasharray:5 4}.fa2-graph-tool-line{stroke:#ea580c;stroke-dasharray:8 4}
.fa2-graph-endpoint{stroke:#111827;stroke-width:2}.fa2-graph-endpoint.is-open{fill:#fff}.fa2-graph-endpoint.is-closed{fill:#111827}
.fa2-graph-point{fill:#334155;stroke:#fff;stroke-width:2}.fa2-graph-label,.fa2-graph-tick,.fa2-graph-trace text{fill:#334155;font-family:monospace;font-size:11px}.fa2-graph-trace line{stroke:#64748b;stroke-dasharray:3 3}.fa2-graph-trace circle{fill:#111827}
`;

class RendererErrorBoundary extends Component<{
  children: ReactNode;
  onError: (error: Error) => void;
}, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError(error);
  }

  render() {
    if (this.state.failed) return <div className="info-box">GeoGebra không thể hiển thị đồ thị này. Chọn SVG để tiếp tục.</div>;
    return this.props.children;
  }
}

function GraphRendererToolbar({
  active,
  status,
  onSelect,
  commands,
  onRetry,
}: {
  active: 'geogebra' | 'svg';
  status: GeoGebraStatus;
  onSelect: (mode: RendererMode) => void;
  commands: string[];
  onRetry: () => void;
}) {
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  async function copyCommands() {
    try {
      await navigator.clipboard.writeText(commands.join('\n'));
      setCopyStatus('Đã sao chép lệnh GeoGebra.');
    } catch {
      setCopyStatus('Không thể sao chép lệnh GeoGebra.');
    }
  }

  return (
    <div className="fa2-graph-toolbar" aria-label="Chọn renderer đồ thị">
      <span>Renderer: <strong>{active === 'geogebra' ? 'GeoGebra' : 'SVG'}</strong></span>
      <div className="fa2-graph-toolbar-actions">
        <button type="button" className="sp-btn-secondary" aria-pressed={active === 'geogebra'} onClick={() => onSelect('geogebra')}>GeoGebra</button>
        <button type="button" className="sp-btn-secondary" aria-pressed={active === 'svg'} onClick={() => onSelect('svg')}>SVG</button>
        <button type="button" className="sp-btn-secondary" onClick={() => void copyCommands()} disabled={!commands.length}>Sao chép lệnh</button>
        {status === 'error' && <button type="button" className="sp-btn-secondary" onClick={onRetry}>Thử lại GeoGebra</button>}
      </div>
      {copyStatus && <span className="sr-only" role="status">{copyStatus}</span>}
    </div>
  );
}

function legacySegment(points: Array<{ x: number; y: number }>): GraphSegmentV2 {
  const emptyBound = { exact: '', latex: '', approx: null };
  return {
    component_id: 'legacy',
    expression_exact: '',
    expression_latex: '',
    start: emptyBound,
    end: emptyBound,
    left_open: true,
    right_open: true,
    left_endpoint: { ...emptyBound, open: true, attained: false, y: null },
    right_endpoint: { ...emptyBound, open: true, attained: false, y: null },
    points,
    sample_count: points.length,
    verification: 'legacy',
  };
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

function createFallbackGraphScene(expression: string): MathScene {
  return {
    problem_text: `Khảo sát hàm số y = ${expression}`,
    grade: null,
    topic: 'function_graph',
    renderer: 'geogebra_2d',
    objects: [{ type: 'function_graph', name: 'f', expression }],
    relations: [],
    annotations: [],
    view: {
      dimension: '2d',
      show_axes: true,
      show_grid: true,
      show_coordinates: false,
    },
  };
}

const SVG_WIDTH = 720;
const SVG_HEIGHT = 300;

function projectFallbackPoint(point: { x: number; y: number }) {
  return {
    x: SVG_WIDTH / 2 + point.x * 42,
    y: SVG_HEIGHT / 2 - point.y * 42,
  };
}

function buildSvgGraph(segments: GraphSegmentV2[], result: AnalyzeResponse, fitDomain = false) {
  const width = SVG_WIDTH;
  const height = SVG_HEIGHT;
  const pad = 28;
  const finitePoints = segments
    .flatMap((segment) => segment.points)
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
    .sort((a, b) => a.x - b.x);
  if (finitePoints.length < 2) {
    return {
      paths: [],
      endpointMarkers: [],
      bounds: { left: -6, right: 6, bottom: -3, top: 3 },
      grid: [],
      xTicks: [],
      yTicks: [],
      project: (p: { x: number; y: number }) => ({ x: p.x, y: p.y }),
      xAxis: { x1: pad, y1: height / 2, x2: width - pad, y2: height / 2 },
      yAxis: { x1: width / 2, y1: pad, x2: width / 2, y2: height - pad },
    };
  }
  const featureXs = [
    ...result.critical_points.map((p) => Number(p.x)),
    ...result.inflection_points.map((p) => Number(p.x)),
    ...result.x_intercepts.map(Number),
  ].filter(Number.isFinite);
  const specialXs = [
    ...featureXs,
    0,
  ].filter(Number.isFinite);
  const quantileMinX = quantile(finitePoints.map((p) => p.x), 0.08);
  const quantileMaxX = quantile(finitePoints.map((p) => p.x), 0.92);
  const keyMinX = specialXs.length > 0 ? Math.min(...specialXs) : quantileMinX;
  const keyMaxX = specialXs.length > 0 ? Math.max(...specialXs) : quantileMaxX;
  const domainMinX = finitePoints[0].x;
  const domainMaxX = finitePoints[finitePoints.length - 1].x;
  let baseMinX = fitDomain ? domainMinX : featureXs.length > 0 ? keyMinX : Math.max(quantileMinX, -6);
  let baseMaxX = fitDomain ? domainMaxX : featureXs.length > 0 ? keyMaxX : Math.min(quantileMaxX, 6);
  if (baseMinX >= baseMaxX) {
    baseMinX = quantileMinX;
    baseMaxX = quantileMaxX;
  }
  const span = Math.max(baseMaxX - baseMinX, 4);
  const xMargin = Math.max(0.9, span * 0.18);
  const x0 = baseMinX - xMargin;
  const x1 = baseMaxX + xMargin;
  const focused = finitePoints.filter((p) => p.x >= x0 && p.x <= x1);
  const usable = focused.length >= 16 ? focused : finitePoints;
  const specialYs = [
    ...result.critical_points.map((p) => Number(p.y)),
    ...result.inflection_points.map((p) => Number(p.y)),
    Number(result.y_intercept),
    0,
  ].filter(Number.isFinite);
  const usableYs = usable.map((p) => p.y);
  const lo = quantile(usableYs, 0.08);
  const hi = quantile(usableYs, 0.92);
  const minY = Math.min(lo, ...specialYs, -1);
  const maxY = Math.max(hi, ...specialYs, 1);
  const dy = Math.max(maxY - minY, 1);
  let y0 = minY - dy * 0.16;
  let y1 = maxY + dy * 0.16;
  let left = x0;
  let right = x1;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const unit = Math.min(plotW / (right - left), plotH / (y1 - y0));
  const targetXRange = plotW / unit;
  const targetYRange = plotH / unit;
  const cx = (left + right) / 2;
  const cy = (y0 + y1) / 2;
  left = cx - targetXRange / 2;
  right = cx + targetXRange / 2;
  y0 = cy - targetYRange / 2;
  y1 = cy + targetYRange / 2;
  const project = (p: { x: number; y: number }) => ({ x: pad + ((p.x - left) / (right - left)) * plotW, y: height - pad - ((p.y - y0) / (y1 - y0)) * plotH });
  const useFocusedWindow = !fitDomain && focused.length >= 16;
  const drawableSegments = segments.map((segment) => segment.points
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    .filter((point) => !useFocusedWindow || (point.x >= x0 && point.x <= x1))
    .sort((a, b) => a.x - b.x));
  const paths = drawableSegments
    .filter((segment) => segment.length > 1)
    .map((segment) => segment.map((p, i) => `${i === 0 ? 'M' : 'L'} ${project(p).x.toFixed(2)} ${project(p).y.toFixed(2)}`).join(' '));
  const endpointMarkers = segments.flatMap((segment) => [
    { key: `${segment.component_id}-left`, endpoint: segment.left_endpoint },
    { key: `${segment.component_id}-right`, endpoint: segment.right_endpoint },
  ]).flatMap(({ key, endpoint }) => {
    const x = endpoint.approx;
    const y = endpoint.y;
    if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return [];
    if (useFocusedWindow && (x < x0 || x > x1)) return [];
    return [{ key, open: endpoint.open, ...project({ x, y }) }];
  });
  const xTicks = createTicks(left, right, 8).map((value) => ({ value, x: project({ x: value, y: y0 }).x, label: shortNumber(value) }));
  const yTicks = createTicks(y0, y1, 6).map((value) => ({ value, y: project({ x: left, y: value }).y, label: shortNumber(value) }));
  const grid = [
    ...xTicks.map((tick) => ({ x1: tick.x, y1: pad, x2: tick.x, y2: height - pad })),
    ...yTicks.map((tick) => ({ x1: pad, y1: tick.y, x2: width - pad, y2: tick.y })),
  ];
  const axis0 = project({ x: 0, y: 0 });
  const axisX = Math.min(width - pad, Math.max(pad, axis0.x));
  const axisY = Math.min(height - pad, Math.max(pad, axis0.y));
  return { paths, endpointMarkers, bounds: { left, right, bottom: y0, top: y1 }, grid, xTicks, yTicks, project, xAxis: { x1: pad, y1: axisY, x2: width - pad, y2: axisY }, yAxis: { x1: axisX, y1: pad, x2: axisX, y2: height - pad } };
}

function createTicks(min: number, max: number, targetCount: number) {
  const range = Math.max(max - min, 1e-8);
  const rough = range / Math.max(targetCount, 2);
  const step = niceStep(rough);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) ticks.push(roundTick(v));
  if (ticks.length < 2) return [roundTick(min), roundTick(max)];
  return ticks;
}

function niceStep(raw: number) {
  const exponent = Math.floor(Math.log10(raw));
  const fraction = raw / 10 ** exponent;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return niceFraction * 10 ** exponent;
}

function roundTick(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function shortNumber(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(1).replace(/\.0$/, '');
  if (abs >= 1) return value.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
  return value.toFixed(3).replace(/\.?0+$/, '');
}

function quantile(values: number[], q: number) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * q;
  const low = Math.floor(index);
  const high = Math.ceil(index);
  if (low === high) return sorted[low];
  const ratio = index - low;
  return sorted[low] * (1 - ratio) + sorted[high] * ratio;
}

function plotSpecialPoints(
  result: AnalyzeResponse,
  project: (point: { x: number; y: number }) => { x: number; y: number },
  width: number,
  height: number,
  pad: number,
) {
  const points = [
    ...result.critical_points.map((cp, i) => ({ key: `cp-${i}`, kind: cp.kind, label: cp.kind === 'max' ? 'CĐ' : cp.kind === 'min' ? 'CT' : 'T', raw: { x: Number(cp.x), y: Number(cp.y) }, coordsText: `(${cp.x_exact || cp.x}; ${cp.y})` })),
    ...result.inflection_points.map((pt, i) => ({ key: `ip-${i}`, kind: 'inflection', label: 'U', raw: { x: Number(pt.x), y: Number(pt.y) }, coordsText: `(${pt.x_exact || pt.x}; ${pt.y})` })),
    ...(result.y_intercept !== null ? [{ key: 'oy', kind: 'axis-y', label: 'Oy', raw: { x: 0, y: Number(result.y_intercept) }, coordsText: `(0; ${result.y_intercept})` }] : []),
    ...result.x_intercepts.map((xv, i) => ({ key: `ox-${i}`, kind: 'axis-x', label: 'Ox', raw: { x: Number(xv), y: 0 }, coordsText: `(${xv}; 0)` })),
  ].filter((p) => Number.isFinite(p.raw.x) && Number.isFinite(p.raw.y)).map((p) => ({ ...p, ...project(p.raw) }));
  const minSepPx = 20;
  const uniqueScreen: typeof points = [];
  for (const p of points) {
    if (uniqueScreen.every((k) => Math.hypot(k.x - p.x, k.y - p.y) >= minSepPx)) uniqueScreen.push(p);
  }
  const occupied: Array<{ x: number; y: number }> = [];
  const candidates: Array<{ dx: number; dy: number; anchor: 'start' | 'middle' | 'end' }> = [
    { dx: 12, dy: -10, anchor: 'start' },
    { dx: 12, dy: 16, anchor: 'start' },
    { dx: -12, dy: -10, anchor: 'end' },
    { dx: -12, dy: 16, anchor: 'end' },
    { dx: 0, dy: -14, anchor: 'middle' },
    { dx: 0, dy: 20, anchor: 'middle' },
  ];
  return uniqueScreen.map((point) => {
    const selected = candidates.find((option) => {
      const x = point.x + option.dx;
      const y = point.y + option.dy;
      const inBounds = x >= pad + 6 && x <= width - pad - 6 && y >= pad + 8 && y <= height - pad - 6;
      if (!inBounds) return false;
      return occupied.every((placed) => Math.abs(placed.x - x) > 30 || Math.abs(placed.y - y) > 15);
    }) ?? { dx: 12, dy: -10, anchor: 'start' as const };
    const labelX = point.x + selected.dx;
    const labelY = point.y + selected.dy;
    occupied.push({ x: labelX, y: labelY });
    const popoverWidth = Math.min(Math.max(point.coordsText.length * 8 + 20, 92), 180);
    const popoverX = Math.min(Math.max(point.x + 10, pad), width - popoverWidth - pad);
    const popoverY = Math.min(Math.max(point.y - 56, pad), height - 52 - pad);
    return { ...point, labelX, labelY, anchor: selected.anchor, popoverX, popoverY, popoverWidth };
  });
}


