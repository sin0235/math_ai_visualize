import { useEffect, useId, useRef } from 'react';

declare global {
  interface Window {
    GGBApplet?: new (parameters: Record<string, unknown>, injectInto: string) => { inject: (id: string) => void };
  }
}

interface GeoGebraViewProps {
  commands: string[];
  embedded?: boolean;
}

function loadGeoGebraScript(): Promise<void> {
  const existing = document.querySelector<HTMLScriptElement>('script[data-geogebra]');
  if (existing) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://www.geogebra.org/apps/deployggb.js';
    script.async = true;
    script.dataset.geogebra = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Không tải được GeoGebra API.'));
    document.body.appendChild(script);
  });
}

export function GeoGebraView({ commands, embedded = false }: GeoGebraViewProps) {
  const rawId = useId();
  const appletId = `ggb-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const apiRef = useRef<unknown>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    loadGeoGebraScript().then(() => {
      if (cancelled || !window.GGBApplet) return;

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
          apiRef.current = api;
          commands.forEach((command) => api.evalCommand(command));
        },
      };

      const applet = new window.GGBApplet(parameters, true as unknown as string);
      applet.inject(appletId);
    });

    return () => {
      cancelled = true;
      apiRef.current = null;
    };
  }, [appletId, commands]);

  const content = <div ref={containerRef} id={appletId} className="geogebra-view" />;

  if (embedded) return content;

  return (
    <div className="viewer-card">
      <div className="viewer-header">GeoGebra Renderer</div>
      {content}
    </div>
  );
}
