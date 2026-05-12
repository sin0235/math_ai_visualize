import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

type LabMode = 'graphing' | 'geometry' | '3d' | 'probability';

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
  icon: ReactNode;
  appName: string;
  perspective?: string;
  presets: Preset[];
}

interface Preset {
  label: string;
  commands: string[];
  desc?: string;
}

/* SVG icon helpers */
const svgProps = { viewBox: '0 0 24 24', width: 18, height: 18, fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const };
const GraphIcon = <svg {...svgProps}><polyline points="4 18 8 10 12 14 16 6 20 12" /><path d="M4 20h16" /><path d="M4 4v16" /></svg>;
const GeometryIcon = <svg {...svgProps}><polygon points="12 3 4 20 20 20" /><circle cx="12" cy="14" r="4" /></svg>;
const ThreeDIcon = <svg {...svgProps}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" /><path d="M12 12l8-4.5" /><path d="M12 12v9" /><path d="M12 12L4 7.5" /></svg>;
const ProbabilityIcon = <svg {...svgProps}><path d="M4 20c0-8 4-16 8-16s8 8 8 16" /><path d="M4 20h16" /><path d="M12 4v16" /></svg>;
const LabIcon = <svg {...svgProps}><path d="M9 3h6v5l4 9H5l4-9V3z" /><path d="M9 3h6" /><circle cx="10" cy="15" r="1" /><circle cx="14" cy="13" r="1" /></svg>;

