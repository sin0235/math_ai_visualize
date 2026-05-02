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

export function MetricCard({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <article className="admin-metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString('vi-VN')}{suffix}</strong>
    </article>
  );
}

export function AdminNavButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <button type="button" className={active ? 'active' : ''} onClick={onClick}>{label}</button>;
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
