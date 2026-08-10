import {
  applyRilievoLeadSelection,
  normalizeRilievoLeads,
  rilievoLeadLabel,
} from "./rilievoLeadSelection";

const BASE_FORM = {
  lead_id: "",
  sopralluogo_legacy_id: "",
  cliente: "Cliente manuale",
  indirizzo: "Indirizzo manuale",
};

describe("selezione lead per il primo rilievo", () => {
  const leads = [
    {
      id: "lead-2",
      nome: "Zeno Bianchi",
      email: "zeno@example.it",
      citta: "Napoli",
    },
    {
      id: "lead-1",
      nome: "Anna Rossi",
      telefono: "+39 333 0000000",
      indirizzo: "Via Roma 10",
      citta: "Caserta",
    },
  ];

  test("ordina i lead e mostra dati utili per distinguerli", () => {
    const normalized = normalizeRilievoLeads([
      ...leads,
      { id: "senza-nome" },
      { nome: "Senza id" },
    ]);

    expect(normalized.map((lead) => lead.id)).toEqual(["lead-1", "lead-2"]);
    expect(rilievoLeadLabel(normalized[0])).toBe(
      "Anna Rossi · Caserta · +39 333 0000000",
    );
  });

  test("precompila cliente e indirizzo collegando il lead selezionato", () => {
    expect(
      applyRilievoLeadSelection(
        { ...BASE_FORM, sopralluogo_legacy_id: "appuntamento-1" },
        "lead-1",
        leads,
      ),
    ).toEqual({
      ...BASE_FORM,
      lead_id: "lead-1",
      sopralluogo_legacy_id: "",
      cliente: "Anna Rossi",
      indirizzo: "Via Roma 10",
    });
  });

  test("mantiene i dati digitati quando si torna all'inserimento manuale", () => {
    expect(
      applyRilievoLeadSelection(
        {
          ...BASE_FORM,
          lead_id: "lead-1",
          sopralluogo_legacy_id: "appuntamento-1",
        },
        "",
        leads,
      ),
    ).toEqual(BASE_FORM);
  });
});
