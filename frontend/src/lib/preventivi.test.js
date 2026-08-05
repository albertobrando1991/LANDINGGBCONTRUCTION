import {
  azioniPerPreventivo,
  etichettaEventoPreventivo,
  preventivoGestibile,
} from "./preventivi";

test("consente le transizioni terminali solo dopo l'invio", () => {
  expect(azioniPerPreventivo("inviato").map((azione) => azione.stato)).toEqual([
    "accettato",
    "rifiutato",
    "scaduto",
  ]);
  expect(azioniPerPreventivo("bozza")).toEqual([]);
  expect(azioniPerPreventivo("accettato")).toEqual([]);
});

test("limita la gestione del ciclo ai preventivi EdilOS", () => {
  expect(preventivoGestibile({ source: "edilos" })).toBe(true);
  expect(preventivoGestibile({ source: "legacy" })).toBe(false);
  expect(preventivoGestibile({})).toBe(false);
});

test("rende leggibili gli eventi dello storico", () => {
  expect(etichettaEventoPreventivo({ tipo: "email_inviata" })).toBe(
    "Email inviata",
  );
  expect(etichettaEventoPreventivo({ tipo: "stato" })).toBe("Stato aggiornato");
});
