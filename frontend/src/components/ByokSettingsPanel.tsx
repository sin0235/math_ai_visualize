import { useEffect, useMemo, useState } from 'react';

import { checkUserAiProvider, getUserSettings, updateUserAiModels, updateUserAiProvider, updateUserAiTaskProfiles } from '../api/userSettings';
import type { UserAiModelSettings, UserAiProviderSettings, UserAiTaskProfileSettings, UserAiTask } from '../types/userSettings';
import { USER_AI_TASK_LABELS, USER_AI_TASKS } from '../types/userSettings';

type ToastKind = 'error' | 'warning' | 'info';

interface ByokSettingsPanelProps {
  onToast: (title: string, message: string, kind?: ToastKind) => void;
}

const emptyProvider: UserAiProviderSettings = {
  enabled: false,
  base_url: '',
  api_key_configured: false,
};

export function ByokSettingsPanel({ onToast }: ByokSettingsPanelProps) {
  const [provider, setProvider] = useState<UserAiProviderSettings>(emptyProvider);
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState<UserAiModelSettings[]>([]);
  const [taskProfiles, setTaskProfiles] = useState<UserAiTaskProfileSettings[]>([]);
  const [checkModel, setCheckModel] = useState('gpt-4o-mini');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSettings().catch((error) => onToast('BYOK', error instanceof Error ? error.message : 'Không thể tải cấu hình BYOK.', 'error'));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ tải khi mở trang tài khoản
  }, []);

  const enabledModels = useMemo(() => models.filter((model) => model.enabled), [models]);

  async function loadSettings() {
    const settings = await getUserSettings();
    setProvider(settings.ai_provider);
    setModels(settings.models.map(({ model_id, label, supports_vision, enabled }) => ({ model_id, label, supports_vision, enabled })));
    setTaskProfiles(settings.task_profiles);
  }

  async function saveProvider(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      const updated = await updateUserAiProvider({
        enabled: provider.enabled,
        base_url: provider.base_url,
        api_key: apiKey || null,
      });
      setProvider(updated.ai_provider);
      setModels(updated.models.map(({ model_id, label, supports_vision, enabled }) => ({ model_id, label, supports_vision, enabled })));
      setTaskProfiles(updated.task_profiles);
      setApiKey('');
      onToast('BYOK', 'Đã lưu cấu hình provider.', 'info');
    } catch (error) {
      onToast('BYOK', error instanceof Error ? error.message : 'Không thể lưu cấu hình provider.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function clearApiKey() {
    setLoading(true);
    try {
      const updated = await updateUserAiProvider({
        enabled: false,
        base_url: provider.base_url,
        clear_api_key: true,
      });
      setProvider(updated.ai_provider);
      setApiKey('');
      onToast('BYOK', 'Đã xoá API key đã lưu.', 'info');
    } catch (error) {
      onToast('BYOK', error instanceof Error ? error.message : 'Không thể xoá API key.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function checkProvider() {
    setLoading(true);
    try {
      const result = await checkUserAiProvider({
        base_url: provider.base_url,
        api_key: apiKey || null,
        model: checkModel,
      });
      onToast('BYOK', result.message, result.ok ? 'info' : 'warning');
    } catch (error) {
      onToast('BYOK', error instanceof Error ? error.message : 'Không thể kiểm tra provider.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function saveModels(nextModels: UserAiModelSettings[]) {
    setLoading(true);
    try {
      const updated = await updateUserAiModels({ models: nextModels });
      setModels(updated.models.map(({ model_id, label, supports_vision, enabled }) => ({ model_id, label, supports_vision, enabled })));
      setTaskProfiles(updated.task_profiles);
      onToast('BYOK', 'Đã lưu danh sách model.', 'info');
    } catch (error) {
      onToast('BYOK', error instanceof Error ? error.message : 'Không thể lưu model.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function saveTaskProfiles(nextProfiles: UserAiTaskProfileSettings[]) {
    setLoading(true);
    try {
      const updated = await updateUserAiTaskProfiles({ task_profiles: nextProfiles });
      setTaskProfiles(updated.task_profiles);
      onToast('BYOK', 'Đã lưu model theo tác vụ.', 'info');
    } catch (error) {
      onToast('BYOK', error instanceof Error ? error.message : 'Không thể lưu task profile.', 'error');
    } finally {
      setLoading(false);
    }
  }

  function addModel() {
    setModels([...models, { model_id: '', label: '', supports_vision: false, enabled: true }]);
  }

  function updateModel(index: number, patch: Partial<UserAiModelSettings>) {
    setModels(models.map((model, current) => (current === index ? { ...model, ...patch } : model)));
  }

  function removeModel(index: number) {
    setModels(models.filter((_, current) => current !== index));
  }

  function updateTask(task: UserAiTask, modelId: string) {
    const next = taskProfiles.filter((profile) => profile.task !== task);
    if (modelId) next.push({ task, model_id: modelId, enabled: true });
    setTaskProfiles(next);
  }

  function taskModel(task: UserAiTask) {
    return taskProfiles.find((profile) => profile.task === task && profile.enabled)?.model_id ?? '';
  }

  return (
    <section className="account-panel">
      <div className="account-section-title">
        <div className="account-panel-title"><h3>BYOK OpenAI-compatible</h3></div>
        <div className={provider.enabled ? 'status-pill success' : 'status-pill warning'}>{provider.enabled ? 'Đang bật' : 'Đang tắt'}</div>
      </div>
      <p className="field-hint">Cấu hình API key riêng cho tài khoản. API key chỉ gửi lên server khi lưu hoặc kiểm tra, không lưu trong trình duyệt.</p>

      <form className="account-grid" onSubmit={saveProvider}>
        <label className="field-label">
          Base URL
          <input value={provider.base_url} onChange={(event) => setProvider({ ...provider, base_url: event.target.value })} placeholder="https://api.example.com/v1" maxLength={500} />
        </label>
        <label className="field-label">
          API key mới
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={provider.api_key_configured ? `Đã lưu key kết thúc bằng ${provider.api_key_last4 ?? '****'}` : 'Nhập API key'} autoComplete="off" maxLength={4096} />
        </label>
        <label className="field-label">
          Model kiểm tra
          <input value={checkModel} onChange={(event) => setCheckModel(event.target.value)} placeholder="gpt-4o-mini" maxLength={256} />
        </label>
        <label className="field-label byok-toggle-row">
          <span>Bật BYOK cho tài khoản</span>
          <input type="checkbox" checked={provider.enabled} onChange={(event) => setProvider({ ...provider, enabled: event.target.checked })} />
        </label>
        <div className="auth-actions">
          <button type="submit" disabled={loading}>Lưu provider</button>
          <button type="button" className="secondary-button" onClick={checkProvider} disabled={loading || !provider.base_url || !checkModel}>Kiểm tra kết nối</button>
          {provider.api_key_configured && <button type="button" className="secondary-button" onClick={clearApiKey} disabled={loading}>Xoá API key</button>}
        </div>
      </form>

      <div className="account-panel nested-panel">
        <div className="account-section-title">
          <div className="account-panel-title"><h4>Model BYOK</h4></div>
          <button type="button" className="secondary-button" onClick={addModel} disabled={loading}>Thêm model</button>
        </div>
        <div className="byok-model-list">
          {models.map((model, index) => (
            <div className="byok-model-row" key={`${model.model_id}-${index}`}>
              <input value={model.model_id} onChange={(event) => updateModel(index, { model_id: event.target.value, label: model.label || event.target.value })} placeholder="model-id" maxLength={256} />
              <input value={model.label} onChange={(event) => updateModel(index, { label: event.target.value })} placeholder="Nhãn hiển thị" maxLength={256} />
              <label><input type="checkbox" checked={model.supports_vision} onChange={(event) => updateModel(index, { supports_vision: event.target.checked })} /> Vision</label>
              <label><input type="checkbox" checked={model.enabled} onChange={(event) => updateModel(index, { enabled: event.target.checked })} /> Bật</label>
              <button type="button" className="secondary-button" onClick={() => removeModel(index)} disabled={loading}>Xoá</button>
            </div>
          ))}
          {models.length === 0 && <p className="field-hint">Chưa có model BYOK nào.</p>}
        </div>
        <button type="button" onClick={() => saveModels(models)} disabled={loading}>Lưu model</button>
      </div>

      <div className="account-panel nested-panel">
        <div className="account-panel-title"><h4>Model theo tác vụ</h4></div>
        <div className="account-grid">
          {USER_AI_TASKS.map((task) => (
            <label className="field-label" key={task}>
              {USER_AI_TASK_LABELS[task]}
              <select value={taskModel(task)} onChange={(event) => updateTask(task, event.target.value)}>
                <option value="">Chưa chọn</option>
                {enabledModels.map((model) => (
                  <option key={`${task}-${model.model_id}`} value={model.model_id}>{model.label || model.model_id}</option>
                ))}
              </select>
            </label>
          ))}
        </div>
        <button type="button" onClick={() => saveTaskProfiles(taskProfiles)} disabled={loading}>Lưu tác vụ</button>
      </div>
    </section>
  );
}
