import type { CommittedSceneRefV3, MathSceneV3, SceneCommand, SceneWorkspaceResponseV3 } from '../types/sceneV3';

export type CommandCommitMode = 'normal' | 'undo' | 'redo';

export interface SceneWorkspaceStateV3 {
  committed: SceneWorkspaceResponseV3 | null;
  previewScene: MathSceneV3 | null;
  pendingCommand: SceneCommand | null;
  pendingMode: CommandCommitMode | null;
  undoStack: SceneCommand[];
  redoStack: SceneCommand[];
  confirmedRevision: number | null;
  error: string | null;
}

export const emptySceneWorkspaceStateV3: SceneWorkspaceStateV3 = {
  committed: null,
  previewScene: null,
  pendingCommand: null,
  pendingMode: null,
  undoStack: [],
  redoStack: [],
  confirmedRevision: null,
  error: null,
};

export type SceneWorkspaceActionV3 =
  | { type: 'load'; response: SceneWorkspaceResponseV3 }
  | { type: 'preview'; scene: MathSceneV3 }
  | { type: 'clear_preview' }
  | { type: 'begin'; command: SceneCommand; mode: CommandCommitMode }
  | { type: 'commit'; response: SceneWorkspaceResponseV3 }
  | { type: 'reject'; message: string }
  | { type: 'confirm'; response: SceneWorkspaceResponseV3 };

export function sceneWorkspaceReducerV3(state: SceneWorkspaceStateV3, action: SceneWorkspaceActionV3): SceneWorkspaceStateV3 {
  switch (action.type) {
    case 'load':
      return {
        ...emptySceneWorkspaceStateV3,
        committed: action.response,
        confirmedRevision: action.response.confirmed_revision ?? null,
      };
    case 'preview':
      return { ...state, previewScene: action.scene, error: null };
    case 'clear_preview':
      return { ...state, previewScene: null };
    case 'begin':
      return { ...state, pendingCommand: action.command, pendingMode: action.mode, error: null };
    case 'commit':
      return commitResponse(state, action.response);
    case 'reject':
      return { ...state, previewScene: null, pendingCommand: null, pendingMode: null, error: action.message };
    case 'confirm':
      return {
        ...state,
        committed: action.response,
        confirmedRevision: action.response.confirmed_revision ?? null,
        error: null,
      };
  }
}

export function rebaseSceneCommand(command: SceneCommand, scene: MathSceneV3): SceneCommand {
  return { ...command, scene_id: scene.scene_id, base_revision: scene.revision };
}

export function previewPointMove(scene: MathSceneV3, pointId: string, position: [number, number, number]): MathSceneV3 {
  const objects = scene.objects.map((object) => {
    if (object.id !== pointId) return object;
    if (object.type === 'point_2d') return { ...object, x: position[0], y: position[1] };
    if (object.type === 'point_3d') return { ...object, x: position[0], y: position[1], z: position[2] };
    return object;
  });
  return { ...scene, objects };
}

export function workspaceDisplayScene(state: SceneWorkspaceStateV3): MathSceneV3 | null {
  return state.previewScene ?? state.committed?.scene ?? null;
}

export function workspaceIsTrusted(state: SceneWorkspaceStateV3): boolean {
  return state.committed?.trusted_for_downstream === true;
}

export function committedSceneRefV3(workspace: SceneWorkspaceResponseV3): CommittedSceneRefV3 {
  return { scene_id: workspace.scene.scene_id, revision: workspace.scene.revision };
}

export function downstreamGateMessageV3(workspace: SceneWorkspaceResponseV3, action: string): string | null {
  return workspace.trusted_for_downstream ? null : `Scene chưa được backend xác nhận cho ${action}.`;
}

function commitResponse(state: SceneWorkspaceStateV3, response: SceneWorkspaceResponseV3): SceneWorkspaceStateV3 {
  const inverse = response.inverse_command;
  if (!inverse || !state.pendingMode) {
    return { ...emptySceneWorkspaceStateV3, committed: response, error: 'Server không trả inverse command.' };
  }
  if (state.pendingMode === 'undo') {
    return {
      ...state,
      committed: response,
      previewScene: null,
      pendingCommand: null,
      pendingMode: null,
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, inverse],
      confirmedRevision: null,
      error: null,
    };
  }
  if (state.pendingMode === 'redo') {
    return {
      ...state,
      committed: response,
      previewScene: null,
      pendingCommand: null,
      pendingMode: null,
      undoStack: [...state.undoStack, inverse],
      redoStack: state.redoStack.slice(0, -1),
      confirmedRevision: null,
      error: null,
    };
  }
  return {
    ...state,
    committed: response,
    previewScene: null,
    pendingCommand: null,
    pendingMode: null,
    undoStack: [...state.undoStack, inverse],
    redoStack: [],
    confirmedRevision: null,
    error: null,
  };
}