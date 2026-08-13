import { formatArrivalDateTime } from "./format";

describe("formatArrivalDateTime", () => {
  test("mostra data e ora di arrivo nel fuso italiano", () => {
    expect(formatArrivalDateTime("2026-08-13T09:30:00Z")).toMatch(
      /13 ago 2026, 11:30/,
    );
  });

  test("gestisce valori mancanti o non validi", () => {
    expect(formatArrivalDateTime()).toBe("—");
    expect(formatArrivalDateTime("non-valida")).toBe("—");
  });
});
