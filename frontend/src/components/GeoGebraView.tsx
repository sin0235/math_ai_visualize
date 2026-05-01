import { useEffect, useId, useRef, useState } from 'react';

declare global {
  interface Window {
    GGBApplet?: new (parameters: Record<string, unknown>, injectInto: string) => { inject: (id: string) => void };
  }
}

interface GeoGebraViewProps {
  commands: string[];
  embedded?: boolean;
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

export function GeoGebraView({ commands, embedded = false }: GeoGebraViewProps) {
  const rawId = useId();
  const appletId = `ggb-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const apiRef = useRef<unknown>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [commandErrors, setCommandErrors] = useState<string[]>([]);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    setErrorMessage(null);
    setCommandErrors([]);

    loadGeoGebraScript()
      .then(() => {
        if (cancelled) return;
        if (!window.GGBApplet) {
          throw new Error('GeoGebra API đã tải nhưng không khởi tạo được applet.');
        }

        const containerWidth = Math.max(containerRef.current?.clientWidth ?? 720, 320);
        const containerHeight = Math.max(containerRef.current?.clientHeight ?? 600, 420);

        const parameters = {
          appName: 'classic',
          width: containerWidth,
          height: containerHeight,
          showToolBar: false,
          showAlgebraInput: false,
          showMenuBar: false,
          appletOnLoad: (api: { evalCommand: (command: string) => void; setLabelVisible: (name: string, visible: boolean) => void }) => {
            if (cancelled) return;
            apiRef.current = api;
            const failures: string[] = [];
            commands.forEach((command) => {
              try {
                api.evalCommand(command);
              } catch (caught) {
                const detail = caught instanceof Error ? caught.message : 'Không rõ lỗi';
                failures.push(`${command}: ${detail}`);
              }
            });
            setCommandErrors(failures);
            setStatus(failures.length > 0 ? 'error' : 'ready');
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
      apiRef.current = null;
    };
  }, [appletId, commands, retryCount]);

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
