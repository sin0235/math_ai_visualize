import { useState } from 'react';

import { scanProviderModels } from '../api/client';
import type { ProviderKey, RuntimeSettings, SettingsDefaults } from '../types/settings';

interface SettingsPanelProps {
  value: RuntimeSettings;
  defaults: SettingsDefaults | null;
  onChange: (next: RuntimeSettings) => void;
  onReset: () => void;
}

const providerLabels: Record<ProviderKey, string> = {
  openrouter: 'OpenRouter',
  nvidia: 'NVIDIA',
  ollama: 'Ollama / OpenAI-compatible',
};

const providerHints: Record<ProviderKey, string> = {
  openrouter: 'Cho phép nhập base URL tùy chỉnh cho OpenRouter hoặc gateway OpenAI-compatible.',
  nvidia: 'Dùng khi bạn muốn đổi endpoint NVIDIA mặc định sang proxy nội bộ hoặc gateway riêng.',
  ollama: 'Phù hợp cho Ollama cloud, local, server nội bộ hoặc endpoint OpenAI-compatible.',
};

export function SettingsPanel({ value, defaults, onChange, onReset }: SettingsPanelProps) {
  const [scanningProvider, setScanningProvider] = useState<ProviderKey | null>(null);
  const [scanErrors, setScanErrors] = useState<Partial<Record<ProviderKey, string>>>({});

  function updateProvider(provider: ProviderKey, field: 'api_key' | 'base_url' | 'model', nextValue: string) {
    onChange({
      ...value,
      [provider]: {
        ...value[provider],
        [field]: nextValue,
      },
    });
  }

  async function scanModels(provider: ProviderKey) {
    setScanningProvider(provider);
    setScanErrors((current) => ({ ...current, [provider]: undefined }));
    try {
      const models = await scanProviderModels(provider, value);
      const availableIds = new Set(models.map((model) => model.id));
      onChange({
        ...value,
        [provider]: {
          ...value[provider],
          scanned_models: models,
          model: availableIds.has(value[provider].model) ? value[provider].model : models[0]?.id ?? value[provider].model,
          last_scanned_at: new Date().toISOString(),
        },
      });
    } catch (caught) {
      setScanErrors((current) => ({
        ...current,
        [provider]: caught instanceof Error ? caught.message : 'Không thể quét model provider.',
      }));
    } finally {
      setScanningProvider(null);
    }
  }

  return (
    <section className="settings-layout">
      <div className="panel settings-hero">
        <div className="panel-title">Setting</div>
        <p className="field-hint">
          Cấu hình từ cơ bản đến nâng cao cho provider AI. 9router có trang riêng để quét và quản lý model khả dụng.
          Các giá trị này được lưu ngay trên trình duyệt và gửi theo từng lần dựng hình.
        </p>
      </div>

      <div className="settings-grid">
        {(['openrouter', 'nvidia', 'ollama'] as ProviderKey[]).map((provider) => {
          const providerDefaults = defaults?.[provider];
          return (
            <section className="panel settings-section" key={provider}>
              <div className="settings-provider-header">
                <div className="panel-title">{providerLabels[provider]}</div>
                <p className="field-hint">{providerHints[provider]}</p>
              </div>

              <label className="field-label">
                API key override
                <input
                  type="password"
                  value={value[provider].api_key}
                  onChange={(event) => updateProvider(provider, 'api_key', event.target.value)}
                  placeholder={providerDefaults?.api_key_configured ? 'Configured in backend .env' : 'Nhập API key nếu muốn override'}
                  autoComplete="off"
                />
              </label>

              <label className="field-label">
                Base URL override
                <input
                  type="url"
                  value={value[provider].base_url}
                  onChange={(event) => updateProvider(provider, 'base_url', event.target.value)}
                  placeholder={providerDefaults?.base_url || 'Backend default'}
                />
              </label>

              <label className="field-label">
                Model override
                {value[provider].scanned_models.length > 0 ? (
                  <select value={value[provider].model} onChange={(event) => updateProvider(provider, 'model', event.target.value)}>
                    <option value="">Backend default: {providerDefaults?.model || 'not set'}</option>
                    {value[provider].scanned_models.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={value[provider].model}
                    onChange={(event) => updateProvider(provider, 'model', event.target.value)}
                    placeholder={providerDefaults?.model || 'Tên model override'}
                  />
                )}
              </label>

              <button type="button" className="secondary-button" onClick={() => scanModels(provider)} disabled={scanningProvider === provider}>
                {scanningProvider === provider ? 'Đang quét...' : 'Quét model provider'}
              </button>
              <p className="field-hint">Để trống field override để backend dùng `.env`/default. Placeholder không được gửi lên backend.</p>
              {scanErrors[provider] && <div className="error-box">{scanErrors[provider]}</div>}
              {value[provider].last_scanned_at && <p className="field-hint">Lần quét gần nhất: {new Date(value[provider].last_scanned_at).toLocaleString()}</p>}
            </section>
          );
        })}
      </div>

      <section className="panel settings-section">
        <div className="panel-title">Ghi chú cấu hình</div>
        <ul className="settings-notes">
          <li>`OpenRouter` hỗ trợ nhập `base URL` để đổi endpoint mặc định.</li>
          <li>`NVIDIA`, `Ollama` và trang riêng `9router` có thể trỏ sang proxy hoặc gateway tương thích OpenAI.</li>
          <li>Dữ liệu đang được lưu trong `localStorage` của trình duyệt, không ghi vào file `.env`.</li>
        </ul>
        <button type="button" className="secondary-button settings-reset" onClick={onReset}>Khôi phục mặc định</button>
      </section>
    </section>
  );
}
