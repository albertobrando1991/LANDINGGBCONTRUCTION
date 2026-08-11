import {
  isVoceDaClassificare,
  moveVoceIds,
  raggruppaVociPerFase,
  vociDaClassificare,
} from "./computo";

const voci = [{ id: "a" }, { id: "b" }, { id: "c" }];

test("sposta una voce mantenendo l'ordine completo", () => {
  expect(moveVoceIds(voci, 1, -1)).toEqual(["b", "a", "c"]);
  expect(moveVoceIds(voci, 1, 1)).toEqual(["a", "c", "b"]);
});

test("non sposta una voce oltre i limiti", () => {
  expect(moveVoceIds(voci, 0, -1)).toEqual(["a", "b", "c"]);
  expect(moveVoceIds(voci, 2, 1)).toEqual(["a", "b", "c"]);
});

const vociFasi = [
  { id: "a", fase: "Pavimenti e rivestimenti", fase_ordine: 70, totale: 300 },
  { id: "b", fase: "Demolizioni e rimozioni", fase_ordine: 15, totale: 100 },
  { id: "c", fase: "Pavimenti e rivestimenti", fase_ordine: 70, totale: 100 },
];

test("raggruppa per fase in ordine di cantiere con subtotali e incidenza", () => {
  const gruppi = raggruppaVociPerFase(vociFasi);

  expect(gruppi.map((gruppo) => gruppo.fase)).toEqual([
    "Demolizioni e rimozioni",
    "Pavimenti e rivestimenti",
  ]);
  expect(gruppi.map((gruppo) => gruppo.totale)).toEqual([100, 400]);
  expect(gruppi.map((gruppo) => gruppo.incidenza)).toEqual([20, 80]);
});

test("conserva l'indice piatto necessario al riordino", () => {
  const gruppi = raggruppaVociPerFase(vociFasi);

  expect(gruppi[0].voci[0].__index).toBe(1);
  expect(gruppi[1].voci.map((voce) => voce.__index)).toEqual([0, 2]);
  expect(gruppi[1].voci.map((voce) => voce.__posizione)).toEqual([1, 2]);
});

test("le voci senza fase finiscono in Da classificare", () => {
  const gruppi = raggruppaVociPerFase([
    { id: "x", qta: 2, prezzo_unitario: 50 },
  ]);

  expect(gruppi[0].fase).toBe("Da classificare");
  expect(gruppi[0].totale).toBe(100);
});

test("fase ordine 99 resta visibile come Da classificare anche con un nome fase", () => {
  const voce = {
    id: "x",
    fase: "Importazione ACCA",
    fase_ordine: 99,
    totale: 100,
  };

  expect(isVoceDaClassificare(voce)).toBe(true);
  expect(vociDaClassificare([voce])).toEqual([voce]);
  expect(raggruppaVociPerFase([voce])[0]).toMatchObject({
    fase: "Da classificare",
    fase_ordine: 99,
  });
});

test("separa soltanto le voci che richiedono davvero una fase", () => {
  const classificata = {
    id: "ok",
    fase: "Demolizioni e rimozioni",
    fase_ordine: 15,
  };
  const senzaNome = { id: "vuota", fase: "", fase_ordine: null };
  const esplicita = {
    id: "manuale",
    fase: "Da classificare",
    fase_ordine: 99,
  };

  expect(vociDaClassificare([classificata, senzaNome, esplicita])).toEqual([
    senzaNome,
    esplicita,
  ]);
});

test("una fase valida senza ordine non diventa un falso positivo", () => {
  const voce = { id: "legacy", fase: "Impianto elettrico e speciali" };

  expect(isVoceDaClassificare(voce)).toBe(false);
  expect(vociDaClassificare([voce])).toEqual([]);
});

test("usa gli id canonici del backend quando disponibili", () => {
  const elenco = [
    { id: "a", fase: "Da classificare", fase_ordine: 99 },
    { id: "b", fase: "Da classificare", fase_ordine: 99 },
  ];

  expect(vociDaClassificare(elenco, ["b"])).toEqual([elenco[1]]);
});
