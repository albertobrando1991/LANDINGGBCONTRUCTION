import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import client from "@/lib/api";
import CantierePresenze from "./CantierePresenze";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
  extractErrorDetail: jest.fn(async () => "Errore"),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

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
    await new Promise((resolve) => setTimeout(resolve, 25));
  });
  expect(container.textContent).toContain("Squadra Alfa");
  expect(container.textContent).toContain("4 presenti");
  await act(async () => root.unmount());
});
