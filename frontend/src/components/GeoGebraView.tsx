import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { MathScene, Renderer, SceneView } from '../types/scene';

declare global {
  interface Window {
    GGBApplet?: new (parameters: Record<string, unknown>, injectInto: string) => { inject: (id: string) => void };
    [key: string]: unknown;
  }
}

type Vec3 = { x: number; y: number; z: number };
type GraphViewBounds = { left: number; right: number; bottom: number; top: number };

/** Lightweight point list from RenderProjectionV3 — preferred over full MathScene. */
export type GeoGebraPoint = {
  name: string;
  x: number;
  y: number;
  z?: number;
};

interface GeoGebraViewProps {
  commands: string[];
  renderer: Extract<Renderer, 'geogebra_2d' | 'geogebra_3d'>;
  /** Optional full scene (function analyzer). Prefer `points` for Scene v3 workspace. */
  scene?: MathScene;
  /** Projection points for Scene v3 / GeoGebra without legacy MathScene bridge. */
  points?: GeoGebraPoint[];
  view: SceneView;
  viewBounds?: GraphViewBounds;
  objectVisibility?: Readonly<Record<string, boolean>>;
  onPointChange?: (name: string, point: Vec3) => void | Promise<void>;
  onStatusChange?: (status: LoadStatus, detail?: string) => void;
  embedded?: boolean;
}

interface GeoGebraApi {
  evalCommand: (command: string) => boolean | void;
  reset?: () => void;
  setAxesVisible?: (xAxis: boolean, yAxis: boolean, zAxis?: boolean) => void;
  setGridVisible?: (visible: boolean) => void;
  setVisible?: (name: string, visible: boolean) => void;
  setErrorDialogsActive?: (active: boolean) => void;
  getBase64?: (callback: (base64: string) => void) => void;
  setBase64?: (base64: string) => void;
  getXcoord?: (name: string) => number;
  getYcoord?: (name: string) => number;
  getZcoord?: (name: string) => number;
  setCoordSystem?: (xmin: number, xmax: number, ymin: number, ymax: number) => void;
  setPerspective?: (perspective: string) => void;
  setWidth?: (width: number) => void;
  setHeight?: (height: number) => void;
  setSize?: (width: number, height: number) => void;
  registerObjectClickListener?: (callbackName: string) => void;
  unregisterObjectClickListener?: (callbackName: string) => void;
  registerUpdateListener?: (callbackName: string) => void;
  unregisterUpdateListener?: (callbackName: string) => void;
}

type LoadStatus = 'loading' | 'ready' | 'error';

let geogebraLoadPromise: Promise<void> | null = null;

function loadGeoGebraScript(): Promise<void> {
  if (window.GGBApplet) return Promise.resolve();
  if (geogebraLoadPromise) return geogebraLoadPromise;

  geogebraLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-geogebra]');
    const script = existing ?? document.createElement('script');

    const cleanup = () => {
      script.removeEventListener('load', handleLoad);
      script.removeEventListener('error', handleError);
    };
    const handleLoad = () => {
      cleanup();
      if (window.GGBApplet) {
        resolve();
      } else {
        geogebraLoadPromise = null;
        reject(new Error('GeoGebra API đã tải nhưng không khởi tạo được applet.'));
      }
    };
    const handleError = () => {
      cleanup();
      script.remove();
      geogebraLoadPromise = null;
      reject(new Error('Không tải được GeoGebra API.'));
    };

    script.addEventListener('load', handleLoad);
    script.addEventListener('error', handleError);

    if (!existing) {
      script.src = 'https://www.geogebra.org/apps/deployggb.js';
      script.async = true;
      script.dataset.geogebra = 'true';
      document.body.appendChild(script);
    }
  });

  return geogebraLoadPromise;
}

function resetGeoGebraLoader() {
  if (window.GGBApplet) return;
  document.querySelector<HTMLScriptElement>('script[data-geogebra]')?.remove();
  geogebraLoadPromise = null;
}

