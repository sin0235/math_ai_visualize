import { useCallback, useEffect, useId, useRef, useState } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

type LabMode = 'graphing' | 'geometry' | '3d' | 'probability';
type LabSvgName = 'logo' | 'graphing' | 'geometry' | 'threeD' | 'probability' | 'chevronLeft' | 'chevronRight' | 'play' | 'undo' | 'redo' | 'trash' | 'save' | 'folder' | 'close';

interface GeoGebraApi {
  evalCommand: (cmd: string) => boolean | void;
  evalLaTeX?: (latex: string) => boolean | void;
  reset?: () => void;
  newConstruction?: () => void;
  setErrorDialogsActive?: (active: boolean) => void;
  setAxesVisible?: (x: boolean, y: boolean, z?: boolean) => void;
  setGridVisible?: (flag: boolean) => void;
  setPerspective?: (p: string) => void;
  setCoordSystem?: (xmin: number, xmax: number, ymin: number, ymax: number) => void;
  setSize?: (w: number, h: number) => void;
  setWidth?: (w: number) => void;
  setHeight?: (h: number) => void;
  getBase64?: (cb: (b64: string) => void) => void;
  setBase64?: (b64: string) => void;
  getPNGBase64?: (scale: number, transparent: boolean, dpi: number | undefined) => string;
  exportSVG?: (cb: (svg: string) => void) => void;
  exportPDF?: (scale: number, cb: (pdf: string) => void) => void;
  undo?: () => void;
  redo?: () => void;
  getAllObjectNames?: (type?: string) => string[];
  getObjectNumber?: () => number;
  showAllObjects?: () => void;
  setMode?: (mode: number) => void;
  getMode?: () => number;
  getValueString?: (name: string) => string;
  getObjectType?: (name: string) => string;
  exists?: (name: string) => boolean;
  setAnimating?: (name: string, animate: boolean) => void;
  startAnimation?: () => void;
  stopAnimation?: () => void;
  isAnimationRunning?: () => boolean;
  setRepaintingActive?: (flag: boolean) => void;
  refreshViews?: () => void;
  setPointCapture?: (view: number, mode: number) => void;
  setRounding?: (round: string) => void;
}

/* Window.GGBApplet is declared in GeoGebraView.tsx */
/* ------------------------------------------------------------------ */
/*  Tab configs                                                       */
/* ------------------------------------------------------------------ */

interface TabConfig {
  key: LabMode;
  label: string;
  desc: string;
  icon: LabSvgName;
  appName: string;
  perspective?: string;
  equalAxis?: boolean;
  presets: Preset[];
}

interface Preset {
  label: string;
  commands: string[];
  desc?: string;
}

