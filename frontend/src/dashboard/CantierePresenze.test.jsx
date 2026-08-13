import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import client from "@/lib/api";
import CantierePresenze from "./CantierePresenze";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
    request: jest.fn(),
  },
  extractErrorDetail: jest.fn(async () => "Errore"),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("mostra le presenze giornaliere del cantiere", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  client.get.mockResolvedValue({
    data: {
      totale_unita: 4,
      righe: [
        {
          id: "p1",
          personale_nome: "Squadra Alfa",
          unita_presenti: 4,
          ore_lavorate: 8,
        },
      ],
    },
  });
  const container = document.createElement("div");
  const root = createRoot(container);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <CantierePresenze cantiere={{ id: "c1" }} personale={[]} />
      </QueryClientProvider>,
    );
  });
  await act(async () => {
    container.querySelector("button").click();
    await new Promise((resolve) => setTimeout(resolve, 100));
  });
  expect(container.textContent).toContain("Squadra Alfa");
  expect(container.textContent).toContain("4 presenti");
  await act(async () => root.unmount());
});

test("nella sezione dedicata carica subito e registra una presenza", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  client.get.mockResolvedValue({
    data: {
      totale_unita: 0,
      totale_interni: 0,
      totale_subappaltatori: 0,
      righe: [],
    },
  });
  client.request.mockResolvedValue({ data: { id: "presenza-1" } });
  const container = document.createElement("div");
  const root = createRoot(container);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <CantierePresenze
          cantiere={{ id: "c1" }}
          personale={[
            {
              id: "persona-1",
              nome: "Mario Rossi",
              tipo: "interno",
              attivo: true,
            },
          ]}
          standalone
        />
      </QueryClientProvider>,
    );
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(client.get).toHaveBeenCalledWith("/cantieri/c1/presenze", {
    params: { data: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) },
  });
  expect(container.textContent).toContain("Presenze giornaliere");
  expect(container.textContent).toContain("Interni");

  const select = container.querySelector(
    '[aria-label="Persona o squadra presente"]',
  );
  const setSelectValue = Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype,
    "value",
  ).set;
  await act(async () => {
    setSelectValue.call(select, "persona-1");
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const register = Array.from(container.querySelectorAll("button")).find(
    (button) => button.textContent.includes("Registra"),
  );
  await act(async () => {
    register.click();
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(client.request).toHaveBeenCalledWith(
    expect.objectContaining({
      method: "post",
      url: "/cantieri/c1/presenze",
      data: expect.objectContaining({
        personale_id: "persona-1",
        unita_presenti: 1,
        tipo_giornata: "intera",
        ore_lavorate: 8,
        client_id: expect.any(String),
      }),
    }),
  );
  await act(async () => root.unmount());
});