const TABS: TabConfig[] = [
  {
    key: 'graphing',
    label: 'Graphing Calculator',
    desc: 'Đồ thị hàm số 2D, phương trình, bất phương trình',
    icon: GraphIcon,
    appName: 'graphing',
    presets: [
      { label: 'Parabol y=x²', commands: ['f(x)=x^2'], desc: 'Đồ thị hàm bậc hai' },
      { label: 'Đường tròn', commands: ['x^2+y^2=9'], desc: 'x²+y²=9' },
      { label: 'Elip', commands: ['x^2/4+y^2/9=1'], desc: 'Elip chuẩn' },
      { label: 'Hyperbol', commands: ['x^2/4-y^2/9=1'], desc: 'Hyperbol chuẩn' },
      { label: 'Sin(x)', commands: ['f(x)=sin(x)'], desc: 'Hàm lượng giác' },
      { label: 'Bất PT y≥x²', commands: ['y>=x^2'], desc: 'Miền nghiệm' },
      { label: 'Hàm bậc 3', commands: ['f(x)=x^3-3x+1'], desc: 'Cực trị, uốn' },
      { label: 'Đường thẳng', commands: ['y=2x+1', 'y=-x+3'], desc: 'Hai đường cắt nhau' },
    ],
  },
  {
    key: 'geometry',
    label: 'Geometry',
    desc: 'Hình học phẳng: tam giác, đường tròn, đa giác, góc',
    icon: GeometryIcon,
    appName: 'geometry',
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
    icon: ThreeDIcon,
    appName: '3d',
    presets: [
      { label: 'Mặt phẳng', commands: ['a:x+y+z=3'], desc: 'x+y+z=3' },
      { label: 'Mặt cầu', commands: ['x^2+y^2+z^2=9'], desc: 'R=3' },
      { label: 'Parabol xoay', commands: ['Surface(u*cos(v),u*sin(v),u^2,u,0,2,v,0,2*pi)'], desc: 'z=x²+y²' },
      { label: 'Hình nón', commands: ['Cone((0,0,3),(0,0,0),2)'], desc: 'Đỉnh (0,0,3), r=2' },
      { label: 'Hình trụ', commands: ['Cylinder((0,0,0),(0,0,3),1.5)'], desc: 'h=3, r=1.5' },
      { label: 'Tứ diện', commands: ['A=(0,0,0)', 'B=(3,0,0)', 'C=(1.5,2.6,0)', 'D=(1.5,0.87,2.45)', 'Polygon(A,B,C)', 'Polygon(A,B,D)', 'Polygon(B,C,D)', 'Polygon(A,C,D)'] },
      { label: 'Lăng trụ', commands: ['A=(0,0,0)', 'B=(3,0,0)', 'C=(1.5,2.6,0)', 'Prism(A,B,C,4)'] },
      { label: 'Mặt yên ngựa', commands: ['Surface(u,v,u^2-v^2,u,-2,2,v,-2,2)'], desc: 'z=x²-y²' },
    ],
  },
  {
    key: 'probability',
    label: 'Probability',
    desc: 'Phân phối chuẩn, nhị thức, Poisson, tính xác suất',
    icon: ProbabilityIcon,
    appName: 'classic',
    perspective: 'P',
    presets: [
      { label: 'Normal(0,1)', commands: ['Normal(0,1,1)'], desc: 'Phân phối chuẩn tắc' },
      { label: 'Normal(5,2)', commands: ['Normal(5,2,7)'], desc: 'μ=5, σ=2' },
      { label: 'Binomial(10,0.5)', commands: ['BinomialDist(10,0.5,3,true)'], desc: 'n=10, p=0.5' },
      { label: 'Poisson(4)', commands: ['Poisson(4,3,true)'], desc: 'λ=4' },
      { label: 'P(X≤2)', commands: ['Normal(0,1,2)'], desc: 'CDF chuẩn tắc tại x=2' },
    ],
  },
];

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
        const w = Math.max(containerRef.current?.clientWidth ?? 800, 400);
        const h = Math.max(containerRef.current?.clientHeight ?? 600, 400);

        const params: Record<string, unknown> = {
          appName: tab.appName,
          width: w,
          height: h,
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
            if (tab.perspective) api.setPerspective?.(tab.perspective);
            requestAnimationFrame(() => resizeToContainer(api, containerRef.current));
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
  const workspaceRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (status !== 'ready') return;
    const workspace = workspaceRef.current;
    const container = containerRef.current;
    if (!workspace || !container) return;
    let frame = 0;
    const doResize = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => resizeToContainer(apiRef.current, container));
    };
    const obs = new ResizeObserver(doResize);
    obs.observe(workspace);
    return () => { obs.disconnect(); if (frame) cancelAnimationFrame(frame); };
  }, [status]);

  /* ---------- resize on sidebar toggle ---------- */
  useEffect(() => {
    if (status !== 'ready') return;
    // Multiple delays to catch CSS grid reflow timing
    const timers = [50, 150, 350].map((ms) =>
      setTimeout(() => resizeToContainer(apiRef.current, containerRef.current), ms),
    );
    return () => timers.forEach(clearTimeout);
  }, [sidebarOpen, status]);

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
          <span className="gglab-logo" aria-hidden="true">{LabIcon}</span>
          <div>
            <h2>GeoGebra Lab</h2>
            <span className="gglab-subtitle">Phòng thí nghiệm toán học tương tác</span>
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
              <span className="gglab-tab-icon">{t.icon}</span>
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
            {sidebarOpen ? '‹' : '›'}
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
                  <button type="button" className="gglab-cmd-run" onClick={() => runCommand(cmdText)} disabled={status !== 'ready' || !cmdText.trim()}><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" stroke="none" aria-hidden="true"><polygon points="6 3 20 12 6 21" /></svg></button>
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
                <strong className="gglab-section-title">Mẫu nhanh — {tab.label}</strong>
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
                  <button type="button" onClick={handleUndo} disabled={status !== 'ready'} title="Hoàn tác"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 7v6h6" /><path d="M3 13a9 9 0 0 1 15.36-6.36" /></svg> Undo</button>
                  <button type="button" onClick={handleRedo} disabled={status !== 'ready'} title="Làm lại"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 7v6h-6" /><path d="M21 13a9 9 0 0 0-15.36-6.36" /></svg> Redo</button>
                  <button type="button" onClick={clearAll} disabled={status !== 'ready'} title="Xoá tất cả"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v5" /><path d="M14 11v5" /></svg> Xoá</button>
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
                  <button type="button" onClick={saveState} disabled={status !== 'ready'}><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" /><polyline points="17 21 17 13 7 13 7 21" /><polyline points="7 3 7 8 15 8" /></svg> Lưu</button>
                </div>
                {Object.keys(savedStates).length > 0 && (
                  <div className="gglab-saved-list">
                    {Object.entries(savedStates).map(([key, b64]) => (
                      <div key={key} className="gglab-saved-item">
                        <button type="button" onClick={() => loadState(b64)} title="Tải lại trạng thái"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{marginRight:4,verticalAlign:'middle'}}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>{key}</button>
                        <button type="button" className="gglab-saved-delete" onClick={() => deleteState(key)} aria-label="Xoá">×</button>
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
          <div className="gglab-mode-badge"><span className="gglab-mode-badge-icon">{tab.icon}</span> {tab.label}</div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Utils                                                             */
/* ------------------------------------------------------------------ */

function resizeToContainer(api: GeoGebraApi | null, el: HTMLDivElement | null) {
  if (!api || !el) return;
  const w = Math.max(el.clientWidth, 400);
  const h = Math.max(el.clientHeight, 400);
  api.setSize?.(w, h);
  api.setWidth?.(w);
  api.setHeight?.(h);
}

function downloadDataUrl(url: string, filename: string) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
