import { moveVoceIds } from "./computo";

const voci = [{ id: "a" }, { id: "b" }, { id: "c" }];

test("sposta una voce mantenendo l'ordine completo", () => {
  expect(moveVoceIds(voci, 1, -1)).toEqual(["b", "a", "c"]);
  expect(moveVoceIds(voci, 1, 1)).toEqual(["a", "c", "b"]);
});

test("non sposta una voce oltre i limiti", () => {
  expect(moveVoceIds(voci, 0, -1)).toEqual(["a", "b", "c"]);
  expect(moveVoceIds(voci, 2, 1)).toEqual(["a", "b", "c"]);
});
