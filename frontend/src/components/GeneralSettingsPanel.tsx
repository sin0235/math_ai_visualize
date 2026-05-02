import { type ChangeEvent } from 'react';

import type { OcrProvider, RuntimeSettings, SettingsDefaults } from '../types/settings';

interface GeneralSettingsPanelProps {
  value: RuntimeSettings;
  defaults: SettingsDefaults | null;
  onChange: (next: RuntimeSettings) => void;
  onReset: () => void;
}

export function GeneralSettingsPanel({ value, defaults, onChange, onReset }: GeneralSettingsPanelProps) {
  const ocrModels = value.ocr.provider === 'router9'
    ? value.router9.scanned_models
    : value[value.ocr.provider].scanned_models;
  const selectedOcrModel = ocrModels.some((model) => model.id === value.ocr.model) ? value.ocr.model : '';

  function updateField<Key extends keyof RuntimeSettings>(key: Key, nextValue: RuntimeSettings[Key]) {
    onChange({ ...value, [key]: nextValue });
  }

  function updateOcr<Field extends keyof RuntimeSettings['ocr']>(field: Field, nextValue: RuntimeSettings['ocr'][Field]) {
    onChange({
      ...value,
      ocr: {
        ...value.ocr,
        [field]: nextValue,
      },
    });
  }

  return (
    <section className="settings-layout">
      <div className="panel settings-hero">
        <div className="panel-title">General Settings</div>
        <p className="field-hint">Configure app-wide defaults. These values are stored in this browser and sent with each request.</p>
      </div>

      <div className="settings-grid settings-grid-balanced">
        <div className="settings-stack">
          <section className="panel settings-section">
            <div className="panel-title">Default AI</div>
            <label className="field-label">
              Default provider
              <select value={value.default_provider} onChange={(event) => updateField('default_provider', event.target.value)}>
                <option value="auto">Auto select provider</option>
                <option value="nvidia">NVIDIA</option>
                <option value="openrouter">OpenRouter Nemotron</option>
                <option value="openrouter_gpt_oss">OpenRouter GPT OSS</option>
                <option value="opencode_nemotron">OpenCode Nemotron</option>
                <option value="router9">9router</option>
                <option value="ollama_gpt_oss">Ollama GPT OSS</option>
                <option value="mock">Mock extractor</option>
              </select>
            </label>

            <label className="checkbox-label settings-checkbox">
              <input
                type="checkbox"
                checked={value.openrouter_reasoning_enabled}
                onChange={(event: ChangeEvent<HTMLInputElement>) => updateField('openrouter_reasoning_enabled', event.target.checked)}
              />
              Enable OpenRouter reasoning by default
            </label>
          </section>

          <section className="panel settings-section">
            <div className="panel-title">OpenRouter metadata overrides</div>
            <label className="field-label">
              HTTP Referer
              <input
                type="url"
                value={value.openrouter_http_referer}
                onChange={(event) => updateField('openrouter_http_referer', event.target.value)}
                placeholder={defaults?.openrouter.http_referer || 'Backend default: empty'}
              />
            </label>

            <label className="field-label">
              X-Title
              <input
                type="text"
                value={value.openrouter_x_title}
                onChange={(event) => updateField('openrouter_x_title', event.target.value)}
                placeholder={defaults?.openrouter.x_title || 'Backend default'}
              />
            </label>
          </section>
        </div>

        <section className="panel settings-section">
          <div className="settings-provider-header">
            <div className="panel-title">Image OCR</div>
            <p className="field-hint">Images are sent to the selected provider to extract editable problem text before rendering.</p>
          </div>

          <label className="field-label">
            Default OCR provider
            <select value={value.ocr.provider} onChange={(event) => updateOcr('provider', event.target.value as OcrProvider)}>
              <option value="openrouter">OpenRouter vision</option>
              <option value="router9">9router vision</option>
            </select>
          </label>

          <label className="field-label">
            OCR model override
            {ocrModels.length > 0 ? (
              <select value={selectedOcrModel} onChange={(event) => updateOcr('model', event.target.value)}>
                <option value="">Backend default: {value.ocr.provider === 'openrouter' ? defaults?.openrouter.vision_model : defaults?.router9.model || 'not set'}</option>
                {ocrModels.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
              </select>
            ) : (
              <select value="" disabled>
                <option value="">Scan provider models first</option>
              </select>
            )}
            <span className="field-hint">Leave empty to use backend default; scan models first if you want to override OCR model.</span>
          </label>

          <label className="field-label">
            Max image size (MB)
            <input
              type="number"
              min="1"
              max="20"
              value={value.ocr.max_image_mb}
              onChange={(event) => updateOcr('max_image_mb', Number(event.target.value) || 1)}
            />
          </label>
        </section>
      </div>

      <section className="panel settings-section">
        <div className="panel-title">Storage</div>
        <p className="field-hint">Non-secret settings are saved locally and sync to your account after login. API key overrides stay temporary and are never saved to the database or backend .env files.</p>
        <button type="button" className="secondary-button settings-reset" onClick={onReset}>Reset to defaults</button>
      </section>
    </section>
  );
}
