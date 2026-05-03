import type { OcrProvider, RuntimeSettings, SettingsDefaults } from '../types/settings';
import { buildModelOptionsFromDefaults, buildOcrProviderOptions, buildProviderOptions } from '../utils/settingsOptions';

interface GeneralSettingsPanelProps {
  value: RuntimeSettings;
  defaults: SettingsDefaults | null;
  onChange: (next: RuntimeSettings) => void;
  onReset: () => void;
}

export function GeneralSettingsPanel({ value, defaults, onChange, onReset }: GeneralSettingsPanelProps) {
  const providerOptions = buildProviderOptions(defaults, false);
  const providerModelOptions = buildProviderModelOptions(defaults, value.default_provider, currentProviderModel(value));
  const ocrProviderOptions = buildOcrProviderOptions(defaults);
  const ocrProviderDefaults = value.ocr.provider === 'router9' ? defaults?.router9 : defaults?.openrouter;
  const ocrModels = buildModelOptionsFromDefaults(ocrProviderDefaults, value.ocr.model, [defaults?.ocr.model ?? '']);
  const selectedOcrModel = value.ocr.model;

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

  function updateDefaultModel(modelId: string) {
    const provider = value.default_provider;
    if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'router9') {
      onChange({
        ...value,
        [provider]: { ...value[provider], model: modelId },
      });
    }
  }

  return (
    <section className="settings-layout">
      <div className="panel settings-hero">
        <div className="panel-title">Cài đặt cá nhân</div>
        <p className="field-hint">Bạn chỉ chọn provider/model mặc định và các tuỳ chọn cơ bản. Quét model, allowlist và cấu hình provider nằm trong Admin Dashboard.</p>
      </div>

      <div className="settings-grid settings-grid-balanced">
        <div className="settings-stack">
          <section className="panel settings-section">
            <div className="panel-title">AI mặc định</div>
            <label className="field-label">
              Provider mặc định
              <select value={value.default_provider} onChange={(event) => updateField('default_provider', event.target.value)}>
                {providerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>) }
              </select>
            </label>

            <label className="field-label">
              Model mặc định
              <select value={currentProviderModel(value)} onChange={(event) => updateDefaultModel(event.target.value)} disabled={value.default_provider === 'auto' || value.default_provider === 'mock'}>
                <option value="">Dùng mặc định hệ thống</option>
                {currentProviderModel(value) && !providerModelOptions.some((model) => model.id === currentProviderModel(value)) && <option value={currentProviderModel(value)}>{currentProviderModel(value)}</option>}
                {providerModelOptions.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
              </select>
              <span className="field-hint">Danh sách này do admin bật trong dashboard quản trị.</span>
            </label>
          </section>

          <section className="panel settings-section">
            <div className="panel-title">Phân quyền cấu hình</div>
            <p className="field-hint">Người dùng thường không thể đổi base URL, quét model hoặc quản lý allowlist. Các cấu hình đó được lưu ở cơ sở dữ liệu bởi admin.</p>
          </section>
        </div>

        <section className="panel settings-section">
          <div className="settings-provider-header">
            <div className="panel-title">OCR ảnh</div>
            <p className="field-hint">Ảnh được gửi tới provider/model OCR đã được admin cấu hình để trích xuất đề bài.</p>
          </div>

          <label className="field-label">
            Provider OCR mặc định
            <select value={value.ocr.provider} onChange={(event) => updateOcr('provider', event.target.value as OcrProvider)}>
              {ocrProviderOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>) }
            </select>
          </label>

          <label className="field-label">
            Model OCR mặc định
            <select value={selectedOcrModel} onChange={(event) => updateOcr('model', event.target.value)}>
              <option value="">Dùng mặc định hệ thống: {value.ocr.provider === 'openrouter' ? defaults?.openrouter.vision_model : defaults?.router9.model || 'chưa đặt'}</option>
              {value.ocr.model && !ocrModels.some((model) => model.id === value.ocr.model) && <option value={value.ocr.model}>{value.ocr.model}</option>}
              {ocrModels.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}
            </select>
            <span className="field-hint">Để trống để dùng mặc định hệ thống; danh sách model do admin bật.</span>
          </label>

          <label className="field-label">
            Kích thước ảnh tối đa (MB)
            <input
              type="number"
              min="1"
              max="32"
              value={value.ocr.max_image_mb}
              onChange={(event) => updateOcr('max_image_mb', Number(event.target.value) || 1)}
            />
          </label>
        </section>
      </div>

      <section className="panel settings-section">
        <div className="panel-title">Lưu trữ</div>
        <p className="field-hint">Cài đặt cá nhân được lưu cục bộ và đồng bộ vào tài khoản sau khi đăng nhập. Các cấu hình hệ thống/model được admin lưu trong cơ sở dữ liệu.</p>
        <button type="button" className="secondary-button settings-reset" onClick={onReset}>Khôi phục mặc định</button>
      </section>
    </section>
  );
}

function currentProviderModel(value: RuntimeSettings) {
  const provider = value.default_provider;
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'router9') return value[provider].model;
  return '';
}

function buildProviderModelOptions(defaults: SettingsDefaults | null, provider: string, currentModel: string) {
  if (!defaults || !(provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'router9')) return currentModel ? [{ id: currentModel, label: currentModel }] : [];
  return buildModelOptionsFromDefaults(defaults[provider], currentModel);
}
