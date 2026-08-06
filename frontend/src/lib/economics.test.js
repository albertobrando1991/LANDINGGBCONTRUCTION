import { filterEconomics, isOverdue, summarizeMargins } from "./economics";

test("filtra tutti i movimenti per cantiere", () => {
  const data = {
    cantieri: [{ cantiere_id: "a" }, { cantiere_id: "b" }],
    spese: [{ cantiere_id: "a" }, { cantiere_id: "b" }],
    incassi: [{ cantiere_id: "b" }],
    scadenze: [{ cantiere_id: "a" }],
  };
  const result = filterEconomics(data, "a");
  expect(result.cantieri).toHaveLength(1);
  expect(result.spese).toHaveLength(1);
  expect(result.incassi).toHaveLength(0);
  expect(result.scadenze).toHaveLength(1);
});

test("calcola margine aggregato senza sommare percentuali", () => {
  const result = summarizeMargins([
    { ricavi_maturati: 1000, costi_registrati: 600 },
    { ricavi_maturati: 500, costi_registrati: 300 },
  ]);
  expect(result.margine).toBe(600);
  expect(result.margine_percentuale).toBe(40);
});

test("riconosce solo scadenze aperte oltre la data", () => {
  const today = new Date("2026-08-06T12:00:00");
  expect(
    isOverdue({ stato: "aperta", data_scadenza: "2026-08-05" }, today),
  ).toBe(true);
  expect(
    isOverdue({ stato: "completata", data_scadenza: "2026-08-05" }, today),
  ).toBe(false);
});
