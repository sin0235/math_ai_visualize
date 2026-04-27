import { useEffect, useId, useRef } from 'react';

declare global {
  interface Window {
    GGBApplet?: new (parameters: Record<string, unknown>, injectInto: string) => { inject: (id: string) => void };
  }
}

interface GeoGebraViewProps {
  commands: string[];
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

export function GeoGebraView({ commands }: GeoGebraViewProps) {
  const rawId = useId();
  const appletId = `ggb-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const apiRef = useRef<unknown>(null);

  useEffect(() => {
    let cancelled = false;

    loadGeoGebraScript().then(() => {
      if (cancelled || !window.GGBApplet) return;

      const parameters = {
        appName: 'classic',
        width: 720,
        height: 520,
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

  return (
    <div className="viewer-card">
      <div className="viewer-header">GeoGebra Renderer</div>
      <div id={appletId} className="geogebra-view" />
    </div>
  );
}
