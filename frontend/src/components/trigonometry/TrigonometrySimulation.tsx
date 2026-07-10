/* @refresh reset */
import type { ReactNode } from 'react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { KatexSpan } from '../KatexSpan';
import { degToRad, formatAngleLabel, formatTrigNumber, normalizeAngleRad, radToDeg, safeCot, safeTan, sampleTrigWave, SPECIAL_ANGLES, type WavePoint } from '../../utils/trigonometryNumerics';
import { formatVerifyTone, verifyTanCotRelation, verifyUnitCircleIdentity } from '../../simulation/math/verify';

interface Props {
  playing: boolean;
}

const TAU = Math.PI * 2;
const GRAPH_MIN = 0;
const GRAPH_MAX = TAU;
const TRIG_SVG_SIZE = 560;
const TRIG_WAVE_VIEW_W = 680;
const TRIG_UNIT_RADIUS_U = 190;
const TRIG_PLOT_PIXEL_SCALE = 0.76;
const WAVE_TICK_LABELS = [String.raw`0`, String.raw`\frac{\pi}{2}`, String.raw`\pi`, String.raw`\frac{3\pi}{2}`, String.raw`2\pi`];

type VisibleKey = 'sin' | 'cos' | 'tan' | 'cot';

export function TrigonometrySimulation({ playing }: Props) {
  const [manualAngle, setManualAngle] = useState(Math.PI / 6);
  const [animatedAngle, setAnimatedAngle] = useState(Math.PI / 6);
  const [angularSpeed, setAngularSpeed] = useState(0.7);
  const [phaseDeg, setPhaseDeg] = useState(0);
  const [amplitude, setAmplitude] = useState(1);
  const [frequency, setFrequency] = useState(1);
  const [visible, setVisible] = useState<Record<VisibleKey, boolean>>({ sin: true, cos: true, tan: false, cot: false });
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);
  const baseAngleRad = playing ? animatedAngle : manualAngle;
  const phaseRad = degToRad(phaseDeg);
  const phaseAngleRad = normalizeAngleRad(baseAngleRad + phaseRad);
  const baseAngleDeg = radToDeg(baseAngleRad);
  const phaseAngleDeg = radToDeg(phaseAngleRad);
  const sin = Math.sin(phaseAngleRad);
  const cos = Math.cos(phaseAngleRad);
  const tan = safeTan(phaseAngleRad);
  const cot = safeCot(phaseAngleRad);
  const identityCheck = useMemo(() => verifyUnitCircleIdentity(phaseAngleRad), [phaseAngleRad]);
  const tanCotCheck = useMemo(() => verifyTanCotRelation(phaseAngleRad), [phaseAngleRad]);
  const waves = useMemo(() => ({
    sin: sampleShiftedTrigWave('sin', phaseRad, amplitude, frequency),
    cos: sampleShiftedTrigWave('cos', phaseRad, amplitude, frequency),
    tan: sampleShiftedTrigWave('tan', phaseRad, amplitude, frequency),
    cot: sampleShiftedTrigWave('cot', phaseRad, amplitude, frequency),
  }), [phaseRad, amplitude, frequency]);

  useEffect(() => {
    if (!playing) {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTimeRef.current = null;
      setAnimatedAngle(manualAngle);
      return;
    }
    const tick = (time: number) => {
      const last = lastTimeRef.current ?? time;
      const delta = (time - last) / 1000;
      lastTimeRef.current = time;
      setAnimatedAngle((current) => normalizeAngleRad(current + delta * angularSpeed));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [angularSpeed, manualAngle, playing]);

  function setAngleRad(next: number) {
    const normalized = normalizeAngleRad(next);
    setManualAngle(normalized);
    setAnimatedAngle(normalized);
  }

  function setAngleDeg(next: number) {
    setAngleRad(degToRad(next));
  }

  function toggle(key: VisibleKey) {
    setVisible((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <section className="trig-core" data-trig-ui="3">
      <aside className="trig-control-panel">
        <label className="trig-angle-control">
          <span>Góc gốc <KatexSpan tex={String.raw`\theta`} /></span>
          <strong>{Math.round(baseAngleDeg)}° · {formatAngleLabel(baseAngleRad, false)}</strong>
          <input type="range" min="0" max="360" step="1" value={Math.round(baseAngleDeg)} onChange={(event) => setAngleDeg(Number(event.target.value))} />
        </label>

        <label className="trig-angle-control trig-param-control">
          <span>Tốc độ góc <KatexSpan tex={String.raw`\omega`} /></span>
          <strong>{angularSpeed.toFixed(2)} rad/s</strong>
          <input type="range" min="0.1" max="2.5" step="0.05" value={angularSpeed} onChange={(event) => setAngularSpeed(Number(event.target.value))} />
        </label>

        <label className="trig-angle-control trig-param-control">
          <span>Pha <KatexSpan tex={String.raw`\varphi`} /></span>
          <strong>{phaseDeg > 0 ? 'Sớm pha' : phaseDeg < 0 ? 'Trễ pha' : 'Cùng pha'} · {phaseDeg}°</strong>
          <input type="range" min="-180" max="180" step="5" value={phaseDeg} onChange={(event) => setPhaseDeg(Number(event.target.value))} />
        </label>

        <label className="trig-angle-control trig-param-control">
          <span>Biên độ sóng <KatexSpan tex="A" /></span>
          <strong>{amplitude.toFixed(2)} · đồ thị <KatexSpan tex={String.raw`A\sin(B\theta+\varphi)`} /></strong>
          <input type="range" min="0.25" max="2.5" step="0.05" value={amplitude} onChange={(event) => setAmplitude(Number(event.target.value))} />
        </label>

        <label className="trig-angle-control trig-param-control">
          <span>Tần số góc <KatexSpan tex="B" /></span>
          <strong>{frequency.toFixed(2)} · chu kỳ đồ thị ~ <KatexSpan tex={String.raw`2\pi/|B|`} /></strong>
          <input type="range" min="0.5" max="3" step="0.1" value={frequency} onChange={(event) => setFrequency(Number(event.target.value))} />
        </label>

        <div className="trig-phase-presets" aria-label="Mẫu pha">
          {[-90, -45, 0, 45, 90].map((degree) => <button key={degree} type="button" className={phaseDeg === degree ? 'active' : ''} onClick={() => setPhaseDeg(degree)}>{degree > 0 ? `+${degree}°` : `${degree}°`}</button>)}
        </div>

        <div className="trig-phase-readout">
          <span>Vector gốc <KatexSpan tex={String.raw`P(\theta)`} />: {Math.round(baseAngleDeg)}°</span>
          <strong>Vector pha <KatexSpan tex={String.raw`Q(\theta+\varphi)`} />: {Math.round(phaseAngleDeg)}°</strong>
        </div>

        <div className="trig-values-core">
          <ValueTile label={<KatexSpan tex={String.raw`\sin(\theta+\varphi)`} className="trig-value-tile-katex" />} value={formatTrigNumber(sin)} tone="sin" />
          <ValueTile label={<KatexSpan tex={String.raw`\cos(\theta+\varphi)`} className="trig-value-tile-katex" />} value={formatTrigNumber(cos)} tone="cos" />
          <ValueTile label={<KatexSpan tex={String.raw`\tan(\theta+\varphi)`} className="trig-value-tile-katex" />} value={tan.undefined ? 'Không xác định' : formatTrigNumber(tan.value)} tone="tan" />
          <ValueTile label={<KatexSpan tex={String.raw`\cot(\theta+\varphi)`} className="trig-value-tile-katex" />} value={cot.undefined ? 'Không xác định' : formatTrigNumber(cot.value)} tone="cot" />
        </div>

        <div className={`sim-verify-banner sim-verify-${identityCheck.severity}`} role="status">
          <strong>{formatVerifyTone(identityCheck.severity)}</strong>
          <span>{identityCheck.message}</span>
        </div>
        <div className={`sim-verify-banner sim-verify-${tanCotCheck.severity}`} role="status">
          <strong>{formatVerifyTone(tanCotCheck.severity)}</strong>
          <span>{tanCotCheck.message}</span>
        </div>
        {(visible.tan || visible.cot) && (
          <p className="trig-asymptote-hint">Đường đứt nét trên đồ thị đánh dấu vùng gần tiệm cận của tan/cot (giá trị không xác định).</p>
        )}

        <div className="trig-toggle-list">
          {(['sin', 'cos', 'tan', 'cot'] as VisibleKey[]).map((key) => (
            <button key={key} type="button" className={visible[key] ? `active ${key}` : ''} onClick={() => toggle(key)}>
              <span />
              <KatexSpan tex={`\\${key}\\theta`} />
            </button>
          ))}
        </div>
      </aside>

      <TrigStagePanel
        baseAngleRad={baseAngleRad}
        phaseAngleRad={phaseAngleRad}
        phaseDeg={phaseDeg}
        showTan={visible.tan}
        visible={visible}
        waves={waves}
        onAngleChange={setAngleRad}
      />
    </section>
  );
}

function sampleShiftedTrigWave(kind: VisibleKey, phaseRad: number, amplitude = 1, frequency = 1) {
  return sampleTrigWave(kind, GRAPH_MIN, GRAPH_MAX, 420).map((point) => {
    const arg = frequency * point.x + phaseRad;
    const raw = shiftedTrigValue(kind, arg);
    const y = Number.isFinite(raw) ? amplitude * raw : NaN;
    return {
      ...point,
      y,
      valid: Number.isFinite(y) && Math.abs(y) <= 6,
    };
  });
}

function shiftedTrigValue(kind: VisibleKey, value: number) {
  if (kind === 'sin') return Math.sin(value);
  if (kind === 'cos') return Math.cos(value);
  if (kind === 'tan') {
    const tan = safeTan(value);
    return tan.undefined ? NaN : tan.value;
  }
  const cot = safeCot(value);
  return cot.undefined ? NaN : cot.value;
}

function ValueTile({ label, value, tone }: { label: ReactNode; value: string; tone: string }) {
  return (
    <article className={`trig-value-tile ${tone}`}>
      <span className="trig-value-tile-label">{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function trigPlotPixelSide(panel: HTMLElement, circleBoard: HTMLElement, waveBoard: HTMLElement) {
  const innerPad = 24;
  const w1 = Math.max(80, circleBoard.clientWidth - innerPad);
  const w2 = Math.max(80, waveBoard.clientWidth - innerPad);
  const vwCap = typeof window !== 'undefined' ? Math.min(400, window.innerWidth * 0.32) : 400;
  const raw = Math.min(w1, (w2 * TRIG_SVG_SIZE) / TRIG_WAVE_VIEW_W, vwCap, TRIG_SVG_SIZE);
  return Math.floor(TRIG_PLOT_PIXEL_SCALE * raw);
}

function TrigStagePanel({
  baseAngleRad,
  phaseAngleRad,
  phaseDeg,
  showTan,
  visible,
  waves,
  onAngleChange,
}: {
  baseAngleRad: number;
  phaseAngleRad: number;
  phaseDeg: number;
  showTan: boolean;
  visible: Record<VisibleKey, boolean>;
  waves: Record<VisibleKey, WavePoint[]>;
  onAngleChange: (angle: number) => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const circleBoardRef = useRef<HTMLDivElement>(null);
  const waveBoardRef = useRef<HTMLDivElement>(null);
  const pointRef = useRef<SVGCircleElement>(null);
  const sinDotRef = useRef<SVGCircleElement>(null);
  const cosDotRef = useRef<SVGCircleElement>(null);
  const cosRot90DotRef = useRef<SVGCircleElement>(null);
  const [plotPx, setPlotPx] = useState<number | null>(null);
  type SyncSeg = { x1: number; y1: number; x2: number; y2: number } | null;
  const [syncLines, setSyncLines] = useState<{ sin: SyncSeg; cos: SyncSeg }>({ sin: null, cos: null });

  const updateSyncLines = useCallback(() => {
    const panel = panelRef.current;
    if (!panel) {
      setSyncLines({ sin: null, cos: null });
      return;
    }
    const pr = panel.getBoundingClientRect();
    let sin: SyncSeg = null;
    if (visible.sin && pointRef.current && sinDotRef.current) {
      const a = pointRef.current.getBoundingClientRect();
      const b = sinDotRef.current.getBoundingClientRect();
      sin = {
        x1: a.left + a.width / 2 - pr.left,
        y1: a.top + a.height / 2 - pr.top,
        x2: b.left + b.width / 2 - pr.left,
        y2: b.top + b.height / 2 - pr.top,
      };
    }
    let cos: SyncSeg = null;
    const cosBridgeEnd = cosRot90DotRef.current ?? cosDotRef.current;
    if (visible.cos && pointRef.current && cosBridgeEnd) {
      const a = pointRef.current.getBoundingClientRect();
      const b = cosBridgeEnd.getBoundingClientRect();
      cos = {
        x1: a.left + a.width / 2 - pr.left,
        y1: a.top + a.height / 2 - pr.top,
        x2: b.left + b.width / 2 - pr.left,
        y2: b.top + b.height / 2 - pr.top,
      };
    }
    setSyncLines((prev) => {
      if (
        prev.sin?.x1 === sin?.x1 && prev.sin?.y1 === sin?.y1 && prev.sin?.x2 === sin?.x2 && prev.sin?.y2 === sin?.y2
        && prev.cos?.x1 === cos?.x1 && prev.cos?.y1 === cos?.y1 && prev.cos?.x2 === cos?.x2 && prev.cos?.y2 === cos?.y2
      ) return prev;
      return { sin, cos };
    });
  }, [phaseAngleRad, visible.sin, visible.cos]);

  const syncPlotSize = useCallback(() => {
    const panel = panelRef.current;
    const cb = circleBoardRef.current;
    const wb = waveBoardRef.current;
    if (!panel || !cb || !wb) return;
    const next = trigPlotPixelSide(panel, cb, wb);
    if (next < 40) return;
    setPlotPx((prev) => (prev === next ? prev : next));
  }, []);

  useLayoutEffect(() => {
    syncPlotSize();
    updateSyncLines();
    const panel = panelRef.current;
    const cb = circleBoardRef.current;
    const wb = waveBoardRef.current;
    const onResize = () => {
      syncPlotSize();
      updateSyncLines();
    };
    const ro = typeof ResizeObserver !== 'undefined' && panel ? new ResizeObserver(onResize) : null;
    if (panel) ro?.observe(panel);
    if (cb) ro?.observe(cb);
    if (wb) ro?.observe(wb);
    window.addEventListener('resize', onResize);
    window.addEventListener('scroll', updateSyncLines, true);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', onResize);
      window.removeEventListener('scroll', updateSyncLines, true);
    };
  }, [syncPlotSize, updateSyncLines]);

  useLayoutEffect(() => {
    updateSyncLines();
  }, [plotPx, updateSyncLines]);

  return (
    <div ref={panelRef} className="trig-stage-panel">
      <UnitCircle boardRef={circleBoardRef} plotPx={plotPx} baseAngleRad={baseAngleRad} phaseAngleRad={phaseAngleRad} phaseDeg={phaseDeg} showTan={showTan} waves={waves} showCosRotatedWave={visible.cos} cosRot90DotRef={cosRot90DotRef} onAngleChange={onAngleChange} pointRef={pointRef} />
      <WaveGraph boardRef={waveBoardRef} plotPx={plotPx} angleRad={phaseAngleRad} waves={waves} visible={visible} sinDotRef={sinDotRef} cosDotRef={cosDotRef} />
      {(syncLines.sin || syncLines.cos) && (
        <svg className="trig-sync-bridge" aria-hidden="true">
          {syncLines.sin && <line x1={syncLines.sin.x1} y1={syncLines.sin.y1} x2={syncLines.sin.x2} y2={syncLines.sin.y2} className="trig-sync-bridge-line trig-sync-bridge-line--sin" />}
          {syncLines.cos && <line x1={syncLines.cos.x1} y1={syncLines.cos.y1} x2={syncLines.cos.x2} y2={syncLines.cos.y2} className="trig-sync-bridge-line trig-sync-bridge-line--cos" />}
        </svg>
      )}
    </div>
  );
}

function TrigWaveGraphSvg({
  angleRad,
  waves,
  visible,
  plotPx,
  sinDotRef,
  cosDotRef,
  ariaLabel,
  showOrthogonalAxis,
}: {
  angleRad: number;
  waves: Record<VisibleKey, WavePoint[]>;
  visible: Record<VisibleKey, boolean>;
  plotPx: number | null;
  sinDotRef?: React.RefObject<SVGCircleElement | null>;
  cosDotRef?: React.RefObject<SVGCircleElement | null>;
  ariaLabel: string;
  showOrthogonalAxis?: boolean;
}) {
  const width = TRIG_WAVE_VIEW_W;
  const height = TRIG_SVG_SIZE;
  const pad = 50;
  const markerX = pad + ((angleRad - GRAPH_MIN) / (GRAPH_MAX - GRAPH_MIN)) * (width - pad * 2);
  const midX = pad + (width - 2 * pad) / 2;
  const project = (x: number, y: number) => ({
    x: pad + ((x - GRAPH_MIN) / (GRAPH_MAX - GRAPH_MIN)) * (width - pad * 2),
    y: height / 2 - y * TRIG_UNIT_RADIUS_U,
  });
  const plotStyle = plotPx != null && plotPx > 0
    ? { width: (plotPx * TRIG_WAVE_VIEW_W) / TRIG_SVG_SIZE, height: plotPx, display: 'block' as const, marginInline: 'auto' as const } as const
    : undefined;

  return (
    <svg style={plotStyle} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
      <rect x="0" y="0" width={width} height={height} className="trig-canvas-bg" />
      <line x1={pad} x2={width - pad} y1={height / 2} y2={height / 2} className="trig-axis" />
      {showOrthogonalAxis && <line x1={midX} x2={midX} y1={pad} y2={height - pad} className="trig-axis" aria-hidden="true" />}
      {[0, Math.PI / 2, Math.PI, 3 * Math.PI / 2, TAU].map((x, index) => <g key={x}><line x1={project(x, 0).x} x2={project(x, 0).x} y1={pad} y2={height - pad} className="trig-grid-line" /><SvgKatexLabel x={project(x, 0).x} y={height - 14} tex={WAVE_TICK_LABELS[index]} className="trig-graph-label" /></g>)}
      {[-1, 1].map((y) => <g key={y}><line x1={pad} x2={width - pad} y1={project(0, y).y} y2={project(0, y).y} className="trig-grid-line" /><text x={pad - 6} y={project(0, y).y + 5} className="trig-y-label">{y}</text></g>)}
      {visible.cos && <path d={buildPath(waves.cos, project)} className="trig-wave-path cos" />}
      {visible.sin && <path d={buildPath(waves.sin, project)} className="trig-wave-path sin" />}
      {visible.tan && <path d={buildPath(waves.tan.filter((point) => !point.valid || Math.abs(point.y) <= 1.5), project)} className="trig-wave-path tan" />}
      {visible.cot && <path d={buildPath(waves.cot.filter((point) => !point.valid || Math.abs(point.y) <= 1.5), project)} className="trig-wave-path cot" />}
      <line x1={markerX} x2={markerX} y1={pad} y2={height - pad} className="trig-marker" />
      {visible.sin && <circle ref={sinDotRef as React.Ref<SVGCircleElement> | undefined} cx={markerX} cy={project(angleRad, Math.sin(angleRad)).y} r="7" className="trig-wave-dot sin" />}
      {visible.cos && <circle ref={cosDotRef as React.Ref<SVGCircleElement> | undefined} cx={markerX} cy={project(angleRad, Math.cos(angleRad)).y} r="7" className="trig-wave-dot cos" />}
    </svg>
  );
}

function SvgKatexLabel({ x, y, tex, className, width = 66, height = 24 }: { x: number; y: number; tex: string; className?: string; width?: number; height?: number }) {
  return (
    <foreignObject x={x - width / 2} y={y - height / 2} width={width} height={height} className={className}>
      <div className="trig-svg-katex-label">
        <KatexSpan tex={tex} />
      </div>
    </foreignObject>
  );
}

function WaveGraphCosRotated90({
  angleRad,
  plotPx,
  waves,
  cosDotRef,
}: {
  angleRad: number;
  plotPx: number | null;
  waves: Record<VisibleKey, WavePoint[]>;
  cosDotRef: React.RefObject<SVGCircleElement | null>;
}) {
  const visibleCosOnly: Record<VisibleKey, boolean> = { sin: false, cos: true, tan: false, cot: false };
  const waveW = plotPx != null && plotPx > 0 ? (plotPx * TRIG_WAVE_VIEW_W) / TRIG_SVG_SIZE : 0;
  const frameH = plotPx != null && plotPx > 0 ? (plotPx * TRIG_WAVE_VIEW_W) / TRIG_SVG_SIZE : undefined;
  const frameStyle = plotPx != null && plotPx > 0
    ? { width: plotPx, height: frameH, position: 'relative' as const, marginInline: 'auto' as const }
    : undefined;
  const spinStyle = plotPx != null && plotPx > 0 && waveW > 0
    ? {
        position: 'absolute' as const,
        left: '50%',
        top: '50%',
        width: waveW,
        height: plotPx,
        transform: 'translate(-50%, -50%) rotate(90deg)',
      }
    : undefined;

  return (
    <div className="trig-board trig-board-wave trig-board-wave--rot90">
      <div className="trig-wave-rot90-frame" style={frameStyle}>
        <div className="trig-wave-rot90-spin" style={spinStyle}>
          <TrigWaveGraphSvg
            angleRad={angleRad}
            waves={waves}
            visible={visibleCosOnly}
            plotPx={plotPx}
            cosDotRef={cosDotRef}
            showOrthogonalAxis
            ariaLabel="Đồ thị cos θ theo θ (xoay 90 độ, cùng tỉ lệ với đồ thị chính)"
          />
        </div>
      </div>
    </div>
  );
}

function UnitCircle({
  boardRef,
  plotPx,
  baseAngleRad,
  phaseAngleRad,
  phaseDeg,
  showTan,
  waves,
  showCosRotatedWave,
  cosRot90DotRef,
  onAngleChange,
  pointRef,
}: {
  boardRef: React.RefObject<HTMLDivElement | null>;
  plotPx: number | null;
  baseAngleRad: number;
  phaseAngleRad: number;
  phaseDeg: number;
  showTan: boolean;
  waves: Record<VisibleKey, WavePoint[]>;
  showCosRotatedWave: boolean;
  cosRot90DotRef: React.RefObject<SVGCircleElement | null>;
  onAngleChange: (angle: number) => void;
  pointRef: React.RefObject<SVGCircleElement | null>;
}) {
  const size = TRIG_SVG_SIZE;
  const center = size / 2;
  const radius = TRIG_UNIT_RADIUS_U;
  const baseSin = Math.sin(baseAngleRad);
  const baseCos = Math.cos(baseAngleRad);
  const sin = Math.sin(phaseAngleRad);
  const cos = Math.cos(phaseAngleRad);
  const tan = safeTan(phaseAngleRad);
  const baseP = { x: center + baseCos * radius, y: center - baseSin * radius };
  const p = { x: center + cos * radius, y: center - sin * radius };
  const tanY = tan.undefined ? null : center - tan.value * radius;
  const phaseDirection = phaseDeg === 0 ? 'Cùng pha' : phaseDeg > 0 ? 'Q chạy trước P' : 'Q chạy sau P';
  const phaseAbs = Math.abs(phaseDeg);
  const arcRadius = 54;
  const arcStart = { x: center + Math.cos(baseAngleRad) * arcRadius, y: center - Math.sin(baseAngleRad) * arcRadius };
  const arcEnd = { x: center + Math.cos(phaseAngleRad) * arcRadius, y: center - Math.sin(phaseAngleRad) * arcRadius };
  const deltaRad = Math.atan2(Math.sin(phaseAngleRad - baseAngleRad), Math.cos(phaseAngleRad - baseAngleRad));
  const arcMidAngle = normalizeAngleRad(baseAngleRad + deltaRad / 2);
  const arcLabel = { x: center + Math.cos(arcMidAngle) * (arcRadius + 24), y: center - Math.sin(arcMidAngle) * (arcRadius + 24) };
  const arcLarge = Math.abs(deltaRad) > Math.PI - 1e-6 ? 1 : 0;
  const arcSweep = deltaRad > 0 ? 1 : 0;

  function handlePointer(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = rect.height / 2 - (event.clientY - rect.top);
    onAngleChange(Math.atan2(y, x));
  }

  const plotStyle = plotPx != null && plotPx > 0 ? { width: plotPx, height: plotPx } as const : undefined;

  return (
    <div ref={boardRef as React.Ref<HTMLDivElement>} className="trig-board trig-board-circle">
      <svg style={plotStyle} viewBox={`0 0 ${size} ${size}`} onPointerDown={handlePointer} onPointerMove={(event) => { if (event.buttons === 1) handlePointer(event); }} role="img" aria-label="Vòng tròn đơn vị">
        <rect x="0" y="0" width={size} height={size} className="trig-canvas-bg" />
        {[-1, -0.5, 0.5, 1].map((value) => <g key={value}><line x1={center + value * radius} x2={center + value * radius} y1={center - radius - 20} y2={center + radius + 20} className="trig-grid-line" /><line x1={center - radius - 20} x2={center + radius + 20} y1={center - value * radius} y2={center - value * radius} className="trig-grid-line" /></g>)}
        <line x1="46" x2={size - 46} y1={center} y2={center} className="trig-axis" />
        <line x1={center} x2={center} y1="46" y2={size - 46} className="trig-axis" />
        <circle cx={center} cy={center} r={radius} className="trig-unit-outline" />
        {SPECIAL_ANGLES.filter((angle) => (angle.degree % 45 === 0 || angle.degree % 90 === 0) && angle.degree !== 360).map((angle) => {
          const x = center + Math.cos(angle.radian) * radius;
          const y = center - Math.sin(angle.radian) * radius;
          const labelR = radius + 36;
          let lx = center + Math.cos(angle.radian) * labelR;
          let ly = center - Math.sin(angle.radian) * labelR;
          const nudgeY = 16;
          const nudgeX90 = 20;
          const nudgeX270 = 25;
          if (angle.degree === 0 || angle.degree === 180) {
            ly += nudgeY;
          } else if (angle.degree === 90) {
            lx += nudgeX90;
          } else if (angle.degree === 270) {
            lx -= nudgeX270;
          }
          return (
            <g key={angle.degree}>
              <circle cx={x} cy={y} r="4.5" className="trig-special-dot" />
              <text x={lx} y={ly} className="trig-special-label" dominantBaseline="middle" textAnchor="middle">{angle.degree}°</text>
            </g>
          );
        })}
        <line x1={center} y1={center} x2={baseP.x} y2={baseP.y} className="trig-base-radius" />
        <circle cx={baseP.x} cy={baseP.y} r="8" className="trig-base-point" />
        <text x={baseP.x + 12} y={baseP.y + 18} className="trig-base-point-label">P</text>
        {phaseAbs > 0 && <path d={`M ${arcStart.x} ${arcStart.y} A ${arcRadius} ${arcRadius} 0 ${arcLarge} ${arcSweep} ${arcEnd.x} ${arcEnd.y}`} className={phaseDeg > 0 ? 'trig-phase-arc is-leading' : 'trig-phase-arc is-lagging'} />}
        {phaseAbs > 0 && <SvgKatexLabel x={arcLabel.x} y={arcLabel.y} tex={String.raw`\varphi=${phaseDeg > 0 ? '+' : '-'}${phaseAbs}^{\circ}`} className="trig-phase-label" width={86} />}
        {phaseAbs > 0 && <text x={center} y={center + radius + 62} className={phaseDeg > 0 ? 'trig-phase-state is-leading' : 'trig-phase-state is-lagging'}>{phaseDirection}</text>}
        <line x1={center} y1={center} x2={p.x} y2={p.y} className="trig-radius" />
        <line x1={center} y1={center} x2={p.x} y2={center} className="trig-cos-segment" />
        <line x1={p.x} y1={center} x2={p.x} y2={p.y} className="trig-sin-segment" />
        <line x1={center} y1={center} x2={p.x} y2={p.y} className="trig-hypotenuse" />
        {showTan && <line x1={center + radius} x2={center + radius} y1={center - radius - 16} y2={center + radius + 16} className="trig-tan-axis" />}
        {showTan && tanY !== null && Math.abs(tan.value) < 2.4 && <><line x1={center + radius} y1={center} x2={center + radius} y2={tanY} className="trig-tan-segment" /><line x1={p.x} y1={p.y} x2={center + radius} y2={tanY} className="trig-tan-link" /></>}
        {showTan && tan.undefined && <text x={center + radius + 12} y={center - 8} className="trig-undefined-label">tan không xác định</text>}
        <circle ref={pointRef as React.Ref<SVGCircleElement>} cx={p.x} cy={p.y} r="11" className="trig-point" />
        <text x={p.x + 14} y={p.y - 14} className="trig-point-label">Q</text>
      </svg>
      {showCosRotatedWave && <WaveGraphCosRotated90 angleRad={phaseAngleRad} plotPx={plotPx} waves={waves} cosDotRef={cosRot90DotRef} />}
    </div>
  );
}

function WaveGraph({
  boardRef,
  plotPx,
  angleRad,
  waves,
  visible,
  sinDotRef,
  cosDotRef,
}: {
  boardRef: React.RefObject<HTMLDivElement | null>;
  plotPx: number | null;
  angleRad: number;
  waves: Record<VisibleKey, WavePoint[]>;
  visible: Record<VisibleKey, boolean>;
  sinDotRef: React.RefObject<SVGCircleElement | null>;
  cosDotRef: React.RefObject<SVGCircleElement | null>;
}) {
  return (
    <div ref={boardRef as React.Ref<HTMLDivElement>} className="trig-board trig-board-wave">
      <TrigWaveGraphSvg
        angleRad={angleRad}
        waves={waves}
        visible={visible}
        plotPx={plotPx}
        sinDotRef={sinDotRef}
        cosDotRef={cosDotRef}
        ariaLabel="Đồ thị sin cos tan theo góc"
      />
    </div>
  );
}

function buildPath(points: WavePoint[], project: (x: number, y: number) => { x: number; y: number }) {
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
