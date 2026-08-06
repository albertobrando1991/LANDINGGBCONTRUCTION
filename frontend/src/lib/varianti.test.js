import { filterRigheVariante, formatDelta } from "./varianti";

const righe = [
  { classificazione: "modificata" },
  { classificazione: "nuova" },
  { classificazione: "invariata" },
];

test("filtra il quadro variante per classificazione", () => {
  expect(filterRigheVariante(righe, "nuova")).toEqual([righe[1]]);
  expect(filterRigheVariante(righe, "tutte")).toEqual(righe);
});

test("formatta il delta economico con segno esplicito", () => {
  expect(formatDelta(125.5)).toBe("+125,50");
  expect(formatDelta(-10)).toBe("−10,00");
  expect(formatDelta(0)).toBe("0,00");
});
