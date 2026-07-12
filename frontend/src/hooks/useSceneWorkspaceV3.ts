import { useCallback, useReducer, useRef } from 'react';

import { ApiError, applySceneCommandV3, createSceneWorkspaceV3, getSceneWorkspaceV3 } from '../api/client';
import type { MathSceneV3, SceneCommand, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import {
  emptySceneWorkspaceStateV3,
  rebaseSceneCommand,
  sceneWorkspaceReducerV3,
  workspaceDisplayScene,
  workspaceIsTrusted,
  type CommandCommitMode,
} from './sceneWorkspaceV3State';

export function useSceneWorkspaceV3() {
  const [state, dispatch] = useReducer(sceneWorkspaceReducerV3, emptySceneWorkspaceStateV3);
  const requestInFlight = useRef(false);

  const hydrate = useCallback((response: SceneWorkspaceResponseV3) => {
    dispatch({ type: 'load', response });
  }, []);

  const create = useCallback(async (scene: MathSceneV3) => {
    const response = await createSceneWorkspaceV3(scene);
    dispatch({ type: 'load', response });
    return response;
  }, []);

  const reload = useCallback(async (sceneId: string) => {
    const response = await getSceneWorkspaceV3(sceneId);
    dispatch({ type: 'load', response });
    return response;
  }, []);

  const commit = useCallback(async (command: SceneCommand, mode: CommandCommitMode = 'normal') => {
    if (requestInFlight.current || !state.committed) return null;
    const rebased = rebaseSceneCommand(command, state.committed.scene);
    requestInFlight.current = true;
    dispatch({ type: 'begin', command: rebased, mode });
    try {
      const response = await applySceneCommandV3(rebased);
      dispatch({ type: 'commit', response });
      return response;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Không thể áp dụng chỉnh sửa scene.';
      dispatch({ type: 'reject', message });
      if (caught instanceof ApiError && caught.code === 'SCENE_EDIT_STALE') {
        const response = await getSceneWorkspaceV3(rebased.scene_id);
        dispatch({ type: 'load', response });
      }
      throw caught;
    } finally {
      requestInFlight.current = false;
    }
  }, [state.committed]);

  const undo = useCallback(() => {
    const command = state.undoStack[state.undoStack.length - 1];
    return command ? commit(command, 'undo') : Promise.resolve(null);
  }, [commit, state.undoStack]);

  const redo = useCallback(() => {
    const command = state.redoStack[state.redoStack.length - 1];
    return command ? commit(command, 'redo') : Promise.resolve(null);
  }, [commit, state.redoStack]);

  return {
    state,
    scene: workspaceDisplayScene(state),
    trusted: workspaceIsTrusted(state),
    hydrate,
    create,
    reload,
    preview: (scene: MathSceneV3) => dispatch({ type: 'preview', scene }),
    clearPreview: () => dispatch({ type: 'clear_preview' }),
    commit,
    undo,
    redo,
    confirm: () => dispatch({ type: 'confirm' }),
  };
}