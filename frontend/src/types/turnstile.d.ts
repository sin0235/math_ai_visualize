export {};

interface TurnstileRenderOptions {
  sitekey: string;
  theme?: 'light' | 'dark' | 'auto';
  callback?: (token: string) => void;
  'error-callback'?: () => void;
  'expired-callback'?: () => void;
}

declare global {
  interface Window {
    turnstile?: {
      render(container: string | HTMLElement, options: TurnstileRenderOptions): string;
      reset(widgetId?: string): void;
      remove(widgetId?: string): void;
      getResponse(widgetId?: string): string | undefined;
    };
  }
}
