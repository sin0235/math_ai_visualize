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
  const [importState, setImportState] = useState('');
  const [stateMessage, setStateMessage] = useState<string | null>(null);

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
          appletOnLoad: (api: GeoGebraApi) => {
            if (cancelled) return;
            apiRef.current = api;
            api.setErrorDialogsActive?.(false);
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
      setApiReady(false);
    };
  }, [appletId, appName, retryCount]);

  useEffect(() => {
    if (!apiReady || !apiRef.current) return;
    const api = apiRef.current;
    applyingCommandsRef.current = true;
    const failures = applyCommands(api, commands, view, scene, renderer === 'geogebra_3d');
    window.setTimeout(() => {
      applyingCommandsRef.current = false;
    }, 0);
    setCommandErrors(failures);
    setStatus(failures.length > 0 ? 'error' : 'ready');
    setStateMessage(null);
  }, [apiReady, commandSignature, commands, renderer, scene, view.show_axes, view.show_grid]);

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

  function exportState() {
    const api = apiRef.current;
    if (!api?.getBase64) {
      setStateMessage('GeoGebra runtime hiện không hỗ trợ export state.');
      return;
    }
    api.getBase64((base64) => {
      navigator.clipboard?.writeText(base64).then(
        () => setStateMessage('Đã sao chép state GeoGebra vào clipboard.'),
        () => {
          setImportState(base64);
          setStateMessage('Không ghi được clipboard; state đã được đưa vào ô nhập bên dưới.');
        },
      );
    });
  }

  function importGeoGebraState() {
    const api = apiRef.current;
    const value = importState.trim();
    if (!value) {
      setStateMessage('Hãy dán state GeoGebra base64 trước khi nhập.');
      return;
    }
    if (!api?.setBase64) {
      setStateMessage('GeoGebra runtime hiện không hỗ trợ import state.');
      return;
    }
    try {
      api.setBase64(value);
      setStatus('ready');
      setStateMessage('Đã nhập state GeoGebra. Render đề mới sẽ ghi đè state này.');
    } catch (caught) {
      setStateMessage(caught instanceof Error ? caught.message : 'Không nhập được state GeoGebra.');
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
      <div className="geogebra-tools">
        <div className="geogebra-status">
          {selectedObject ? <span>Đối tượng đã chọn: <strong>{selectedObject}</strong></span> : <span>Click vào đối tượng GeoGebra để xem tên.</span>}
          {onPointChange && <span>Kéo điểm trong GeoGebra để cập nhật scene.</span>}
          {updateCount > 0 && <span>Đã cập nhật trong GeoGebra: {updateCount}</span>}
          {syncMessage && <span>{syncMessage}</span>}
        </div>
        <div className="geogebra-actions">
          <button type="button" className="secondary-button" onClick={exportState} disabled={!apiReady}>Sao chép state GeoGebra</button>
        </div>
        <details className="geogebra-import">
          <summary>Nhập state GeoGebra</summary>
          <textarea value={importState} onChange={(event) => setImportState(event.target.value)} placeholder="Dán base64 GeoGebra state..." rows={3} />
          <button type="button" className="secondary-button" onClick={importGeoGebraState} disabled={!apiReady}>Nhập state</button>
        </details>
        {stateMessage && <p className="field-hint">{stateMessage}</p>}
      </div>
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
      if (result === false) failures.push(`${command}: GeoGebra không chấp nhận lệnh`);
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

function fit2dView(api: GeoGebraApi, scene: MathScene) {
  if (!api.setCoordSystem) return;
  const points = scene.objects.filter((obj) => obj.type === 'point_2d');
  if (points.length === 0) return;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const padding = Math.max(width, height) * 0.25 + 1;
  api.setCoordSystem(minX - padding, maxX + padding, minY - padding, maxY + padding);
}