const TABS: TabConfig[] = [
  {
    key: 'graphing',
    label: 'Graphing Calculator',
    desc: 'Đồ thị hàm số 2D, phương trình, bất phương trình',
    icon: 'graphing',
    appName: 'graphing',
    equalAxis: true,
    presets: [
      { label: 'Parabol', commands: ['f(x)=x^2'], desc: 'Đồ thị bậc 2' },
      { label: 'Đường tròn', commands: ['x^2+y^2=9'], desc: 'Tâm O, R = 3' },
      { label: 'Elip', commands: ['x^2/4+y^2/9=1'], desc: 'Elip chuẩn' },
      { label: 'Hyperbol', commands: ['x^2/4-y^2/9=1'], desc: 'Hyperbol chuẩn' },
      { label: 'Sin(x)', commands: ['f(x)=sin(x)'], desc: 'Hàm lượng giác' },
      { label: 'Bất PT', commands: ['y>=x^2'], desc: 'Miền nghiệm' },
      { label: 'Hàm bậc 3', commands: ['f(x)=x^3-3x+1'], desc: 'Cực trị, uốn' },
      { label: 'Đường thẳng', commands: ['y=2x+1', 'y=-x+3'], desc: 'Hai đường cắt nhau' },
    ],
  },
  {
    key: 'geometry',
    label: 'Geometry',
    desc: 'Hình học phẳng: tam giác, đường tròn, đa giác, góc',
    icon: 'geometry',
    appName: 'geometry',
    equalAxis: true,
    presets: [
      { label: 'Tam giác', commands: ['A=(0,0)', 'B=(4,0)', 'C=(2,3)', 'Polygon(A,B,C)'], desc: 'ABC' },
      { label: 'Tam giác đều', commands: ['A=(0,0)', 'B=(4,0)', 'RegularPolygon(A,B,3)'] },
      { label: 'Đường tròn ngoại tiếp', commands: ['A=(0,0)', 'B=(4,0)', 'C=(1,3)', 'Circumcircle(A,B,C)'] },
      { label: 'Trung điểm', commands: ['A=(0,0)', 'B=(6,4)', 'M=Midpoint(A,B)', 'Segment(A,B)'] },
      { label: 'Tiếp tuyến', commands: ['c:x^2+y^2=4', 'P=(2,0)', 'Tangent(P,c)'] },
      { label: 'Đa giác đều 6', commands: ['A=(0,0)', 'B=(3,0)', 'RegularPolygon(A,B,6)'] },
      { label: 'Đường cao', commands: ['A=(0,0)', 'B=(5,0)', 'C=(2,4)', 'Polygon(A,B,C)', 'PerpendicularLine(C,Line(A,B))'] },
      { label: 'Phép đối xứng', commands: ['A=(1,2)', 'B=(4,1)', 'l=Line(A,B)', 'P=(3,4)', 'Reflect(P,l)'] },
    ],
  },
  {
    key: '3d',
    label: '3D Calculator',
    desc: 'Đồ thị 3D, mặt phẳng, bề mặt, khối đa diện',
    icon: 'threeD',
    appName: '3d',
    presets: [
      { label: 'Mặt phẳng', commands: ['a:x+y+z=3'], desc: 'x+y+z=3' },
      { label: 'Mặt cầu', commands: ['x^2+y^2+z^2=9'], desc: 'R=3' },
      { label: 'Parabol xoay', commands: ['Surface(u*cos(v),u*sin(v),u^2,u,0,2,v,0,2*pi)'], desc: 'z=x^2+y^2' },
      { label: 'Hình nón', commands: ['Cone((0,0,3),(0,0,0),2)'], desc: 'Đỉnh (0,0,3), r=2' },
      { label: 'Hình trụ', commands: ['Cylinder((0,0,0),(0,0,3),1.5)'], desc: 'h=3, r=1.5' },
      { label: 'Tứ diện', commands: ['A=(0,0,0)', 'B=(3,0,0)', 'C=(1.5,2.6,0)', 'D=(1.5,0.87,2.45)', 'Polygon(A,B,C)', 'Polygon(A,B,D)', 'Polygon(B,C,D)', 'Polygon(A,C,D)'] },
      { label: 'Lăng trụ', commands: ['A=(0,0,0)', 'B=(3,0,0)', 'C=(1.5,2.6,0)', 'Prism(A,B,C,4)'] },
      { label: 'Mặt yên ngựa', commands: ['Surface(u,v,u^2-v^2,u,-2,2,v,-2,2)'], desc: 'z=x^2-y^2' },
    ],
  },
  {
    key: 'probability',
    label: 'Probability',
    desc: 'Phân phối chuẩn, nhị thức, Poisson, tính xác suất',
    icon: 'probability',
    appName: 'classic',
    perspective: '6',
    presets: [
      { label: 'Normal(0,1)', commands: ['Normal(0,1,1)'], desc: 'Phân phối chuẩn tắc' },
      { label: 'Normal(5,2)', commands: ['Normal(5,2,7)'], desc: 'μ=5, σ=2' },
      { label: 'Binomial(10,0.5)', commands: ['BinomialDist(10,0.5,3,true)'], desc: 'n=10, p=0.5' },
      { label: 'Poisson(4)', commands: ['Poisson(4,3,true)'], desc: 'λ=4' },
      { label: 'P(X<=2)', commands: ['Normal(0,1,2)'], desc: 'CDF chuẩn tắc tại x=2' },
    ],
  },
];

