import { formatDecimale, parseDecimale } from "./rilievoNumeri";

test.each([
  ["2,70", 2.7],
  ["2.70", 2.7],
  ["", null],
  [" 2,70 m ", 2.7],
  ["12 mq", 12],
  [0, 0],
])("normalizza %p nel valore metrico %p", (input, expected) => {
  expect(parseDecimale(input)).toEqual({
    ok: true,
    value: expected,
    error: null,
  });
});

test.each(["abc", "-1", "2,7,0", "2.7.0", Infinity])(
  "rifiuta il valore metrico %p",
  (input) => {
    expect(parseDecimale(input)).toEqual({
      ok: false,
      value: null,
      error: "Usa un numero, es. 2,70",
    });
  },
);

test("formatta i decimali per la visualizzazione italiana", () => {
  expect(formatDecimale(2.7)).toBe("2,7");
  expect(formatDecimale(2.71828, 3)).toBe("2,718");
  expect(formatDecimale(null)).toBe("");
});
