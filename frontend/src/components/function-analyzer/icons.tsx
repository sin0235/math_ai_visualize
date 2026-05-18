import type { CSSProperties } from 'react';

export type IconName = 'wave' | 'camera' | 'graph' | 'derivative' | 'points' | 'asymptote' | 'hint' | 'attach' | 'upload' | 'chevron' | 'trend' | 'target' | 'triangleUp' | 'triangleDown' | 'magnify';

export function SvgIcon({ name }: { name: IconName }) {
  if (name === 'magnify') return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' } as CSSProperties}><circle cx="11" cy="11" r="7" /><path d="M9 11h4M11 9v4" /><path d="m20 20-4.35-4.35" /></svg>;
  if (name === 'camera') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h4l2-3h4l2 3h4v11H4z" /><circle cx="12" cy="13" r="4" /></svg>;
  if (name === 'attach') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>;
  if (name === 'hint') return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' } as CSSProperties}><circle cx="12" cy="12" r="9.5" /><path d="M12 11v5" /><circle cx="12" cy="7.5" r="0.5" fill="currentColor" stroke="none" /></svg>;
  if (name === 'graph') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19V5" /><path d="M4 19h16" /><path d="M6 15c3-8 6 8 12-6" /></svg>;
  if (name === 'derivative') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 18c4-1 4-11 8-12" /><path d="M9 12h8" /><path d="M15 8l4 4-4 4" /></svg>;
  if (name === 'points') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="7" cy="16" r="2" /><circle cx="12" cy="8" r="2" /><circle cx="17" cy="16" r="2" /><path d="M7 16l5-8 5 8" /></svg>;
  if (name === 'asymptote') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 18c4-10 12-10 16 0" /><path d="M4 6h16" strokeDasharray="3 3" /></svg>;
  if (name === 'upload') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M5 16v3h14v-3" /></svg>;
  if (name === 'chevron') return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>;
  if (name === 'trend') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 17l6-6 4 4 6-8" /><path d="M15 7h5v5" /></svg>;
  if (name === 'target') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></svg>;
  if (name === 'triangleUp') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M12 5 20 19H4Z" /></svg>;
  if (name === 'triangleDown') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M4 5h16l-8 14Z" /></svg>;
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
}
