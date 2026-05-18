import type { ComponentProps } from 'react';
import { ApiError } from './api/client';
import type { AnalyzeOptions, AnalyzeResponse, RenderHistoryItem, SolveResponse, UserResponse } from './api/client';
import { analyzeFunction, analyzeFunctionImage } from './api/analyze';
import { getCurrentUser, login, logout } from './api/auth';
import { checkAllAdminProviders, getAdminSummary } from './api/admin';
import { getHealth, renderProblem, solveProblem } from './api/render';
import { AccessDeniedPage, HistoryPanel, isGeometryMobileWarningView } from './components/AppPages';
import { FunctionAnalyzerPanel } from './components/FunctionAnalyzerPanel';
import { AnalyzerInput } from './components/function-analyzer/AnalyzerInput';
import { AnalyzerResult } from './components/function-analyzer/AnalyzerResult';
import { AnalyzerToolControls } from './components/function-analyzer/AnalyzerToolControls';
import { FunctionGraph } from './components/function-analyzer/FunctionGraph';
import { VariationTable } from './components/function-analyzer/VariationTable';
import { SvgIcon } from './components/function-analyzer/icons';
import { useFunctionAnalysis } from './components/function-analyzer/useFunctionAnalysis';
import { NotificationStack } from './components/NotificationStack';
import type { Notification } from './hooks/useNotifications';
import type { RuntimeSettings } from './types/settings';
import type { MathScene } from './types/scene';
import { clamp, findPoint, hasSegment, nextPointName, projectPointToSegment, round } from './utils/sceneEditing';

const apiError: ApiError = new ApiError('x', ['detail']);
void apiError;

const analyzeOptions: AnalyzeOptions = {
  interval: { a: -1, b: 1 },
  line: { k: 1, b: 0 },
  transform: { type: 'vertical_shift', value: 1 },
};
void analyzeOptions;

const analyzeResponse: AnalyzeResponse = {
  expression: 'x^2',
  expression_latex: 'x^2',
  evaluated_expression: null,
  evaluated_expression_latex: null,
  parameters: null,
  analysis_mode: 'symbolic',
  derivative: '2*x',
  derivative_latex: '2x',
  second_derivative: null,
  second_derivative_latex: null,
  critical_points: [],
  inflection_points: [],
  intervals_increasing: [],
  intervals_decreasing: [],
  concave_up_intervals: [],
  concave_down_intervals: [],
  horizontal_asymptotes: [],
  vertical_asymptotes: [],
  oblique_asymptote: null,
  x_intercepts: [],
  y_intercept: null,
  variation_table: [],
  domain: 'R',
  domain_latex: '\\mathbb{R}',
  range_val: null,
  range_latex: null,
  parity: 'neither',
  geogebra_commands: [],
  graph_scene: null,
  graph_points: [{ x: 0, y: 0 }, { x: 1, y: 1 }],
  ocr_text: null,
  ocr_expression: null,
  warnings: [],
};

const solveResponse: SolveResponse = { question: 'q', answer: 'a', warnings: [], steps: [] };
void solveResponse;

const user: UserResponse = {
  id: 'u1',
  email: 'user@example.com',
  created_at: '2026-01-01T00:00:00Z',
  role: 'user',
  status: 'active',
  plan: 'free',
};

const historyItem: RenderHistoryItem = {
  id: 'h1',
  problem_text: 'problem',
  created_at: '2026-01-01T00:00:00Z',
  source_type: 'text',
};

const scene: MathScene = {
  problem_text: 'scene',
  grade: null,
  topic: 'geometry',
  renderer: 'geogebra_2d',
  objects: [
    { type: 'point_2d', name: 'A', x: 0, y: 0 },
    { type: 'point_2d', name: 'B', x: 2, y: 0 },
    { type: 'segment', name: 'AB', points: ['A', 'B'], hidden: false },
  ],
  relations: [],
  annotations: [],
  view: { dimension: '2d', show_axes: true, show_grid: true, show_coordinates: false },
};

const notification: Notification = { id: 1, kind: 'info', title: 't', message: 'm', details: [] };

const analyzerPanelProps: ComponentProps<typeof FunctionAnalyzerPanel> = {
  initialExpression: 'x^2',
  onOpenGuide: () => undefined,
  onWarnings: () => undefined,
};

const analyzerInputProps: ComponentProps<typeof AnalyzerInput> = {
  expression: 'x^2',
  loading: false,
  ocrLoading: false,
  error: null,
  onExpressionChange: () => undefined,
  onAnalyze: () => undefined,
  onImageChange: () => undefined,
};

const analyzerResultProps: ComponentProps<typeof AnalyzerResult> = {
  result: analyzeResponse,
  toolControls: null,
};

const analyzerToolProps: ComponentProps<typeof AnalyzerToolControls> = {
  enableInterval: false,
  enableLine: false,
  enableTransform: false,
  intervalA: -2,
  intervalB: 2,
  lineK: 1,
  lineB: 0,
  transformType: 'vertical_shift',
  transformValue: 1,
  isAnimatingTransform: false,
  disabled: false,
  onToggleTool: () => undefined,
  onIntervalAChange: () => undefined,
  onIntervalBChange: () => undefined,
  onLineKChange: () => undefined,
  onLineBChange: () => undefined,
  onTransformTypeChange: () => undefined,
  onTransformValueChange: () => undefined,
  onToggleAnimation: () => undefined,
};

const notificationStackProps: ComponentProps<typeof NotificationStack> = {
  notifications: [notification],
  onDismiss: () => undefined,
};

const accessDeniedProps: ComponentProps<typeof AccessDeniedPage> = {
  user,
  onHome: () => undefined,
  onLogin: () => undefined,
};

const historyPanelProps: ComponentProps<typeof HistoryPanel> = {
  items: [historyItem],
  loading: false,
  openingId: null,
  onOpen: () => undefined,
  onDelete: () => undefined,
};

const variationTableProps: ComponentProps<typeof VariationTable> = {
  rows: [{ x: '0', y: '0', kind: 'min', arrow_to_next: 'up' }],
};

const functionGraphProps: ComponentProps<typeof FunctionGraph> = { result: analyzeResponse };
const iconProps: ComponentProps<typeof SvgIcon> = { name: 'graph' };

void analyzerPanelProps;
void analyzerInputProps;
void analyzerResultProps;
void analyzerToolProps;
void notificationStackProps;
void accessDeniedProps;
void historyPanelProps;
void variationTableProps;
void functionGraphProps;
void iconProps;
void useFunctionAnalysis;
void analyzeFunction;
void analyzeFunctionImage;
void getCurrentUser;
void login;
void logout;
void checkAllAdminProviders;
void getAdminSummary;
void getHealth;
void renderProblem;
void solveProblem;
void (undefined as RuntimeSettings | undefined);

const pointA = findPoint(scene, 'A');
const pointB = findPoint(scene, 'B');
if (pointA && pointB) {
  const projection = projectPointToSegment({ x: 1, y: 1, z: 0 }, pointA, pointB);
  round(projection.x);
}

hasSegment(scene, 'A', 'B');
nextPointName(scene);
clamp(10, 0, 5);
isGeometryMobileWarningView('render');
