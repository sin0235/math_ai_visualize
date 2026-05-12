import type { RectSample, SamplePoint } from '../../utils/calculusNumerics';
import { formatNumber, sampleRange } from '../../utils/calculusNumerics';
import { KatexSpan } from '../KatexSpan';

export interface CalculusGraph2DProps {
  primary: SamplePoint[];
  secondary?: SamplePoint[];
  fillBetween?: boolean;
  fillProgress?: number;
  rectangles?: RectSample[];
  visibleRectangles?: number;
  intersections?: Array<{ x: number; y: number }>;
  markerX?: number;
  title?: string;
  primaryLabel?: string;
  secondaryLabel?: string;
}

const WIDTH = 760;
const HEIGHT = 380;
const PAD = 42;

export function CalculusGraph2D({ primary, secondary = [], fillBetween = false, fillProgress = 1, rectangles = [], visibleRectangles = rectangles.length, intersections = [], markerX, title, primaryLabel = 'f(x)', secondaryLabel = 'g(x)' }: CalculusGraph2DProps) {
  const range = sampleRange([...primary, ...secondary], rectangles.flatMap((r) => [r.top, r.bottom]));
  const project = (x: number, y: number) => ({
    x: PAD + ((x - range.minX) / Math.max(range.maxX - range.minX, 1e-8)) * (WIDTH - PAD * 2),
    y: HEIGHT - PAD - ((y - range.minY) / Math.max(range.maxY - range.minY, 1e-8)) * (HEIGHT - PAD * 2),
  });
  const xAxis = project(0, 0).y;
  const yAxis = project(0, 0).x;
  const shownRects = rectangles.filter((rect) => Number.isFinite(rect.top) && Number.isFinite(rect.bottom) && Number.isFinite(rect.area)).slice(0, Math.max(0, Math.min(rectangles.length, visibleRectangles)));
  const fillPointCount = Math.max(0, Math.min(primary.length, secondary.length, Math.ceil(Math.min(primary.length, secondary.length) * clampUnit(fillProgress))));
  const fillPrimary = primary.slice(0, fillPointCount);
  const fillSecondary = secondary.slice(0, fillPointCount);
  const fillPath = fillBetween && fillPointCount > 1 && !curvesOverlap(primary, secondary) ? buildAreaPaths(fillPrimary, fillSecondary, project) : [];
  const showSecondaryLegend = secondary.length > 1 && secondaryLabel.trim().length > 0;

  return (
    <div className="csim-graph-card">
      <div className="csim-graph-head">
        <strong>{title ?? 'Đồ thị'}</strong>
        <span><i className="csim-line f" /> <GraphLegendLabel label={primaryLabel} />{showSecondaryLegend && <><i className="csim-line g" /> <GraphLegendLabel label={secondaryLabel} /></>}</span>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="csim-svg" role="img" aria-label={title ?? 'Đồ thị mô phỏng'}>
        <rect x="0" y="0" width={WIDTH} height={HEIGHT} rx="18" className="csim-svg-bg" />
        {ticks(range.minX, range.maxX, 8).map((tick) => {
          const p = project(tick, 0);
          return <g key={`x-${tick}`}><line x1={p.x} x2={p.x} y1={PAD} y2={HEIGHT - PAD} className="csim-grid" /><text x={p.x} y={HEIGHT - 12} className="csim-tick">{shortTick(tick)}</text></g>;
        })}
        {ticks(range.minY, range.maxY, 6).map((tick) => {
          const p = project(0, tick);
          return <g key={`y-${tick}`}><line x1={PAD} x2={WIDTH - PAD} y1={p.y} y2={p.y} className="csim-grid" /><text x="8" y={p.y + 4} className="csim-tick">{shortTick(tick)}</text></g>;
        })}
        <line x1={PAD} x2={WIDTH - PAD} y1={clampSvg(xAxis, PAD, HEIGHT - PAD)} y2={clampSvg(xAxis, PAD, HEIGHT - PAD)} className="csim-axis" />
        <line x1={clampSvg(yAxis, PAD, WIDTH - PAD)} x2={clampSvg(yAxis, PAD, WIDTH - PAD)} y1={PAD} y2={HEIGHT - PAD} className="csim-axis" />
        {fillPath.map((path, index) => <path key={`area-${index}`} d={path} className="csim-area-fill" />)}
        {shownRects.map((rect, index) => {
          const left = project(rect.x, rect.bottom);
          const right = project(rect.x + rect.width, rect.top);
          const yTop = Math.min(left.y, right.y);
          const yBottom = Math.max(left.y, right.y);
          return <rect key={`rect-${index}`} x={left.x} y={yTop} width={Math.max(1, right.x - left.x)} height={Math.max(1, yBottom - yTop)} className="csim-riemann-rect" />;
        })}
        <path d={buildLinePath(primary, project)} className="csim-path-f" />
        {secondary.length > 1 && <path d={buildLinePath(secondary, project)} className="csim-path-g" />}
        {markerX !== undefined && Number.isFinite(markerX) && (
          <line x1={project(markerX, 0).x} x2={project(markerX, 0).x} y1={PAD} y2={HEIGHT - PAD} className="csim-marker-line" />
        )}
        {intersections.map((point, index) => {
          const p = project(point.x, point.y);
          return (
            <g key={`intersection-${index}`} className="csim-intersection">
              <circle cx={p.x} cy={p.y} r="6" />
              <text x={p.x + 10} y={p.y - 10}>I{index + 1}({formatNumber(point.x, 2)}; {formatNumber(point.y, 2)})</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function GraphLegendLabel({ label }: { label: string }) {
  if (!label.trim()) return null;
  if (label === 'Ox') return <KatexSpan tex="Ox" />;
  return <KatexSpan tex={label} />;
}

function curvesOverlap(primary: SamplePoint[], secondary: SamplePoint[]) {
  const pairs = primary.map((point, index) => [point, secondary[index]] as const).filter(([a, b]) => a.valid && b?.valid);
  return pairs.length > 1 && pairs.every(([a, b]) => Math.abs(a.y - b.y) < 1e-7);
}

function buildLinePath(points: SamplePoint[], project: (x: number, y: number) => { x: number; y: number }) {
  const parts: string[] = [];
  let open = false;
  points.forEach((point) => {
    if (!point.valid) {
      open = false;
      return;
    }
    const p = project(point.x, point.y);
    parts.push(`${open ? 'L' : 'M'} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
    open = true;
  });
  return parts.join(' ');
}

function buildAreaPaths(primary: SamplePoint[], secondary: SamplePoint[], project: (x: number, y: number) => { x: number; y: number }) {
  const paths: string[] = [];
  let segment: Array<{ top: SamplePoint; bottom: SamplePoint }> = [];
  const flush = () => {
    if (segment.length < 2) {
      segment = [];
      return;
    }
    const first = project(segment[0].top.x, segment[0].top.y);
    const parts = [`M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`];
    segment.slice(1).forEach(({ top }) => {
      const p = project(top.x, top.y);
      parts.push(`L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
    });
    segment.slice().reverse().forEach(({ bottom }) => {
      const p = project(bottom.x, bottom.y);
      parts.push(`L ${p.x.toFixed(2)} ${p.y.toFixed(2)}`);
    });
    parts.push('Z');
    paths.push(parts.join(' '));
    segment = [];
  };
  primary.forEach((top, index) => {
    const bottom = secondary[index];
    if (top.valid && bottom?.valid && Math.abs(top.x - bottom.x) < 1e-8) segment.push({ top, bottom });
    else flush();
  });
  flush();
  return paths;
}

function ticks(min: number, max: number, count: number) {
  const range = Math.max(max - min, 1e-8);
  const raw = range / count;
  const exp = Math.floor(Math.log10(raw));
  const base = raw / 10 ** exp;
  const step = (base <= 1 ? 1 : base <= 2 ? 2 : base <= 5 ? 5 : 10) * 10 ** exp;
  const start = Math.ceil(min / step) * step;
  const values: number[] = [];
  for (let value = start; value <= max + step * 0.5; value += step) values.push(Math.round(value * 1e6) / 1e6);
  return values;
}

function shortTick(value: number) {
  return Math.abs(value) >= 10 ? value.toFixed(1).replace(/\.0$/, '') : value.toFixed(2).replace(/\.?0+$/, '');
}

function clampSvg(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function clampUnit(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}
