import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Preventivi from "./Preventivi";
import client from "@/lib/api";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    delete: jest.fn(),
  },
  extractErrorDetail: jest.fn(async () => "Errore inatteso"),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("@/dashboard/NuovoPreventivoModal", () => () => null);
jest.mock("@/dashboard/PreventivoLifecycleModal", () => () => null);

const EDILOS = {
  id: "20000000-0000-4000-8000-000000000001",
  computo_id: "10000000-0000-4000-8000-000000000001",
  numero: "P-001",
  cliente: "Cliente EdilOS",
  source: "edilos",
  stato_documento: "bozza",
  computo_stato: "bozza",
  status: "preventivo_preparazione",
  range_basso: 25000,
};

const LEGACY = {
  id: "64b64c8f2f9b2d7a1c000001",
  cliente: "Cliente Legacy",
  status: "preventivo_preparazione",
  range_basso: 15000,
};

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("eliminazione preventivi", () => {
  let container;
  let root;
  let confirmSpy;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    client.get.mockResolvedValue({ data: [EDILOS, LEGACY] });
    client.delete.mockResolvedValue({
      data: { contratti_eliminati: 1, documenti_eliminati: 2 },
    });
    confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    confirmSpy.mockRestore();
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
          <Preventivi />
        </QueryClientProvider>,
      );
    });
    await flush();
  }

  test("elimina un preventivo EdilOS con il relativo fascicolo", async () => {
    await renderPage();

    const button = container.querySelector(
      '[aria-label="Elimina preventivo P-001"]',
    );
    expect(button).not.toBeNull();
    await act(async () => button.click());
    await flush();

    expect(confirmSpy.mock.calls[0][0]).toContain("contratto");
    expect(client.delete).toHaveBeenCalledWith(
      `/preventivi/${EDILOS.id}`,
    );
  });

  test("usa il flusso con artefatti per un preventivo legacy", async () => {
    await renderPage();

    const button = container.querySelector(
      '[aria-label="Elimina preventivo Cliente Legacy"]',
    );
    await act(async () => button.click());
    await flush();

    expect(confirmSpy.mock.calls[0][0]).toContain("lead collegato");
    expect(client.delete).toHaveBeenCalledWith(
      `/leads/${LEGACY.id}/with-artifacts`,
    );
  });
});
