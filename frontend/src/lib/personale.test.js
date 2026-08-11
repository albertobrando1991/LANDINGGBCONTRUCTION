import {
  assegnazioneMatchesCantiere,
  filterPersonale,
  formatRuoloLabel,
  groupAssegnazioniPerCantiere,
  isAssegnazioneAttiva,
} from "./personale";

test("filtra personale per tipo e stato attivo", () => {
  const rows = [
    { id: "1", tipo: "interno", attivo: true },
    { id: "2", tipo: "subappaltatore", attivo: true },
    { id: "3", tipo: "interno", attivo: false },
  ];
  expect(filterPersonale(rows, { tipo: "interno", attivo: true })).toEqual([
    rows[0],
  ]);
});

test("raggruppa le assegnazioni per cantiere", () => {
  const grouped = groupAssegnazioniPerCantiere([
    { id: "a", cantiere_id: "c1" },
    { id: "b", cantiere_id: "c1" },
    { id: "c", cantiere_id: "c2" },
  ]);
  expect(grouped.get("c1")).toHaveLength(2);
  expect(grouped.get("c2")).toHaveLength(1);
});

test("riconosce assegnazioni correnti senza considerare concluse o future", () => {
  const today = new Date("2026-08-11T12:00:00");
  expect(
    isAssegnazioneAttiva(
      { stato: "in_corso", data_da: "2026-08-01", data_a: null },
      today,
    ),
  ).toBe(true);
  expect(
    isAssegnazioneAttiva(
      { stato: "concluso", data_da: "2026-08-01", data_a: null },
      today,
    ),
  ).toBe(false);
  expect(
    isAssegnazioneAttiva(
      { stato: "assegnato", data_da: "2026-08-20", data_a: null },
      today,
    ),
  ).toBe(false);
});

test("fornisce una label di ruolo e supporta gli id cantiere legacy", () => {
  expect(formatRuoloLabel("interno", "")).toBe("Personale interno");
  expect(formatRuoloLabel("subappaltatore", "Elettricisti")).toBe(
    "Elettricisti",
  );
  expect(
    assegnazioneMatchesCantiere(
      { cantiere_id: "uuid", cantiere_legacy_id: "legacy" },
      "legacy",
    ),
  ).toBe(true);
});
