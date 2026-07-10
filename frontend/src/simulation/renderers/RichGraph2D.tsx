import { formatNumber } from '../../utils/calculusNumerics';
import type { SamplePoint } from '../../utils/calculusNumerics';
import { KatexSpan } from '../../components/KatexSpan';

export type GraphCurve = {
  points: SamplePoint[];
  className?: string;
  label?: string;
  dashed?: boolean;
};

export type GraphSegment = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  className?: string;
};

export type GraphMarker = {
  x: number;
  y: number;
  label?: string;
  className?: string;
};

export type GraphVLine = { x: number; className?: string; label?: string };
export type GraphHLine = { y: number; className?: string; label?: string };

export type GraphBand = {
  from: number;
  to: number;
  className?: string;
};

type Props = {
  curves: GraphCurve[];
  segments?: GraphSegment[];
  markers?: GraphMarker[];
  vLines?: GraphVLine[];
  hLines?: GraphHLine[];
  bands?: GraphBand[];
  title?: string;
  width?: number;
  height?: number;
  yPadFactor?: number;
};

const DEFAULT_W = 760;
const DEFAULT_H = 400;
const PAD = 44;

export function RichGraph2D({
  curves,
  segments = [],
  markers = [],
  vLines = [],
  hLines = [],
  bands = [],
  title,
  width = DEFAULT_W,
  height = DEFAULT_H,
  yPadFactor = 0.14,
}: Props) {
  const allPoints = curves.flatMap((c) => c.points.filter((p) => p.valid));
  const extraYs = [
    ...markers.map((m) => m.y),
    ...segments.flatMap((s) => [s.y1, s.y2]),
    ...hLines.map((h) => h.y),
    0,
  ].filter(Number.isFinite);
  const xs = allPoints.map((p) => p.x);
  const ys = [...allPoints.map((p) => p.y), ...extraYs];
  const minX = xs.length ? Math.min(...xs) : -1;
  const maxX = xs.length ? Math.max(...xs) : 1;
  let minY = ys.length ? Math.min(...ys) : -1;
  let maxY = ys.length ? Math.max(...ys) : 1;
  if (minY === maxY) {
    minY -= 1;
    maxY += 1;
  }
  const yPad = Math.max((maxY - minY) * yPadFactor, 0.4);
  minY -= yPad;
  maxY += yPad;
  const xSpan = Math.max(maxX - minX, 1e-8);
  const ySpan = Math.max(maxY - minY, 1e-8);

  const project = (x: number, y: number) => ({
    x: PAD + ((x - minX) / xSpan) * (width - PAD * 2),
    y: height - PAD - ((y - minY) / ySpan) * (height - PAD * 2),
  });

  const xAxisY = project(0, 0).y;
  const yAxisX = project(0, 0).x;

  return (
    <div className="csim-graph-card">
      <div className="csim-graph-head">
        <strong>{title ?? 'Đồ thị'}</strong>
        <span className="sim-rich-legend">
          {curves.filter((c) => c.label).map((c) => (
            <span key={c.label} className="sim-rich-legend-item">
              <i className={`sim-rich-swatch ${c.className ?? 'csim-path-f'}${c.dashed ? ' is-dashed' : ''}`} />
              <GraphLabel label={c.label!} />
            </span>
          ))}
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="csim-svg" role="img" aria-label={title ?? 'Đồ thị'}>
        <rect x="0" y="0" width={width} height={height} rx="18" className="csim-svg-bg" />
        {ticks(minX, maxX, 8).map((tick) => {
          const p = project(tick, 0);
          return (
            <g key={`x-${tick}`}>
              <line x1={p.x} x2={p.x} y1={PAD} y2={height - PAD} className="csim-grid" />
              <text x={p.x} y={height - 12} className="csim-tick">{shortTick(tick)}</text>
            </g>
          );
        })}
        {ticks(minY, maxY, 6).map((tick) => {
          const p = project(0, tick);
          return (
            <g key={`y-${tick}`}>
              <line x1={PAD} x2={width - PAD} y1={p.y} y2={p.y} className="csim-grid" />
              <text x="8" y={p.y + 4} className="csim-tick">{shortTick(tick)}</text>
            </g>
          );
        })}
        {bands.map((band, i) => {
          const left = project(band.from, 0).x;
          const right = project(band.to, 0).x;
          return (
            <rect
              key={`band-${i}`}
              x={Math.min(left, right)}
              y={PAD}
              width={Math.max(1, Math.abs(right - left))}
              height={height - PAD * 2}
              className={band.className ?? 'sim-band-default'}
            />
          );
        })}
        <line x1={PAD} x2={width - PAD} y1={clamp(xAxisY, PAD, height - PAD)} y2={clamp(xAxisY, PAD, height - PAD)} className="csim-axis" />
        <line x1={clamp(yAxisX, PAD, width - PAD)} x2={clamp(yAxisX, PAD, width - PAD)} y1={PAD} y2={height - PAD} className="csim-axis" />
        {vLines.map((line, i) => {
          const x = project(line.x, 0).x;
          return (
            <g key={`vl-${i}`}>
              <line x1={x} x2={x} y1={PAD} y2={height - PAD} className={line.className ?? 'sim-vline'} />
              {line.label && <text x={x + 4} y={PAD + 14} className="csim-tick">{line.label}</text>}
            </g>
          );
        })}
        {hLines.map((line, i) => {
          const y = project(0, line.y).y;
          return (
            <g key={`hl-${i}`}>
              <line x1={PAD} x2={width - PAD} y1={y} y2={y} className={line.className ?? 'sim-hline'} />
              {line.label && <text x={PAD + 4} y={y - 4} className="csim-tick">{line.label}</text>}
            </g>
          );
        })}
        {curves.map((curve, i) => (
          <path
            key={`curve-${i}`}
            d={buildPath(curve.points, project)}
            className={`${curve.className ?? 'csim-path-f'}${curve.dashed ? ' sim-path-dashed' : ''}`}
            fill="none"
          />
        ))}
        {segments.map((seg, i) => {
          const a = project(seg.x1, seg.y1);
          const b = project(seg.x2, seg.y2);
          return <line key={`seg-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={seg.className ?? 'sim-secant'} />;
        })}
        {markers.map((m, i) => {
          const p = project(m.x, m.y);
          return (
            <g key={`mk-${i}`} className={m.className ?? 'sim-marker'}>
              <circle cx={p.x} cy={p.y} r="5.5" />
              {m.label && <text x={p.x + 8} y={p.y - 8}>{m.label}</text>}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function GraphLabel({ label }: { label: string }) {
  if (label.includes('\\') || label.includes('^') || label.includes('_')) {
    return <KatexSpan tex={label} />;
  }
  return <>{label}</>;
}

function buildPath(points: SamplePoint[], project: (x: number, y: number) => { x: number; y: number }) {
  let d = '';
  let penUp = true;
  for (const point of points) {
    if (!point.valid || !Number.isFinite(point.y)) {
      penUp = true;
      continue;
    }
    const p = project(point.x, point.y);
    d += penUp ? `M ${p.x} ${p.y}` : ` L ${p.x} ${p.y}`;
    penUp = false;
  }
  return d || 'M 0 0';
}

function ticks(min: number, max: number, count: number) {
  const span = max - min;
  const step = niceStep(span / Math.max(1, count - 1));
  const start = Math.ceil(min / step) * step;
  const values: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) values.push(Number(v.toFixed(8)));
  return values;
}

function niceStep(raw: number) {
  const pow = 10 ** Math.floor(Math.log10(Math.max(raw, 1e-8)));
  const n = raw / pow;
  if (n < 1.5) return pow;
  if (n < 3.5) return 2 * pow;
  if (n < 7.5) return 5 * pow;
  return 10 * pow;
}

function shortTick(value: number) {
  return formatNumber(value, Math.abs(value) >= 10 ? 1 : 2);
}

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}
