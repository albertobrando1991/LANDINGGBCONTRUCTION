import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Pipeline from "./Pipeline";
import client from "@/lib/api";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    patch: jest.fn(),
  },
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
  },
}));

const leads = Array.from({ length: 8 }, (_, index) => ({
  id: `lead-${index + 1}`,
  nome: `Cliente ${index + 1}`,
  citta: "Napoli",
  score: 60,
  range_basso: 10000,
  range_alto: 20000,
  giorni_in_stato: index,
  created_at: "2026-08-19T08:00:00Z",
}));

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function setInputValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  ).set;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("ricerca e paginazione pipeline", () => {
  let container;
  let root;
  let queryClient;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    client.get.mockResolvedValue({
      data: {
        columns: [
          {
            key: "nuovo",
            label: "Nuovo",
            count: leads.length,
            valore: 120000,
            leads,
          },
        ],
      },
    });
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    queryClient.clear();
    container.remove();
  });

  test("mostra sei lead, cambia pagina e filtra per nome", async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <Pipeline />
        </QueryClientProvider>,
      );
    });
    await flush();

    expect(
      container.querySelectorAll("[data-testid^='kanban-card-']"),
    ).toHaveLength(6);
    expect(
      container.querySelector("[data-testid='kanban-card-lead-7']"),
    ).toBeNull();

    const next = container.querySelector(
      '[aria-label="Pagina successiva per Nuovo"]',
    );
    expect(next).not.toBeNull();
    await act(async () => next.click());

    expect(
      container.querySelectorAll("[data-testid^='kanban-card-']"),
    ).toHaveLength(2);
    expect(
      container.querySelector("[data-testid='kanban-card-lead-7']"),
    ).not.toBeNull();

    const search = container.querySelector("#pipeline-lead-search");
    await act(async () => setInputValue(search, "Cliente 3"));

    expect(
      container.querySelectorAll("[data-testid^='kanban-card-']"),
    ).toHaveLength(1);
    expect(
      container.querySelector("[data-testid='kanban-card-lead-3']"),
    ).not.toBeNull();
    expect(container.textContent).toContain("1 lead trovato");
    expect(
      container.querySelector('[aria-label="Pagina successiva per Nuovo"]'),
    ).toBeNull();
  });
});
