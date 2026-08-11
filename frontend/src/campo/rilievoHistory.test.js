import {
  canRedo,
  canUndo,
  createHistory,
  pushState,
  redo,
  undo,
} from "./rilievoHistory";

test("esegue undo e redo conservando gli stati", () => {
  const first = [{ id: "a" }];
  const second = [...first, { id: "b" }];
  let state = pushState(createHistory([]), first);
  state = pushState(state, second);

  expect(canUndo(state)).toBe(true);
  state = undo(state);
  expect(state.present).toBe(first);
  expect(canRedo(state)).toBe(true);
  state = redo(state);
  expect(state.present).toBe(second);
});

test("una nuova modifica dopo undo invalida il future", () => {
  let state = pushState(createHistory([]), [{ id: "a" }]);
  state = pushState(state, [{ id: "a" }, { id: "b" }]);
  state = undo(state);
  state = pushState(state, [{ id: "a" }, { id: "c" }]);

  expect(canRedo(state)).toBe(false);
  expect(redo(state)).toBe(state);
});

test("limita lo storico a trenta stati", () => {
  let state = createHistory([]);
  for (let index = 0; index < 40; index += 1) {
    state = pushState(state, [{ id: String(index) }]);
  }
  expect(state.past).toHaveLength(30);
});
