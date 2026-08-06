import { azioneStatoSal, periodoMensile, riepilogoSal } from "./sal";

test("espone solo la prossima transizione SAL valida", () => {
  expect(azioneStatoSal("bozza")).toEqual({
    stato: "emesso",
    label: "Emetti SAL",
  });
  expect(azioneStatoSal("emesso")).toEqual({
    stato: "approvato",
    label: "Segna approvato",
  });
  expect(azioneStatoSal("approvato")).toBeNull();
});

test("calcola il periodo mensile rispettando gli anni bisestili", () => {
  expect(periodoMensile(new Date(2028, 1, 10))).toEqual({
    periodo_da: "2028-02-01",
    periodo_a: "2028-02-29",
  });
});

test("riepiloga avanzamento economico ed eccedenze", () => {
  expect(
    riepilogoSal([
      { stato: "approvato", totale_periodo: 1250, contiene_eccedenze: false },
      { stato: "emesso", totale_periodo: 500.5, contiene_eccedenze: true },
    ]),
  ).toEqual({ totale: 2, maturato: 1750.5, approvati: 1, eccedenze: 1 });
});
