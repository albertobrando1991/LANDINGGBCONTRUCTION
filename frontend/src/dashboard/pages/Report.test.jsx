import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Report from "./Report";
import client, { formatApiErrorDetail } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
  formatApiErrorDetail: jest.fn((detail) => detail || "Errore inatteso"),
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
  },
}));

jest.mock("recharts", () => {
  const ReactModule = require("react");
  const component = (name) =>
    function MockChart({ children }) {
      return ReactModule.createElement("div", { "data-chart": name }, children);
    };
  return {
    ResponsiveContainer: component("responsive"),
    LineChart: component("line-chart"),
    Line: component("line"),
    PieChart: component("pie-chart"),
    Pie: component("pie"),
    Cell: component("cell"),
    BarChart: component("bar-chart"),
    Bar: component("bar"),
    XAxis: component("x-axis"),
    YAxis: component("y-axis"),
    Tooltip: component("tooltip"),
    CartesianGrid: component("grid"),
  };
});

const REPORT_DATA = {
  kpi: {
    lead_ricevuti: 12,
    lead_qualificati: 9,
    sopralluoghi: 6,
    preventivi: 4,
    chiusi_vinti: 2,
    chiusi_persi: 1,
    conversione: 16.7,
    valore_pipeline: 250000,
    valore_chiuso: 180000,
  },
  timeline: [
    { data: "2026-07", lead: 5 },
    { data: "2026-08", lead: 7 },
  ],
  distribuzione: [
    { name: "Premium", value: 8 },
    { name: "Luxury", value: 4 },
  ],
  funnel: [
    { step: "Lead", value: 12, percentuale: 100 },
    { step: "Vinti", value: 2, percentuale: 16.7 },
  ],
  geografia: [{ citta: "Napoli", lead: 8, percentuale: 100 }],
  copertura_geografica: {
    segnalati: 8,
    non_segnalati: 4,
    copertura_percentuale: 66.7,
  },
  persi: [
    {
      id: "lost-1",
      nome: "Cliente perso",
      citta: "Napoli",
      livello: "Premium",
      range: 90000,
      data: "2026-08-08T10:00:00+00:00",
    },
  ],
  meta: {
    period: "180d",
    period_label: "Ultimi 6 mesi",
    generated_at: "2026-08-11T10:00:00+00:00",
    lost_total: 1,
  },
};

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("Report", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    formatApiErrorDetail.mockImplementation(
      (detail) => detail || "Errore inatteso",
    );
    client.get.mockResolvedValue({ data: REPORT_DATA });
    client.post.mockResolvedValue({
      data: {
        insights: "Concentra il follow-up sui preventivi aperti.",
        source: "fallback",
      },
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  async function renderPage() {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <Report />
        </QueryClientProvider>,
      );
    });
    await flush();
  }

  test("carica il periodo predefinito e mostra i KPI", async () => {
    await renderPage();

    expect(client.get).toHaveBeenCalledWith(
      "/reports",
      expect.objectContaining({ params: { period: "180d" } }),
    );
    expect(container.textContent).toContain("Lead ricevuti");
    expect(container.textContent).toContain("12");
    expect(container.textContent).toContain("Cliente perso");
    expect(container.textContent).toContain("Pipeline aperta stimata");
    expect(container.textContent).toContain("Valore chiuso stimato");
    expect(
      container.querySelector('[data-testid="geography-reported"]').textContent,
    ).toContain("8");
    expect(
      container.querySelector('[data-testid="geography-unreported"]')
        .textContent,
    ).toContain("4");
    expect(container.textContent).toContain(
      "I dati mancanti restano separati e non incidono sulla distribuzione.",
    );
  });

  test("separa anche i dati geografici non segnalati restituiti dal vecchio backend", async () => {
    client.get.mockResolvedValue({
      data: {
        ...REPORT_DATA,
        geografia: [
          { citta: "Napoli", lead: 8 },
          { citta: "Altro", lead: 4 },
        ],
        copertura_geografica: undefined,
      },
    });
    await renderPage();

    expect(
      container.querySelector('[data-testid="geography-reported"]').textContent,
    ).toContain("8");
    expect(
      container.querySelector('[data-testid="geography-unreported"]')
        .textContent,
    ).toContain("4");
  });

  test("ricarica dati e insight quando cambia il periodo", async () => {
    await renderPage();
    const select = container.querySelector(
      'select[aria-label="Periodo del report"]',
    );

    await act(async () => {
      select.value = "30d";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();

    expect(client.get).toHaveBeenLastCalledWith(
      "/reports",
      expect.objectContaining({ params: { period: "30d" } }),
    );

    const insightButton = container.querySelector(
      '[data-testid="report-insights"]',
    );
    await act(async () => insightButton.click());
    await flush();

    expect(client.post).toHaveBeenCalledWith("/reports/insights", null, {
      params: { period: "30d" },
    });
    expect(container.textContent).toContain(
      "Concentra il follow-up sui preventivi aperti.",
    );
    expect(container.textContent).toContain(
      "non è stato addebitato alcun credito",
    );
  });

  test("mostra un errore recuperabile quando la richiesta fallisce", async () => {
    client.get.mockRejectedValue({
      response: { data: { detail: "Database non raggiungibile" } },
    });
    await renderPage();

    expect(container.textContent).toContain("Report non disponibile");
    expect(container.textContent).toContain("Database non raggiungibile");
    expect(container.textContent).toContain("Riprova");
  });

  test("gestisce il periodo senza dati con stati vuoti espliciti", async () => {
    client.get.mockResolvedValue({
      data: {
        ...REPORT_DATA,
        kpi: Object.fromEntries(
          Object.keys(REPORT_DATA.kpi).map((key) => [key, 0]),
        ),
        timeline: [],
        distribuzione: [],
        funnel: [],
        geografia: [],
        persi: [],
        meta: { ...REPORT_DATA.meta, lost_total: 0 },
      },
    });
    await renderPage();

    expect(container.textContent).toContain(
      "Nessun lead nel periodo selezionato.",
    );
    expect(container.textContent).toContain("Nessun lead perso nel periodo.");
    expect(
      container.querySelector('[data-testid="report-insights"]').disabled,
    ).toBe(true);
  });
});