function LabSvg({ name }: { name: LabSvgName }) {
  const common = {
    className: `gglab-svg gglab-svg-${name}`,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    focusable: false,
  };

  switch (name) {
    case 'logo':
      return <svg {...common}><circle cx="12" cy="12" r="7.4" /><circle cx="7.2" cy="9.2" r="1.5" fill="currentColor" stroke="none" /><circle cx="11.8" cy="5.7" r="1.35" fill="currentColor" stroke="none" /><circle cx="17.1" cy="9.1" r="1.5" fill="currentColor" stroke="none" /><circle cx="16.2" cy="15.6" r="1.35" fill="currentColor" stroke="none" /><circle cx="9.1" cy="16.8" r="1.45" fill="currentColor" stroke="none" /><path d="M7.2 9.2 11.8 5.7l5.3 3.4-.9 6.5-7.1 1.2-1.9-7.6z" /></svg>;
    case 'graphing':
      return <svg {...common}><path d="M4 19.5h16" /><path d="M5 20V4.5" /><path d="M7 16c1.4-5.4 3.1-8.1 5.1-8.1 1.5 0 2.3 1.6 3 3.4.7 1.8 1.4 3.4 3 3.4.5 0 1-.2 1.5-.7" /><path d="M8 11.5h1.2M11.4 8.1h1.2M15.6 13.9h1.2" /></svg>;
    case 'geometry':
      return <svg {...common}><path d="M4.5 18.5 11.5 5l8 13.5h-15z" /><path d="M11.5 5v13.5" /><path d="M8.2 18.5a3.3 3.3 0 0 1 3.3-3.3" /><circle cx="4.5" cy="18.5" r="1.35" fill="currentColor" stroke="none" /><circle cx="11.5" cy="5" r="1.35" fill="currentColor" stroke="none" /><circle cx="19.5" cy="18.5" r="1.35" fill="currentColor" stroke="none" /></svg>;
    case 'threeD':
      return <svg {...common}><path d="m12 3.5 7 4.1v8.8l-7 4.1-7-4.1V7.6l7-4.1z" /><path d="m5 7.6 7 4.1 7-4.1" /><path d="M12 11.7v8.8" /><path d="M8.3 5.7 15.4 10" /></svg>;
    case 'probability':
      return <svg {...common}><path d="M4 19.5h16" /><path d="M5.5 18.5c1.2 0 1.8-1.7 2.4-4.5C8.7 9.9 9.8 5.5 12 5.5s3.3 4.4 4.1 8.5c.6 2.8 1.2 4.5 2.4 4.5" /><path d="M12 5.5v14" /><path d="M8.2 15.2h7.6" /></svg>;
    case 'chevronLeft':
      return <svg {...common}><path d="m14.5 6.5-5 5.5 5 5.5" /></svg>;
    case 'chevronRight':
      return <svg {...common}><path d="m9.5 6.5 5 5.5-5 5.5" /></svg>;
    case 'play':
      return <svg {...common}><path d="m8.3 5.6 10.2 6.4-10.2 6.4V5.6z" fill="currentColor" stroke="none" /></svg>;
    case 'undo':
      return <svg {...common}><path d="M8.5 7.2H4.8v3.7" /><path d="M4.8 10.9c2-3.1 5.8-4.5 9.2-3.2 3.7 1.4 5.2 5.7 3.1 9-.8 1.3-2.1 2.2-3.6 2.6" /></svg>;
    case 'redo':
      return <svg {...common}><path d="M15.5 7.2h3.7v3.7" /><path d="M19.2 10.9c-2-3.1-5.8-4.5-9.2-3.2-3.7 1.4-5.2 5.7-3.1 9 .8 1.3 2.1 2.2 3.6 2.6" /></svg>;
    case 'trash':
      return <svg {...common}><path d="M4.5 7h15" /><path d="M9.2 7V4.8h5.6V7" /><path d="M6.8 7 7.7 20h8.6l.9-13" /><path d="M10.2 11v5.6M13.8 11v5.6" /></svg>;
    case 'save':
      return <svg {...common}><path d="M5 4.5h11.4L19 7.1V19.5H5v-15z" /><path d="M8 4.5v5h7v-5" /><path d="M8 19.5v-6h8v6" /></svg>;
    case 'folder':
      return <svg {...common}><path d="M3.5 7.2h6.2l2 2h8.8v8.9a2.4 2.4 0 0 1-2.4 2.4H5.9a2.4 2.4 0 0 1-2.4-2.4V7.2z" /><path d="M3.5 7.2V5.9a2.4 2.4 0 0 1 2.4-2.4h3.4l2 2h6.8a2.4 2.4 0 0 1 2.4 2.4v1.3" /></svg>;
    case 'close':
      return <svg {...common}><path d="m7 7 10 10M17 7 7 17" /></svg>;
  }
}

