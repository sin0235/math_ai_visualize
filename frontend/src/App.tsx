import { useEffect, useState } from 'react';

import { getSettingsDefaults, ocrImage, renderEditedScene, renderProblem } from './api/client';
import { defaultAdvancedSettings, ProblemInput, staticModelOptions, type ModelOption } from './components/ProblemInput';
import { GeneralSettingsPanel } from './components/GeneralSettingsPanel';
import { RendererPanel } from './components/RendererPanel';
import { Router9SettingsPanel } from './components/Router9SettingsPanel';
import { SceneJsonPanel } from './components/SceneJsonPanel';
import { SceneEditorPanel } from './components/SceneEditorPanel';
import { SettingsPanel } from './components/SettingsPanel';
import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from './types/scene';
import { defaultRuntimeSettings, SETTINGS_STORAGE_VERSION, type RuntimeSettings, type SettingsDefaults } from './types/settings';
import logoUrl from '../img.svg';
import './styles.css';

const SETTINGS_STORAGE_KEY = 'hinh-runtime-settings';

type AppView = 'render' | 'settings';
type SettingsTab = 'general' | 'providers' | 'router9';
type EditTool = 'move' | 'connect' | 'project_to_segment';
type Vec3 = { x: number; y: number; z: number };

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('render');
  const [activeSettingsTab, setActiveSettingsTab] = useState<SettingsTab>('general');
  const [result, setResult] = useState<RenderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [editorSaving, setEditorSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [problemText, setProblemText] = useState('Cho A(1,2), B(4,5). Vẽ đường thẳng AB.');
  const [lastAdvancedSettings, setLastAdvancedSettings] = useState<AdvancedRenderSettings>(defaultAdvancedSettings);
  const [editTool, setEditTool] = useState<EditTool>('move');
  const [pointToSegmentSource, setPointToSegmentSource] = useState<string | null>(null);
  const [runtimeSettings, setRuntimeSettings] = useState<RuntimeSettings>(defaultRuntimeSettings);
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsDefaults | null>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
      if (!saved) return;
      setRuntimeSettings(loadStoredSettings(saved));
    } catch {
      // Keep defaults when local storage is invalid.
    }
  }, []);

  useEffect(() => {
    getSettingsDefaults()
      .then(setSettingsDefaults)
      .catch(() => setSettingsDefaults(null));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({ version: SETTINGS_STORAGE_VERSION, settings: runtimeSettings }));
  }, [runtimeSettings]);

  const modelOptions = buildModelOptions(runtimeSettings);
  const threeInteraction = result?.scene.renderer === 'threejs_3d'
    ? {
        mode: editTool,
        selectedPoint: pointToSegmentSource,
        onPointClick: setPointToSegmentSource,
        onSegmentClick: handlePointToSegmentClick,
        onPointDragEnd: handlePointDragEnd,
        onConnectPoints: handleConnectPoints,
      }
    : undefined;

  async function handleOcrClipboardImage() {
    setOcrError(null);
    if (!navigator.clipboard?.read) {
      setOcrError('Trình duyệt chưa hỗ trợ đọc ảnh từ clipboard.');
      return;
    }
    try {
      const clipboardItems = await navigator.clipboard.read();
      for (const item of clipboardItems) {
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageType) continue;
        const blob = await item.getType(imageType);
        await handleOcrImage(new File([blob], 'clipboard-image.png', { type: imageType }));
        return;
      }
      setOcrError('Clipboard hiện không có ảnh để OCR.');
    } catch (caught) {
      setOcrError(caught instanceof Error ? caught.message : 'Không đọc được ảnh từ clipboard.');
    }
  }

  async function handleOcrImage(file: File) {
    setOcrError(null);
    if (!file.type.startsWith('image/')) {
      setOcrError('File OCR phải là ảnh.');
      return;
    }
    const maxBytes = Math.max(1, runtimeSettings.ocr.max_image_mb) * 1024 * 1024;
    if (file.size > maxBytes) {
      setOcrError(`Ảnh OCR vượt quá giới hạn ${runtimeSettings.ocr.max_image_mb}MB.`);
      return;
    }

    setOcrLoading(true);
    try {
      const imageDataUrl = await fileToDataUrl(file);
      const response = await ocrImage(imageDataUrl, runtimeSettings);
      setProblemText(response.text.trim());
    } catch (caught) {
      setOcrError(caught instanceof Error ? caught.message : 'Không thể OCR ảnh đề bài.');
    } finally {
      setOcrLoading(false);
    }
  }

  async function handleSubmit(
    problemText: string,
    preferredAiProvider?: string,
    preferredAiModel?: string,
    advancedSettings?: AdvancedRenderSettings,
    preferredRenderer?: Renderer,
  ) {
    setLoading(true);
    setError(null);
    setPointToSegmentSource(null);
    setEditTool('move');
    setLastAdvancedSettings(advancedSettings ?? defaultAdvancedSettings);
    try {
      setResult(await renderProblem(problemText, preferredAiProvider, preferredAiModel, advancedSettings, preferredRenderer, runtimeSettings));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Có lỗi không xác định.');
    } finally {
      setLoading(false);
    }
  }

  function resetSettings() {
    setRuntimeSettings(defaultRuntimeSettings);
  }

  async function handleSceneEdit(scene: MathScene) {
    setEditorSaving(true);
    setError(null);
    try {
      setResult(await renderEditedScene(scene, lastAdvancedSettings));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không dựng lại được scene.');
    } finally {
      setEditorSaving(false);
    }
  }

  async function handlePointDragEnd(name: string, point: Vec3) {
    if (!result?.scene) return;
    const editedScene: MathScene = {
      ...result.scene,
      objects: result.scene.objects.map((obj) => {
        if ((obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name) {
          if (obj.type === 'point_3d') {
            return { ...obj, x: round(point.x), y: round(point.y), z: round(point.z) };
          }
          return { ...obj, x: round(point.x), y: round(point.y) };
        }
        return obj;
      }),
    };
    await handleSceneEdit(editedScene);
  }

  async function handleConnectPoints(start: string, end: string) {
    if (!result?.scene) return;
    if (start === end) {
      setError('Chọn hai điểm khác nhau để nối đoạn.');
      return;
    }
    if (hasSegment(result.scene, start, end)) {
      setError(`Đoạn ${start}${end} đã tồn tại.`);
      return;
    }
    const editedScene: MathScene = {
      ...result.scene,
      objects: [
        ...result.scene.objects,
        { type: 'segment', points: [start, end], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
      ],
    };
    await handleSceneEdit(editedScene);
  }

  async function handlePointToSegmentClick(segmentPoints: [string, string], clickedPoint: Vec3) {
    if (!result?.scene || !pointToSegmentSource || editTool !== 'project_to_segment') {
      setError('Chọn công cụ tạo chân nối, chọn một điểm nguồn, rồi click vào đoạn đích.');
      return;
    }
    if (segmentPoints.includes(pointToSegmentSource)) {
      setError('Điểm nguồn đang nằm trên đoạn đích. Hãy chọn đoạn khác nếu muốn nối thêm.');
      return;
    }

    const source = findPoint(result.scene, pointToSegmentSource);
    const start = findPoint(result.scene, segmentPoints[0]);
    const end = findPoint(result.scene, segmentPoints[1]);
    if (!source || !start || !end) {
      setError('Không tìm thấy điểm nguồn hoặc đoạn đích trong scene.');
      return;
    }

    const newPoint = projectPointToSegment(clickedPoint, start, end);
    const newName = nextPointName(result.scene);
    const editedScene: MathScene = {
      ...result.scene,
      objects: [
        ...result.scene.objects,
        { type: 'point_3d', name: newName, x: round(newPoint.x), y: round(newPoint.y), z: round(newPoint.z) },
        { type: 'segment', points: [pointToSegmentSource, newName], hidden: false, color: '#1d3557', line_width: 3, style: 'solid' },
      ],
    };

    setPointToSegmentSource(null);
    await handleSceneEdit(editedScene);
  }

  return (
    <>
      <header className="global-header">
        <div className="header-left">
          <img src={logoUrl} alt="App Logo" className="header-logo" />
          <div className="header-titles">
            <h1 className="header-title">AI Math Renderer</h1>
            <span className="header-subtitle">Dựng hình toán học từ ngôn ngữ tự nhiên</span>
          </div>
        </div>
        <nav className="header-nav">
          <button type="button" className={`nav-item ${activeView === 'render' ? 'active' : ''}`} onClick={() => setActiveView('render')}>
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="6" x2="20" y2="6"></line><line x1="4" y1="12" x2="14" y2="12"></line><line x1="4" y1="18" x2="18" y2="18"></line></svg>
            Dựng hình
          </button>
          <button type="button" className={`nav-item ${activeView === 'settings' ? 'active' : ''}`} onClick={() => setActiveView('settings')}>
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10.91 3H11a2 2 0 1 1 4 0h.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0A1.65 1.65 0 0 0 21 10.91V11a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Setting
          </button>
        </nav>
      </header>

      <main className="app-shell">
        {activeView === 'render' && (
          <section className="workspace">
            <ProblemInput
              loading={loading}
              ocrLoading={ocrLoading}
              ocrError={ocrError}
              problemText={problemText}
              modelOptions={modelOptions}
              router9Only={runtimeSettings.router9.only_mode}
              onProblemTextChange={setProblemText}
              onOcrImage={handleOcrImage}
              onOcrClipboardImage={handleOcrClipboardImage}
              onOpenRouter9Settings={() => {
                setActiveView('settings');
                setActiveSettingsTab('router9');
              }}
              onSubmit={handleSubmit}
            />
            <div className="result-area">
              {error && <div className="error-box">{error}</div>}
              {result?.warnings.map((warning) => <div className="warning-box" key={warning}>{warning}</div>)}
              <SceneEditorPanel
                scene={result?.scene ?? null}
                saving={editorSaving}
                editTool={editTool}
                selectedPoint={pointToSegmentSource}
                onEditToolChange={(tool) => {
                  setEditTool(tool);
                  setPointToSegmentSource(null);
                }}
                onChange={handleSceneEdit}
              />
              <RendererPanel result={result} threeInteraction={threeInteraction} />
              <SceneJsonPanel result={result} />
            </div>
          </section>
        )}
        {activeView === 'settings' && (
          <section className="settings-page">
            <div className="settings-tabs">
              <button type="button" className={`settings-tab ${activeSettingsTab === 'general' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('general')}>General</button>
              <button type="button" className={`settings-tab ${activeSettingsTab === 'providers' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('providers')}>Provider</button>
              <button type="button" className={`settings-tab ${activeSettingsTab === 'router9' ? 'active' : ''}`} onClick={() => setActiveSettingsTab('router9')}>9router</button>
            </div>
            {activeSettingsTab === 'general' ? (
              <GeneralSettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onReset={resetSettings} />
            ) : activeSettingsTab === 'providers' ? (
              <SettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} onReset={resetSettings} />
            ) : (
              <Router9SettingsPanel value={runtimeSettings} defaults={settingsDefaults} onChange={setRuntimeSettings} />
            )}
          </section>
        )}
      </main>
    </>
  );
}

function loadStoredSettings(saved: string): RuntimeSettings {
  const parsed = JSON.parse(saved) as { version?: number; settings?: Partial<RuntimeSettings> } & Partial<RuntimeSettings>;
  const rawSettings = parsed.settings ?? parsed;
  const next: RuntimeSettings = {
    ...defaultRuntimeSettings,
    ...rawSettings,
    openrouter: { ...defaultRuntimeSettings.openrouter, ...rawSettings.openrouter },
    nvidia: { ...defaultRuntimeSettings.nvidia, ...rawSettings.nvidia },
    ollama: { ...defaultRuntimeSettings.ollama, ...rawSettings.ollama },
    router9: { ...defaultRuntimeSettings.router9, ...rawSettings.router9 },
    ocr: { ...defaultRuntimeSettings.ocr, ...rawSettings.ocr },
  };

  if (parsed.version !== SETTINGS_STORAGE_VERSION) {
    dropLegacyDefaults(next);
  }
  dropLegacyOcrDefaults(next);

  return next;
}

function dropLegacyDefaults(settings: RuntimeSettings) {
  const legacyProviderDefaults = {
    openrouter: { base_url: 'https://openrouter.ai/api/v1', model: 'openrouter/nvidia/nemotron-3-super-120b-a12b:free' },
    nvidia: { base_url: 'https://integrate.api.nvidia.com/v1', model: 'qwen/qwen3-coder-480b-a35b-instruct' },
    ollama: { base_url: 'https://ollama.com/v1', model: 'gpt-oss:120b' },
    router9: { base_url: 'http://localhost:20128/v1', model: '' },
  };

  for (const provider of ['openrouter', 'nvidia', 'ollama', 'router9'] as const) {
    if (settings[provider].base_url === legacyProviderDefaults[provider].base_url) {
      settings[provider].base_url = '';
    }
    if (settings[provider].model === legacyProviderDefaults[provider].model) {
      settings[provider].model = '';
    }
  }

  dropLegacyOcrDefaults(settings);
  if (settings.openrouter_x_title === 'Hinh Math Renderer') {
    settings.openrouter_x_title = '';
  }
}

function dropLegacyOcrDefaults(settings: RuntimeSettings) {
  if (settings.ocr.model === 'qwen/qwen2.5-vl-72b-instruct:free' || settings.ocr.model === 'google/gemma-4-26b-a4b-it:free') {
    settings.ocr.model = '';
  }
}

function hasSegment(scene: MathScene, start: string, end: string) {
  return scene.objects.some((obj) => {
    if (obj.type !== 'segment') return false;
    const [a, b] = obj.points;
    return (a === start && b === end) || (a === end && b === start);
  });
}

function findPoint(scene: MathScene, name: string): Vec3 | null {
  const point = scene.objects.find((obj) => (obj.type === 'point_2d' || obj.type === 'point_3d') && obj.name === name);
  if (!point || (point.type !== 'point_2d' && point.type !== 'point_3d')) return null;
  return { x: point.x, y: point.y, z: point.type === 'point_3d' ? point.z : 0 };
}

function projectPointToSegment(point: Vec3, start: Vec3, end: Vec3): Vec3 {
  const direction = sub(end, start);
  const size = dot(direction, direction);
  if (size <= 1e-9) return start;
  const t = Math.max(0, Math.min(1, dot(sub(point, start), direction) / size));
  return add(start, scale(direction, t));
}

function nextPointName(scene: MathScene) {
  const used = new Set(scene.objects.map((obj) => ('name' in obj && typeof obj.name === 'string' ? obj.name : null)).filter(Boolean));
  for (const name of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
    if (!used.has(name)) return name;
  }
  let index = 1;
  while (used.has(`P${index}`)) index += 1;
  return `P${index}`;
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

function dot(a: Vec3, b: Vec3) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function round(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
      } else {
        reject(new Error('Không đọc được ảnh OCR.'));
      }
    };
    reader.onerror = () => reject(new Error('Không đọc được ảnh OCR.'));
    reader.readAsDataURL(file);
  });
}

