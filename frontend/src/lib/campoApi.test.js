import { buildCampoMeasurementPayload } from "./campoApi";

const CLIENT_UUID = "10000000-0000-4000-8000-000000000001";

test("costruisce un rilievo positivo con i soli campi valorizzati", () => {
  expect(
    buildCampoMeasurementPayload(
      {
        mode: "rilievo",
        qta: "12.345",
        data_misura: "2026-08-05",
        parti: "2",
        descrizione: "  Parete nord  ",
        computo_voce_id: "20000000-0000-4000-8000-000000000001",
        lunghezza: "4.2",
        larghezza: "",
        altezza: "2.8",
      },
      CLIENT_UUID,
    ),
  ).toEqual({
    client_uuid: CLIENT_UUID,
    data_misura: "2026-08-05",
    qta: 12.345,
    parti: 2,
    descrizione: "Parete nord",
    computo_voce_id: "20000000-0000-4000-8000-000000000001",
    lunghezza: 4.2,
    altezza: 2.8,
    foto_paths: [],
  });
});

test("una rettifica diventa una nuova misura negativa", () => {
  const payload = buildCampoMeasurementPayload(
    {
      mode: "rettifica",
      qta: "3",
      data_misura: "2026-08-05",
      parti: "1",
    },
    CLIENT_UUID,
  );
  expect(payload.qta).toBe(-3);
});
