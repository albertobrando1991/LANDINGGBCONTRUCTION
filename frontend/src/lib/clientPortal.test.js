import {
  portalAssetsByType,
  portalSummary,
  validatePortalAsset,
} from "./clientPortal";

test("calcola il riepilogo del portale", () => {
  expect(
    portalSummary({
      cantieri: [{ avanzamento: 40 }, { avanzamento: 80 }],
      sal: [{ id: "s1" }],
      varianti: [{ approvata: false }, { approvata: true }],
    }),
  ).toEqual({
    cantieri: 2,
    avanzamento: 60,
    salApprovati: 1,
    variantiDaApprovare: 1,
  });
});

test("separa foto e documenti condivisi", () => {
  const grouped = portalAssetsByType([
    { id: "1", tipo: "foto" },
    { id: "2", tipo: "documento" },
  ]);
  expect(grouped.foto).toHaveLength(1);
  expect(grouped.documenti).toHaveLength(1);
});

test("rifiuta asset fuori dal prefisso del cantiere", () => {
  expect(() =>
    validatePortalAsset({
      bucket: "documenti",
      tenant_id: "a0000000-0000-4000-8000-000000000001",
      cantiere_id: "10000000-0000-4000-8000-000000000001",
      storage_path: "a0000000-0000-4000-8000-000000000002/private/file.pdf",
    }),
  ).toThrow("Percorso file non autorizzato");
});
