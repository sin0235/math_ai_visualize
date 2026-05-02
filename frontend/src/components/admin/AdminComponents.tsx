import React from 'react';
import type { 
  AdminRenderHistoryDetail, 
  AdminRenderHistoryItem, 
  AdminSessionResponse, 
  AuditLogResponse, 
  SystemSettingResponse, 
  UserResponse 
} from '../../api/client';

export function formatHistoryDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}

export type AdminIconName = 'overview' | 'users' | 'renders' | 'models' | 'settings' | 'audit' | 'active' | 'admin' | 'warning' | 'chart' | 'back';

export function AdminIcon({ name }: { name: AdminIconName }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg className="admin-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      {name === 'overview' && <><rect {...common} x="3" y="3" width="7" height="7" rx="1" /><rect {...common} x="14" y="3" width="7" height="7" rx="1" /><rect {...common} x="3" y="14" width="7" height="7" rx="1" /><rect {...common} x="14" y="14" width="7" height="7" rx="1" /></>}
      {name === 'users' && <><path {...common} d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle {...common} cx="9" cy="7" r="4" /><path {...common} d="M22 21v-2a4 4 0 0 0-3-3.87" /><path {...common} d="M16 3.13a4 4 0 0 1 0 7.75" /></>}
      {name === 'renders' && <><path {...common} d="M4 4h16v12H4z" /><path {...common} d="M8 20h8" /><path {...common} d="M12 16v4" /><path {...common} d="m9 10 2 2 4-5" /></>}
      {name === 'models' && <><path {...common} d="M12 2v4" /><path {...common} d="M12 18v4" /><path {...common} d="M4.93 4.93l2.83 2.83" /><path {...common} d="m16.24 16.24 2.83 2.83" /><path {...common} d="M2 12h4" /><path {...common} d="M18 12h4" /><circle {...common} cx="12" cy="12" r="4" /></>}
      {name === 'settings' && <><path {...common} d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" /><path {...common} d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6 1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.14.31.23.65.25 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></>}
      {name === 'audit' && <><path {...common} d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path {...common} d="M14 2v6h6" /><path {...common} d="M9 15l2 2 4-5" /></>}
      {name === 'active' && <><path {...common} d="M22 12h-4l-3 8-6-16-3 8H2" /></>}
      {name === 'admin' && <><path {...common} d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path {...common} d="m9 12 2 2 4-5" /></>}
      {name === 'warning' && <><path {...common} d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><path {...common} d="M12 9v4" /><path {...common} d="M12 17h.01" /></>}
      {name === 'chart' && <><path {...common} d="M3 3v18h18" /><rect {...common} x="7" y="12" width="3" height="5" /><rect {...common} x="12" y="8" width="3" height="9" /><rect {...common} x="17" y="5" width="3" height="12" /></>}
      {name === 'back' && <><path {...common} d="M19 12H5" /><path {...common} d="m12 19-7-7 7-7" /></>}
    </svg>
  );
}

export function MetricCard({ label, value, suffix = '', variant = 'default', icon }: { label: string; value: number; suffix?: string; variant?: 'default' | 'primary' | 'success' | 'warning' | 'info'; icon?: AdminIconName }) {
  const className = variant !== 'default' ? `admin-metric-card metric-${variant}` : 'admin-metric-card';
  return (
    <article className={className}>
      <div className="admin-metric-label">{icon && <AdminIcon name={icon} />}<span>{label}</span></div>
      <strong>{value.toLocaleString('vi-VN')}{suffix}</strong>
    </article>
  );
}

export function AdminNavButton({ active, label, icon, onClick }: { active: boolean; label: string; icon: AdminIconName; onClick: () => void }) {
  return <button type="button" className={active ? 'active' : ''} onClick={onClick}><AdminIcon name={icon} /><span>{label}</span></button>;
}

export function AdminDetails({ title, value }: { title: string; value: unknown }) {
  return <details className="admin-details"><summary>{title}</summary><AdminJsonBlock value={value} /></details>;
}

export function AdminJsonBlock({ value }: { value: unknown }) {
  return <pre className="admin-json-block">{JSON.stringify(value ?? null, null, 2)}</pre>;
}

export function hasObjectKeys(value: Record<string, unknown>) {
  return Object.keys(value).length > 0;
}
