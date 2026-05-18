import { useId, useMemo, useRef, useState } from 'react';
import { GeoGebraView } from '../GeoGebraView';
import type { AnalyzeResponse } from '../../api/client';
import type { MathScene } from '../../types/scene';

export function FunctionGraph({ result }: { result: AnalyzeResponse }) {
  const data = result.graph_points || [];
  const graph = useMemo(() => buildSvgGraph(data, result), [data, result]);
  const svgId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);
  const [view, setView] = useState({ scale: 1, tx: 0, ty: 0 });
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const specialPoints = data.length >= 2 ? plotSpecialPoints(result, graph.project, SVG_WIDTH, SVG_HEIGHT, 28) : plotSpecialPoints(result, projectFallbackPoint, SVG_WIDTH, SVG_HEIGHT, 28);
  const visibleSpecialPoints = specialPoints.filter((point) => point.x >= 0 && point.x <= SVG_WIDTH && point.y >= 0 && point.y <= SVG_HEIGHT);
  const selectedPoint = visibleSpecialPoints.find((point) => point.key === selectedPointKey) ?? null;
  if (result.geogebra_commands.length > 0) {
    const scene = result.graph_scene ?? createFallbackGraphScene(result.expression);
    return (
      <div className="fa2-graph-card fa2-geogebra-graph-card">
        <GeoGebraView
          commands={result.geogebra_commands}
          renderer="geogebra_2d"
          scene={scene}
          view={scene.view}
          embedded
        />
      </div>
    );
  }
  if (data.length < 2) return <div className="info-box">Chưa đủ dữ liệu để vẽ đồ thị.</div>;

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
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.x;
    const deltaY = event.clientY - drag.y;
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
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

  return (
    <div className="fa2-graph-card">
      <div className="fa2-graph-toolbar">
        <span>Kéo để di chuyển | Con lăn để zoom</span>
        <div className="fa2-graph-toolbar-actions">
          <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1.14)} aria-label="Phóng to">+</button>
          <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1 / 1.14)} aria-label="Thu nhỏ">-</button>
          <button type="button" className="sp-btn-secondary" onClick={() => setView({ scale: 1, tx: 0, ty: 0 })}>Reset</button>
        </div>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        role="img"
        aria-label={`Đồ thị y = ${result.expression}`}
        className="fa2-svg-graph"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" />
          </clipPath>
        </defs>
        <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" className="fa2-graph-bg" />
        <g clipPath={`url(#${clipId})`} transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
          {graph.grid.map((line, i) => <line key={`grid-${i}`} {...line} className="fa2-graph-grid" />)}
          <line x1={graph.xAxis.x1} y1={graph.xAxis.y1} x2={graph.xAxis.x2} y2={graph.xAxis.y2} className="fa2-graph-axis" />
          <line x1={graph.yAxis.x1} y1={graph.yAxis.y1} x2={graph.yAxis.x2} y2={graph.yAxis.y2} className="fa2-graph-axis" />
          {graph.paths.map((path, i) => <path key={`path-${i}`} d={path} className="fa2-graph-path" />)}
          {visibleSpecialPoints.map((point) => (
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
          {selectedPoint && (
            <g className="fa2-graph-point-popover" transform={`translate(${selectedPoint.popoverX} ${selectedPoint.popoverY})`}>
              <rect x="0" y="0" width={selectedPoint.popoverWidth} height="46" rx="10" />
              <text x="10" y="18" className="fa2-graph-popover-label">{selectedPoint.label}</text>
              <text x="10" y="36" className="fa2-graph-popover-coords">{selectedPoint.coordsText}</text>
            </g>
          )}
        </g>
        {graph.xTicks.map((tick, idx) => (
          <text key={`xt-${idx}`} x={tick.x} y={SVG_HEIGHT - 6} className="fa2-graph-tick">{tick.label}</text>
        ))}
        {graph.yTicks.map((tick, idx) => (
          <text key={`yt-${idx}`} x={6} y={tick.y + 4} className="fa2-graph-tick">{tick.label}</text>
        ))}
      </svg>
    </div>
  );
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

function buildSvgGraph(points: Array<{ x: number; y: number }>, result: AnalyzeResponse) {
  const width = SVG_WIDTH;
  const height = SVG_HEIGHT;
  const pad = 28;
  const finitePoints = points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).sort((a, b) => a.x - b.x);
  if (finitePoints.length < 2) {
    return {
      paths: [],
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
  let baseMinX = featureXs.length > 0 ? keyMinX : Math.max(quantileMinX, -6);
  let baseMaxX = featureXs.length > 0 ? keyMaxX : Math.min(quantileMaxX, 6);
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
  const yJump = Math.max(2.2, quantile(usableYs.map((v) => Math.abs(v)), 0.9));
  const segments: Array<Array<{ x: number; y: number }>> = [];
  for (const point of usable) {
    const lastSegment = segments[segments.length - 1];
    const lastPoint = lastSegment?.[lastSegment.length - 1];
    if (!lastSegment || !lastPoint || Math.abs(point.x - lastPoint.x) > 0.2 || Math.abs(point.y - lastPoint.y) > yJump) segments.push([point]);
    else lastSegment.push(point);
  }
  const paths = segments.filter((segment) => segment.length > 1).map((segment) => segment.map((p, i) => `${i === 0 ? 'M' : 'L'} ${project(p).x.toFixed(2)} ${project(p).y.toFixed(2)}`).join(' '));
  const xTicks = createTicks(left, right, 8).map((value) => ({ value, x: project({ x: value, y: y0 }).x, label: shortNumber(value) }));
  const yTicks = createTicks(y0, y1, 6).map((value) => ({ value, y: project({ x: left, y: value }).y, label: shortNumber(value) }));
  const grid = [
    ...xTicks.map((tick) => ({ x1: tick.x, y1: pad, x2: tick.x, y2: height - pad })),
    ...yTicks.map((tick) => ({ x1: pad, y1: tick.y, x2: width - pad, y2: tick.y })),
  ];
  const axis0 = project({ x: 0, y: 0 });
  const axisX = Math.min(width - pad, Math.max(pad, axis0.x));
  const axisY = Math.min(height - pad, Math.max(pad, axis0.y));
  return { paths, grid, xTicks, yTicks, project, xAxis: { x1: pad, y1: axisY, x2: width - pad, y2: axisY }, yAxis: { x1: axisX, y1: pad, x2: axisX, y2: height - pad } };
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


