import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { MathScene, Renderer, SceneView } from '../types/scene';

declare global {
  interface Window {
    GGBApplet?: new (parameters: Record<string, unknown>, injectInto: string) => { inject: (id: string) => void };
    [key: string]: unknown;
  }
}

type Vec3 = { x: number; y: number; z: number };

interface GeoGebraViewProps {
  commands: string[];
  renderer: Extract<Renderer, 'geogebra_2d' | 'geogebra_3d'>;
  scene: MathScene;
  view: SceneView;
  onPointChange?: (name: string, point: Vec3) => void | Promise<void>;
  embedded?: boolean;
}

interface GeoGebraApi {
  evalCommand: (command: string) => boolean | void;
  reset?: () => void;
  setAxesVisible?: (xAxis: boolean, yAxis: boolean, zAxis?: boolean) => void;
  setGridVisible?: (visible: boolean) => void;
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

export function GeoGebraView({ commands, renderer, scene, view, onPointChange, embedded = false }: GeoGebraViewProps) {
  const rawId = useId();
  const appletId = `ggb-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const appName = renderer === 'geogebra_3d' ? '3d' : 'classic';
  const apiRef = useRef<GeoGebraApi | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const syncTimerRef = useRef<number | null>(null);
  const applyingCommandsRef = useRef(false);
  const commandSignature = useMemo(() => commands.join('\n'), [commands]);
  const editablePointNames = useMemo(() => new Set(scene.objects.filter((obj) => obj.type === 'point_2d' || obj.type === 'point_3d').map((obj) => obj.name)), [scene.objects]);
  const [apiReady, setApiReady] = useState(false);
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [commandErrors, setCommandErrors] = useState<string[]>([]);
  const [retryCount, setRetryCount] = useState(0);
  const [selectedObject, setSelectedObject] = useState<string | null>(null);
  const [updateCount, setUpdateCount] = useState(0);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
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
          perspective: renderer === 'geogebra_2d' ? 'G' : undefined,
          appletOnLoad: (api: GeoGebraApi) => {
            if (cancelled) return;
            apiRef.current = api;
            api.setErrorDialogsActive?.(false);
            if (renderer === 'geogebra_2d') api.setPerspective?.('G');
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
        if (cancelled) return;
        setStatus('error');
        setErrorMessage(caught instanceof Error ? caught.message : 'Không tải được GeoGebra API.');
      });

    return () => {
      cancelled = true;
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
  }, [appletId, appName, retryCount]);

  useEffect(() => {
    if (!apiReady || !apiRef.current) return;
    const api = apiRef.current;
    applyingCommandsRef.current = true;
    const failures = applyCommands(api, commands, view, scene, renderer === 'geogebra_3d');
    requestAnimationFrame(() => resizeAppletToContainer(api, containerRef.current));
    window.setTimeout(() => {
      applyingCommandsRef.current = false;
    }, 0);
    setCommandErrors(failures);
    setStatus(failures.length > 0 ? 'error' : 'ready');
  }, [apiReady, commandSignature, commands, renderer, scene, view.show_axes, view.show_grid]);

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
      const current = scene.objects.find((obj) => (obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name);
      if (!current) return;
      const x = api.getXcoord(name);
      const y = api.getYcoord(name);
      const z = current.type === 'point_3d' ? api.getZcoord?.(name) ?? current.z : 0;
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
          <p>{errorMessage || 'Một số lệnh GeoGebra không chạy được. Hãy kiểm tra mạng/CDN hoặc thử renderer Three.js nếu phù hợp.'}</p>
          {commandErrors.length > 0 && (
            <details>
              <summary>Lệnh lỗi</summary>
              <ul>{commandErrors.map((error) => <li key={error}>{error}</li>)}</ul>
            </details>
          )}
          <button type="button" className="secondary-button" onClick={() => setRetryCount((count) => count + 1)}>Thử tải lại</button>
        </div>
      )}
      <div ref={containerRef} id={appletId} className="geogebra-view" />
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

function applyCommands(api: GeoGebraApi, commands: string[], view: SceneView, scene: MathScene, is3d: boolean) {
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
      fit2dView(api, scene);
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
  return /^\s*(Set(Color|Caption|Filling|LineStyle|LineThickness|PointSize|VisibleInView|LabelMode)|ShowLabel)\s*\(/i.test(command);
}

function fit2dView(api: GeoGebraApi, scene: MathScene) {
  if (!api.setCoordSystem) return;
  
  const min = { x: Infinity, y: Infinity };
  const max = { x: -Infinity, y: -Infinity };
  let hasGeometry = false;

  // 1. Points
  scene.objects.forEach(obj => {
    if (obj.type === 'point_2d') {
      min.x = Math.min(min.x, obj.x);
      max.x = Math.max(max.x, obj.x);
      min.y = Math.min(min.y, obj.y);
      max.y = Math.max(max.y, obj.y);
      hasGeometry = true;
    } else if (obj.type === 'circle_2d') {
      const center = scene.objects.find(o => o.type === 'point_2d' && o.name === obj.center) as any;
      if (center && obj.radius != null) {
        min.x = Math.min(min.x, center.x - obj.radius);
        max.x = Math.max(max.x, center.x + obj.radius);
        min.y = Math.min(min.y, center.y - obj.radius);
        max.y = Math.max(max.y, center.y + obj.radius);
        hasGeometry = true;
      }
    }
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