/* ------------------------------------------------------------------ */
/*  GeoGebra script loader (shared with GeoGebraView.tsx)             */
/* ------------------------------------------------------------------ */

let ggbLoadPromise: Promise<void> | null = null;

function loadGeoGebraScript(): Promise<void> {
  if (window.GGBApplet) return Promise.resolve();
  if (ggbLoadPromise) return ggbLoadPromise;
  ggbLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-geogebra]');
    const script = existing ?? document.createElement('script');
    const done = () => { script.removeEventListener('load', onLoad); script.removeEventListener('error', onErr); };
    const onLoad = () => { done(); window.GGBApplet ? resolve() : (ggbLoadPromise = null, reject(new Error('GGBApplet not found'))); };
    const onErr = () => { done(); ggbLoadPromise = null; reject(new Error('Failed to load GeoGebra')); };
    script.addEventListener('load', onLoad);
    script.addEventListener('error', onErr);
    if (!existing) { script.src = 'https://www.geogebra.org/apps/deployggb.js'; script.async = true; script.dataset.geogebra = 'true'; document.body.appendChild(script); }
  });
  return ggbLoadPromise;
}

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export function GeoGebraLabPage() {
  const [mode, setMode] = useState<LabMode>('graphing');
  const [cmdText, setCmdText] = useState('');
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const [objectCount, setObjectCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [savedStates, setSavedStates] = useState<Record<string, string>>({});
  const [saveLabel, setSaveLabel] = useState('');

  const rawId = useId();
  const containerId = `gglab-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const apiRef = useRef<GeoGebraApi | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const workspaceRef = useRef<HTMLDivElement | null>(null);

  const tab = TABS.find((t) => t.key === mode)!;

  /* ---------- inject applet ---------- */
  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    setErrorMsg('');
    setObjectCount(0);
    apiRef.current = null;

    const host = containerRef.current;
    if (host) host.innerHTML = '';

    loadGeoGebraScript()
      .then(() => {
        if (cancelled || !window.GGBApplet) return;
        const bounds = workspaceRef.current ?? containerRef.current;
        const w = Math.max(bounds?.clientWidth ?? 800, 400);
        const h = Math.max(bounds?.clientHeight ?? 600, 400);

        const params: Record<string, unknown> = {
          appName: tab.appName,
          id: containerId,
          width: w,
          height: h,
          scaleContainerClass: 'gglab-workspace',
          autoHeight: false,
          allowUpscale: true,
          showToolBar: true,
          showAlgebraInput: true,
          showMenuBar: true,
          showResetIcon: true,
          enableShiftDragZoom: true,
          enableRightClick: true,
          enableLabelDrags: true,
          allowStyleBar: true,
          showZoomButtons: true,
          enableUndoRedo: true,
          errorDialogsActive: false,
          language: 'vi',
          showToolBarHelp: true,
          preventFocus: false,
          ...(tab.perspective ? { perspective: tab.perspective } : {}),
          appletOnLoad: (api: GeoGebraApi) => {
            if (cancelled) return;
            apiRef.current = api;
            api.setErrorDialogsActive?.(false);
            if (tab.perspective) setGeoGebraPerspective(api, tab.perspective);
            requestAnimationFrame(() => resizeLabApplet(api, workspaceRef.current ?? containerRef.current, tab));
            setStatus('ready');
            refreshObjectCount(api);
          },
        };
        const applet = new window.GGBApplet!(params, true as unknown as string);
        applet.inject(containerId);
      })
      .catch((err) => {
        if (!cancelled) { setStatus('error'); setErrorMsg(err instanceof Error ? err.message : 'Không tải được GeoGebra'); }
      });

    return () => { cancelled = true; apiRef.current = null; if (host) host.innerHTML = ''; };
  }, [mode, containerId, tab.appName, tab.perspective]);

  /* ---------- resize observer ---------- */
  useEffect(() => {
    if (status !== 'ready' || !workspaceRef.current) return;
    let frame = 0;
    const obs = new ResizeObserver(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => resizeLabApplet(apiRef.current, workspaceRef.current ?? containerRef.current, tab));
    });
    obs.observe(workspaceRef.current);
    return () => { obs.disconnect(); if (frame) cancelAnimationFrame(frame); };
  }, [status]);

  useEffect(() => {
    if (status !== 'ready') return;
    const resize = () => resizeLabApplet(apiRef.current, workspaceRef.current ?? containerRef.current, tab);
    const frame = requestAnimationFrame(resize);
    const timers = [80, 240].map((delay) => window.setTimeout(resize, delay));
    return () => {
      cancelAnimationFrame(frame);
      timers.forEach(window.clearTimeout);
    };
  }, [sidebarOpen, status, tab]);

  /* ---------- helpers ---------- */
  function refreshObjectCount(api: GeoGebraApi | null) {
    if (!api) return;
    setObjectCount(api.getObjectNumber?.() ?? 0);
  }

  function runCommand(cmd: string) {
    const api = apiRef.current;
    if (!api || !cmd.trim()) return;
    cmd.split('\n').forEach((line) => {
      const trimmed = line.trim();
      if (trimmed) api.evalCommand(trimmed);
    });
    refreshObjectCount(api);
    setCmdHistory((prev) => [cmd, ...prev.slice(0, 49)]);
    setCmdText('');
  }

  function applyPreset(preset: Preset) {
    const api = apiRef.current;
    if (!api) return;
    api.newConstruction?.();
    api.setErrorDialogsActive?.(false);
    preset.commands.forEach((c) => api.evalCommand(c));
    if (tab.equalAxis) applyEqualAxis(api, workspaceRef.current?.clientWidth ?? 0, workspaceRef.current?.clientHeight ?? 0);
    api.showAllObjects?.();
    refreshObjectCount(api);
  }

  function clearAll() {
    apiRef.current?.newConstruction?.();
    setObjectCount(0);
  }

  const handleUndo = useCallback(() => { apiRef.current?.undo?.(); refreshObjectCount(apiRef.current); }, []);
  const handleRedo = useCallback(() => { apiRef.current?.redo?.(); refreshObjectCount(apiRef.current); }, []);

  function exportPNG() {
    const api = apiRef.current;
    if (!api?.getPNGBase64) return;
    const b64 = api.getPNGBase64(2, true, undefined);
    downloadDataUrl(`data:image/png;base64,${b64}`, `geogebra-${mode}.png`);
  }

  function exportSVG() {
    apiRef.current?.exportSVG?.((svg) => {
      if (!svg) return;
      const blob = new Blob([svg], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      downloadDataUrl(url, `geogebra-${mode}.svg`);
      URL.revokeObjectURL(url);
    });
  }

  function exportPDF() {
    apiRef.current?.exportPDF?.(1, (pdf) => {
      if (!pdf) return;
      const link = document.createElement('a');
      link.href = pdf;
      link.download = `geogebra-${mode}.pdf`;
      link.click();
    });
  }

  function saveState() {
    apiRef.current?.getBase64?.((b64) => {
      const key = saveLabel.trim() || `${tab.label} — ${new Date().toLocaleTimeString('vi-VN')}`;
      setSavedStates((prev) => ({ ...prev, [key]: b64 }));
      setSaveLabel('');
    });
  }

  function loadState(b64: string) {
    apiRef.current?.setBase64?.(b64);
    setTimeout(() => refreshObjectCount(apiRef.current), 500);
  }

  function deleteState(key: string) {
    setSavedStates((prev) => { const next = { ...prev }; delete next[key]; return next; });
  }

  /* ---------- render ---------- */
  return (
    <section className="gglab-page">
      {/* ---- Header ---- */}
      <div className="gglab-header">
        <div className="gglab-header-title">
          <span className="gglab-logo" aria-hidden="true"><LabSvg name="logo" /></span>
          <div>
            <h2>GeoGebra Lab</h2>
            <span className="gglab-subtitle">Dựng hình chuyên nghiệp bằng công thức</span>
          </div>
        </div>
        <div className="gglab-tabs" role="tablist" aria-label="Chế độ GeoGebra">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={mode === t.key}
              className={`gglab-tab${mode === t.key ? ' active' : ''}`}
              onClick={() => setMode(t.key)}
              title={t.desc}
            >
              <span className="gglab-tab-icon"><LabSvg name={t.icon} /></span>
              <span className="gglab-tab-label">{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ---- Body ---- */}
      <div className={`gglab-body${sidebarOpen ? '' : ' sidebar-collapsed'}`}>
        {/* ---- Sidebar ---- */}
        <aside className="gglab-sidebar" aria-label="Công cụ phụ">
          <button type="button" className="gglab-sidebar-toggle" onClick={() => setSidebarOpen((v) => !v)} aria-label={sidebarOpen ? 'Thu sidebar' : 'Mở sidebar'}>
            <LabSvg name={sidebarOpen ? 'chevronLeft' : 'chevronRight'} />
          </button>
          {sidebarOpen && (
            <div className="gglab-sidebar-content">
              {/* Command input */}
              <div className="gglab-section">
                <strong className="gglab-section-title">Nhập lệnh GeoGebra</strong>
                <div className="gglab-cmd-row">
                  <input
                    type="text"
                    className="gglab-cmd-input"
                    placeholder="VD: f(x)=x^2, Polygon(A,B,C)"
                    value={cmdText}
                    onChange={(e) => setCmdText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runCommand(cmdText); } }}
                    disabled={status !== 'ready'}
                  />
                  <button type="button" className="gglab-cmd-run" onClick={() => runCommand(cmdText)} disabled={status !== 'ready' || !cmdText.trim()} aria-label="Chạy lệnh"><LabSvg name="play" /></button>
                </div>
                {cmdHistory.length > 0 && (
                  <details className="gglab-cmd-history">
                    <summary>Lịch sử lệnh ({cmdHistory.length})</summary>
                    <ul>{cmdHistory.map((c, i) => <li key={i}><button type="button" onClick={() => runCommand(c)} title="Chạy lại">{c}</button></li>)}</ul>
                  </details>
                )}
              </div>

              {/* Presets */}
              <div className="gglab-section">
                <strong className="gglab-section-title">Mẫu nhanh - {tab.label}</strong>
                <div className="gglab-presets">
                  {tab.presets.map((p) => (
                    <button key={p.label} type="button" className="gglab-preset" onClick={() => applyPreset(p)} disabled={status !== 'ready'} title={p.desc || p.commands.join('; ')}>
                      <strong>{p.label}</strong>
                      {p.desc && <small>{p.desc}</small>}
                    </button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="gglab-section">
                <strong className="gglab-section-title">Thao tác</strong>
                <div className="gglab-actions">
                  <button type="button" onClick={handleUndo} disabled={status !== 'ready'} title="Hoàn tác"><LabSvg name="undo" /><span>Undo</span></button>
                  <button type="button" onClick={handleRedo} disabled={status !== 'ready'} title="Làm lại"><LabSvg name="redo" /><span>Redo</span></button>
                  <button type="button" onClick={clearAll} disabled={status !== 'ready'} title="Xoá tất cả"><LabSvg name="trash" /><span>Xoá</span></button>
                </div>
                <span className="gglab-obj-count">{objectCount} đối tượng</span>
              </div>

              {/* Export */}
              <div className="gglab-section">
                <strong className="gglab-section-title">Xuất hình</strong>
                <div className="gglab-actions">
                  <button type="button" onClick={exportPNG} disabled={status !== 'ready'}>PNG</button>
                  <button type="button" onClick={exportSVG} disabled={status !== 'ready'}>SVG</button>
                  <button type="button" onClick={exportPDF} disabled={status !== 'ready'}>PDF</button>
                </div>
              </div>

              {/* Save / Load */}
              <div className="gglab-section">
                <strong className="gglab-section-title">Lưu / Tải trạng thái</strong>
                <div className="gglab-save-row">
                  <input type="text" placeholder="Tên bản lưu (tuỳ chọn)" className="gglab-cmd-input" value={saveLabel} onChange={(e) => setSaveLabel(e.target.value)} />
                  <button type="button" onClick={saveState} disabled={status !== 'ready'}><LabSvg name="save" /><span>Lưu</span></button>
                </div>
                {Object.keys(savedStates).length > 0 && (
                  <div className="gglab-saved-list">
                    {Object.entries(savedStates).map(([key, b64]) => (
                      <div key={key} className="gglab-saved-item">
                        <button type="button" onClick={() => loadState(b64)} title="Tải lại trạng thái"><LabSvg name="folder" /><span>{key}</span></button>
                        <button type="button" className="gglab-saved-delete" onClick={() => deleteState(key)} aria-label="Xoá"><LabSvg name="close" /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>

        {/* ---- Applet area ---- */}
        <div className="gglab-workspace" ref={workspaceRef}>
          {status === 'loading' && (
            <div className="gglab-overlay">
              <div className="gglab-loading">
                <span className="sp-spinner" />
                <span>Đang tải {tab.label}…</span>
              </div>
            </div>
          )}
          {status === 'error' && (
            <div className="gglab-overlay">
              <div className="gglab-error">
                <strong>Không thể tải GeoGebra</strong>
                <p>{errorMsg}</p>
                <button type="button" onClick={() => setMode(mode)}>Thử lại</button>
              </div>
            </div>
          )}
          <div ref={containerRef} id={containerId} className="gglab-applet" />
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Utils                                                             */
/* ------------------------------------------------------------------ */

function resizeLabApplet(api: GeoGebraApi | null, el: HTMLDivElement | null, tab: TabConfig) {
  if (!api || !el) return;
  const w = Math.max(el.clientWidth, 400);
  const h = Math.max(el.clientHeight, 400);
  api.setSize?.(w, h);
  api.setWidth?.(w);
  api.setHeight?.(h);
  if (tab.equalAxis) applyEqualAxis(api, w, h);
  api.refreshViews?.();
  window.dispatchEvent(new Event('resize'));
}

function applyEqualAxis(api: GeoGebraApi, width: number, height: number) {
  if (!api.setCoordSystem || width <= 0 || height <= 0) return;
  const ratio = width / height;
  const yRadius = 6;
  const xRadius = yRadius * ratio;
  api.setCoordSystem(-xRadius, xRadius, -yRadius, yRadius);
}

function setGeoGebraPerspective(api: GeoGebraApi, perspective: string) {
  try {
    api.setPerspective?.(perspective);
    return;
  } catch {
    // GeoGebra Classic web runtimes can differ; "B" is the Probability view code.
  }
  if (perspective === '6') {
    try {
      api.setPerspective?.('B');
    } catch {
      api.evalCommand?.('SetPerspective("6")');
    }
  }
}

function downloadDataUrl(url: string, filename: string) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
