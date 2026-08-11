import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Personale from "./Personale";
import client from "@/lib/api";

let mockUser = { role: "staff", name: "Capocantiere" };

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
  },
  extractErrorDetail: jest.fn(async (error) => error?.message || "Errore"),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const PERSONA = {
  id: "20000000-0000-4000-8000-000000000001",
  tipo: "interno",
  nome: "Mario Rossi",
  ruolo: "Muratore",
  telefono: "3331234567",
  costo_giornaliero: 150,
  costo_orario: 20,
  attivo: true,
};

const CANTIERE = {
  id: "64b64c8f2f9b2d7a1c000001",
  cliente: "Cliente Demo",
};

const ASSEGNAZIONE = {
  id: "30000000-0000-4000-8000-000000000001",
  personale_id: PERSONA.id,
  cantiere_id: "10000000-0000-4000-8000-000000000001",
  cantiere_legacy_id: CANTIERE.id,
  cantiere_cliente: CANTIERE.cliente,
  data_da: "2026-08-01",
  data_a: null,
  stato: "in_corso",
};

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("Personale", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    mockUser = { role: "staff", name: "Capocantiere" };
    client.get.mockImplementation((url) => {
      if (url === "/personale") return Promise.resolve({ data: [PERSONA] });
      if (url === "/personale/assegnazioni")
        return Promise.resolve({ data: [ASSEGNAZIONE] });
      if (url === "/cantieri") return Promise.resolve({ data: [CANTIERE] });
      if (url === "/economics")
        return Promise.resolve({ data: { fornitori: [] } });
      return Promise.resolve({ data: [] });
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
          <Personale />
        </QueryClientProvider>,
      );
    });
    await flush();
  }

  test("lo staff vede squadra e contatti ma non i costi", async () => {
    await renderPage();

    expect(container.textContent).toContain("Mario Rossi");
    expect(container.textContent).toContain("Cliente Demo");
    expect(
      container.querySelector('a[href="tel:+393331234567"]'),
    ).not.toBeNull();
    expect(
      container.querySelector(`[data-testid="personale-costs-${PERSONA.id}"]`),
    ).toBeNull();
    expect(client.get).not.toHaveBeenCalledWith("/economics");
  });

  test("owner e admin vedono i costi operativi", async () => {
    mockUser = { role: "admin", name: "Admin GB" };
    await renderPage();

    expect(
      container.querySelector(`[data-testid="personale-costs-${PERSONA.id}"]`),
    ).not.toBeNull();
    expect(container.textContent).toContain("150,00");
  });
});