function buildModelOptions(settings: RuntimeSettings): ModelOption[] {
  const scannedProviderOptions = (['openrouter', 'nvidia', 'ollama'] as const).flatMap((provider) =>
    settings[provider].scanned_models.map((model) => ({
      key: `${provider}:${model.id}`,
      provider,
      modelId: model.id,
      label: `${providerLabel(provider)}: ${model.label}`,
      description: `${providerLabel(provider)} model ${model.id}${model.context_length ? ` — context ${model.context_length}` : ''}`,
    }))
  );

  const router9Options = settings.router9.allowed_model_ids.map((modelId) => {
    const scanned = settings.router9.scanned_models.find((model) => model.id === modelId);
    return {
      key: `router9:${modelId}`,
      provider: 'router9',
      modelId,
      label: `9router: ${scanned?.label ?? modelId}`,
      description: `9router model ${modelId}`,
    };
  });

  if (settings.router9.only_mode) {
    return router9Options;
  }

  const showMockProvider = import.meta.env.DEV || import.meta.env.VITE_SHOW_MOCK_PROVIDER === 'true';
  const staticOptions = showMockProvider
    ? [...staticModelOptions, { key: 'provider:mock', provider: 'mock', label: 'Mock extractor', description: 'Mock extractor — chế độ kiểm thử nội bộ, không gọi AI bên ngoài.' }]
    : staticModelOptions;
  return [...staticOptions, ...scannedProviderOptions, ...router9Options];
}

function providerLabel(provider: 'openrouter' | 'nvidia' | 'ollama') {
  if (provider === 'openrouter') return 'OpenRouter';
  if (provider === 'nvidia') return 'NVIDIA';
  return 'Ollama';
}
