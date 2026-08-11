export const MAX_RILIEVO_HISTORY = 30;

export function createHistory(present = []) {
  return { past: [], present, future: [] };
}

export function pushState(state, elements) {
  if (elements === state.present) return state;
  return {
    past: [...state.past, state.present].slice(-MAX_RILIEVO_HISTORY),
    present: elements,
    future: [],
  };
}

export function undo(state) {
  if (!state.past.length) return state;
  const present = state.past[state.past.length - 1];
  return {
    past: state.past.slice(0, -1),
    present,
    future: [state.present, ...state.future],
  };
}

export function redo(state) {
  if (!state.future.length) return state;
  return {
    past: [...state.past, state.present].slice(-MAX_RILIEVO_HISTORY),
    present: state.future[0],
    future: state.future.slice(1),
  };
}

export const canUndo = (state) => state.past.length > 0;
export const canRedo = (state) => state.future.length > 0;
