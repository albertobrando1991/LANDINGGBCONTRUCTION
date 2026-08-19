import {
  filterLeadsByName,
  paginatePipelineLeads,
  PIPELINE_PAGE_SIZE,
} from "./pipelineView";

test("filtra i lead esclusivamente per nome ignorando accenti e maiuscole", () => {
  const leads = [
    { id: "1", nome: "Giovanni D'Angiò", citta: "Napoli" },
    { id: "2", nome: "Maria Rossi", citta: "Giovanni" },
    { id: "3", nome: "Antonio Verdi", citta: "Roma" },
  ];

  expect(filterLeadsByName(leads, "  angio ")).toEqual([leads[0]]);
  expect(filterLeadsByName(leads, "GIOVANNI")).toEqual([leads[0]]);
  expect(filterLeadsByName(leads, "roma")).toEqual([]);
});

test("mostra sei lead per pagina e mantiene corretti limiti e pagine", () => {
  const leads = Array.from({ length: 13 }, (_, index) => ({
    id: String(index + 1),
  }));

  const first = paginatePipelineLeads(leads, 1);
  const second = paginatePipelineLeads(leads, 2);
  const last = paginatePipelineLeads(leads, 99);

  expect(PIPELINE_PAGE_SIZE).toBe(6);
  expect(first.items).toHaveLength(6);
  expect(first).toMatchObject({ page: 1, totalPages: 3, start: 1, end: 6 });
  expect(second.items.map((lead) => lead.id)).toEqual([
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
  ]);
  expect(last.items.map((lead) => lead.id)).toEqual(["13"]);
  expect(last).toMatchObject({ page: 3, start: 13, end: 13 });
});