export function GeoGebraView({ commands, renderer, scene, points, view, viewBounds, objectVisibility, onPointChange, onStatusChange, embedded = false }: GeoGebraViewProps) {
  const rawId = useId();
  const appletId = `ggb-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const appName = renderer === 'geogebra_3d' ? '3d' : 'classic';
  const apiRef = useRef<GeoGebraApi | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const syncTimerRef = useRef<number | null>(null);
  const applyingCommandsRef = useRef(false);
  const commandSignature = useMemo(() => commands.join('\n'), [commands]);
  const geometryPoints = useMemo(() => resolveGeometryPoints(points, scene), [points, scene]);
  const editablePointNames = useMemo(() => new Set(geometryPoints.map((point) => point.name)), [geometryPoints]);
  const [apiReady, setApiReady] = useState(false);
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [commandErrors, setCommandErrors] = useState<string[]>([]);
  const [retryCount, setRetryCount] = useState(0);
  const [selectedObject, setSelectedObject] = useState<string | null>(null);
  const [updateCount, setUpdateCount] = useState(0);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [showAlgebraPanel, setShowAlgebraPanel] = useState(false);

  useEffect(() => {
    onStatusChange?.(status, status === 'error' ? (errorMessage ?? 'GeoGebra command failed') : undefined);
  }, [errorMessage, onStatusChange, status]);

  useEffect(() => {
    let cancelled = false;
    const loadTimeout = window.setTimeout(() => {
      if (cancelled) return;
      resetGeoGebraLoader();
      setStatus('error');
      setErrorMessage('GeoGebra vượt thời gian tải hoặc khởi tạo.');
    }, 12_000);
    const clickCallbackName = `${appletId}Click`;
    const updateCallbackName = `${appletId}Update`;
    setStatus('loading');
    setErrorMessage(null);
    setCommandErrors([]);
    setSelectedObject(null);
    setApiReady(false);

    loadGeoGebraScript()
      .then(() => {
        if (cancelled) return;
        if (!window.GGBApplet) {
          throw new Error('GeoGebra API đã tải nhưng không khởi tạo được applet.');
        }

        const containerWidth = Math.max(containerRef.current?.clientWidth ?? 720, 320);
        const containerHeight = Math.max(containerRef.current?.clientHeight ?? 600, 420);

        const parameters = {
          appName,
          width: containerWidth,
          height: containerHeight,
          showToolBar: false,
          showAlgebraInput: false,
          showMenuBar: false,
          showResetIcon: false,
          enableShiftDragZoom: true,
          perspective: renderer === 'geogebra_2d' ? (showAlgebraPanel ? 'AG' : 'G') : undefined,
          appletOnLoad: (api: GeoGebraApi) => {
            if (cancelled) return;
            window.clearTimeout(loadTimeout);
            apiRef.current = api;
            api.setErrorDialogsActive?.(false);
            if (renderer === 'geogebra_2d') api.setPerspective?.(showAlgebraPanel ? 'AG' : 'G');
            requestAnimationFrame(() => resizeAppletToContainer(api, containerRef.current));
            window[clickCallbackName] = (name: string) => setSelectedObject(name);
            window[updateCallbackName] = (name?: string) => {
              setUpdateCount((count) => count + 1);
              if (typeof name === 'string') schedulePointSync(name);
            };
            api.registerObjectClickListener?.(clickCallbackName);
            api.registerUpdateListener?.(updateCallbackName);
            setApiReady(true);
          },
        };

        const applet = new window.GGBApplet(parameters, true as unknown as string);
        applet.inject(appletId);
      })
      .catch((caught) => {
        window.clearTimeout(loadTimeout);
        if (cancelled) return;
        setStatus('error');
        setErrorMessage(caught instanceof Error ? caught.message : 'Không tải được GeoGebra API.');
      });

    return () => {
      cancelled = true;
      window.clearTimeout(loadTimeout);
      const api = apiRef.current;
      api?.unregisterObjectClickListener?.(clickCallbackName);
      api?.unregisterUpdateListener?.(updateCallbackName);
      delete window[clickCallbackName];
      delete window[updateCallbackName];
      if (syncTimerRef.current !== null) window.clearTimeout(syncTimerRef.current);
      apiRef.current = null;
      const host = containerRef.current;
      if (host) host.innerHTML = '';
      setApiReady(false);
    };
  }, [appletId, appName, retryCount, showAlgebraPanel, renderer]);

  useEffect(() => {
    if (!apiReady || !apiRef.current) return;
    const api = apiRef.current;
    applyingCommandsRef.current = true;
    const failures = applyCommands(api, commands, view, geometryPoints, scene, renderer === 'geogebra_3d', viewBounds);
    requestAnimationFrame(() => resizeAppletToContainer(api, containerRef.current));
    window.setTimeout(() => {
      applyingCommandsRef.current = false;
    }, 0);
    setCommandErrors(failures);
    setStatus(failures.length > 0 ? 'error' : 'ready');
  }, [apiReady, commandSignature, commands, geometryPoints, renderer, scene, view.show_axes, view.show_grid, viewBounds?.bottom, viewBounds?.left, viewBounds?.right, viewBounds?.top]);

  useEffect(() => {
    const api = apiRef.current;
    if (!apiReady || !api?.setVisible || !objectVisibility) return;
    Object.entries(objectVisibility).forEach(([name, visible]) => api.setVisible?.(name, visible));
  }, [apiReady, objectVisibility]);

  useEffect(() => {
    if (!apiReady || !apiRef.current || !containerRef.current || typeof ResizeObserver === 'undefined') return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => resizeAppletToContainer(apiRef.current, containerRef.current));
    });
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [apiReady]);

  function schedulePointSync(name: string) {
    if (!onPointChange || applyingCommandsRef.current || !editablePointNames.has(name)) return;
    if (syncTimerRef.current !== null) window.clearTimeout(syncTimerRef.current);
    syncTimerRef.current = window.setTimeout(() => {
      syncTimerRef.current = null;
      syncPoint(name);
    }, 350);
  }

  function syncPoint(name: string) {
    const api = apiRef.current;
    if (!api?.getXcoord || !api.getYcoord) {
      setSyncMessage('GeoGebra runtime không hỗ trợ đọc tọa độ điểm.');
      return;
    }
    try {
      const current = geometryPoints.find((point) => point.name === name);
      if (!current) return;
      const x = api.getXcoord(name);
      const y = api.getYcoord(name);
      const z = current.z != null ? api.getZcoord?.(name) ?? current.z : 0;
      if (![x, y, z].every(Number.isFinite)) return;
      onPointChange?.(name, { x, y, z });
      setSyncMessage(`Đã đồng bộ điểm ${name}.`);
    } catch (caught) {
      setSyncMessage(caught instanceof Error ? caught.message : `Không đọc được tọa độ điểm ${name}.`);
    }
  }

  const content = (
    <>
      {status === 'loading' && <div className="info-box">Đang tải GeoGebra...</div>}
      {status === 'error' && (
        <div className="error-box">
          <strong>GeoGebra chưa sẵn sàng.</strong>
          <p>{errorMessage || 'GeoGebra không chạy được lệnh dựng đồ thị. Thử tải lại hoặc chọn SVG.'}</p>
          {commandErrors.length > 0 && (
            <details>
              <summary>Lệnh lỗi</summary>
              <ul>{commandErrors.map((error) => <li key={error}>{error}</li>)}</ul>
            </details>
          )}
          <button type="button" className="secondary-button" onClick={() => {
            resetGeoGebraLoader();
            setRetryCount((count) => count + 1);
          }}>Thử tải lại</button>
        </div>
      )}
      <div className="geogebra-shell">
        <button
          type="button"
          className={`geogebra-panel-toggle ${showAlgebraPanel ? 'is-open' : ''}`}
          onClick={() => setShowAlgebraPanel((current) => !current)}
          aria-pressed={showAlgebraPanel}
          aria-label={showAlgebraPanel ? 'Thu bảng công thức GeoGebra' : 'Bung bảng công thức GeoGebra'}
          title={showAlgebraPanel ? 'Thu bảng công thức GeoGebra' : 'Bung bảng công thức GeoGebra'}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            {showAlgebraPanel ? (
              <path d="M14.5 6.5 9 12l5.5 5.5M20 4v16M4 5.5h5M4 12h3.5M4 18.5h5" />
            ) : (
              <path d="M9.5 6.5 15 12l-5.5 5.5M4 4v16M20 5.5h-5M20 12h-3.5M20 18.5h-5" />
            )}
          </svg>
        </button>
        <div ref={containerRef} id={appletId} className="geogebra-view" />
      </div>
      {syncMessage && (
        <div className="geogebra-tools">
          <div className="geogebra-status">
            <span>{syncMessage}</span>
          </div>
        </div>
      )}
    </>
  );

  if (embedded) return content;

  return (
    <div className="viewer-card">
      <div className="viewer-header">GeoGebra Renderer</div>
      {content}
    </div>
  );
}

function resizeAppletToContainer(api: GeoGebraApi | null, container: HTMLDivElement | null) {
  if (!api || !container) return;
  const width = Math.max(container.clientWidth, 320);
  const height = Math.max(container.clientHeight, 420);
  api.setSize?.(width, height);
  api.setWidth?.(width);
  api.setHeight?.(height);
}

function resolveGeometryPoints(points: GeoGebraPoint[] | undefined, scene: MathScene | undefined): GeoGebraPoint[] {
  if (points?.length) return points;
  if (!scene) return [];
  return scene.objects.flatMap((obj) => {
    if (obj.type === 'point_2d') return [{ name: obj.name, x: obj.x, y: obj.y }];
    if (obj.type === 'point_3d') return [{ name: obj.name, x: obj.x, y: obj.y, z: obj.z }];
    return [];
  });
}

function applyCommands(
  api: GeoGebraApi,
  commands: string[],
  view: SceneView,
  points: GeoGebraPoint[],
  scene: MathScene | undefined,
  is3d: boolean,
  viewBounds?: GraphViewBounds,
) {
  const failures: string[] = [];
  try {
    api.reset?.();
    api.setErrorDialogsActive?.(false);
    api.setAxesVisible?.(view.show_axes, view.show_axes, is3d ? view.show_axes : undefined);
    api.setGridVisible?.(view.show_grid);
  } catch (caught) {
    const detail = caught instanceof Error ? caught.message : 'Không rõ lỗi';
    failures.push(`Cấu hình view: ${detail}`);
  }

  commands.forEach((command) => {
    try {
      const result = api.evalCommand(command);
      if (result === false && !isSideEffectCommand(command)) failures.push(`${command}: GeoGebra không chấp nhận lệnh`);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Không rõ lỗi';
      failures.push(`${command}: ${detail}`);
    }
  });

  if (!is3d) {
    try {
      fit2dView(api, points, scene, viewBounds);
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : 'Không rõ lỗi';
      failures.push(`Auto-fit view: ${detail}`);
    }
  }

  return failures;
}

function isSideEffectCommand(command: string) {
  // GeoGebra's JS API can return false for scripting commands that mutate
  // existing objects because those commands do not create a new object.
  return /^\s*(Set[A-Za-z]+|ShowLabel)\s*\(/i.test(command);
}

function fit2dView(
  api: GeoGebraApi,
  points: GeoGebraPoint[],
  scene: MathScene | undefined,
  viewBounds?: GraphViewBounds,
) {
  if (!api.setCoordSystem) return;
  if (viewBounds && [viewBounds.left, viewBounds.right, viewBounds.bottom, viewBounds.top].every(Number.isFinite)
    && viewBounds.left < viewBounds.right && viewBounds.bottom < viewBounds.top) {
    api.setCoordSystem(viewBounds.left, viewBounds.right, viewBounds.bottom, viewBounds.top);
    return;
  }

  const min = { x: Infinity, y: Infinity };
  const max = { x: -Infinity, y: -Infinity };
  let hasGeometry = false;

  points.forEach((point) => {
    min.x = Math.min(min.x, point.x);
    max.x = Math.max(max.x, point.x);
    min.y = Math.min(min.y, point.y);
    max.y = Math.max(max.y, point.y);
    hasGeometry = true;
  });

  // Circles still come from full MathScene (function analyzer path).
  scene?.objects.forEach((obj) => {
    if (obj.type !== 'circle_2d' || obj.radius == null) return;
    const centerFromPoints = points.find((point) => point.name === obj.center);
    const centerFromScene = scene.objects.find((item) => item.type === 'point_2d' && item.name === obj.center);
    const center = centerFromPoints
      ?? (centerFromScene && centerFromScene.type === 'point_2d'
        ? { name: centerFromScene.name, x: centerFromScene.x, y: centerFromScene.y }
        : null);
    if (!center) return;
    min.x = Math.min(min.x, center.x - obj.radius);
    max.x = Math.max(max.x, center.x + obj.radius);
    min.y = Math.min(min.y, center.y - obj.radius);
    max.y = Math.max(max.y, center.y + obj.radius);
    hasGeometry = true;
  });

  if (!hasGeometry) {
    api.setCoordSystem(-5, 5, -5, 5);
    return;
  }

  const width = Math.max(max.x - min.x, 1);
  const height = Math.max(max.y - min.y, 1);
  const padding = Math.max(width, height) * 0.3 + 0.5;

  api.setCoordSystem(min.x - padding, max.x + padding, min.y - padding, max.y + padding);
}
