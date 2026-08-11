import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LeadPortalAccess from "./LeadPortalAccess";
import client from "@/lib/api";
import { toast } from "sonner";

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
    success: jest.fn(),
    error: jest.fn(),
  },
}));

async function flushQueries() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("LeadPortalAccess", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  async function renderCard(data) {
    client.get.mockResolvedValue({ data });
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <LeadPortalAccess
            leadId="64b64c8f2f9b2d7a1c000001"
            email="cliente@example.com"
          />
        </QueryClientProvider>,
      );
    });
    await flushQueries();
  }

  test("per un accesso esistente offre il reinvio e mostra il pagamento", async () => {
    const portal = {
      available: true,
      accesso_attivo: true,
      pagamento_confermato: true,
      modalita_pagamento: "sal",
      numero_preventivo: "PREV-2026-0042",
      cliente_email: "cliente@example.com",
    };
    client.post.mockResolvedValue({ data: { ...portal, invited: false } });

    await renderCard(portal);

    expect(container.textContent).toContain("Pagamento a SAL");
    const button = container.querySelector(
      '[data-testid="lead-portal-invite"]',
    );
    expect(button.textContent).toContain("Reinvia email di accesso");

    await act(async () => {
      button.click();
      await Promise.resolve();
    });
    await flushQueries();

    expect(client.post).toHaveBeenCalledWith(
      "/leads/64b64c8f2f9b2d7a1c000001/portale/invita",
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Email di accesso inviata nuovamente",
    );
  });

  test("per il primo accesso offre l'invio e segnala il pagamento da confermare", async () => {
    await renderCard({
      available: true,
      accesso_attivo: false,
      pagamento_confermato: false,
      numero_preventivo: "PREV-2026-0043",
      cliente_email: "cliente@example.com",
    });

    expect(container.textContent).toContain("Pagamento da confermare");
    expect(
      container.querySelector('[data-testid="lead-portal-invite"]').textContent,
    ).toContain("Invia email di accesso");
  });

  test("senza preventivo spiega il prerequisito e non espone l'invio", async () => {
    await renderCard({
      available: false,
      accesso_attivo: false,
      pagamento_confermato: false,
    });

    expect(container.textContent).toContain(
      "Crea prima un preventivo collegato al lead",
    );
    expect(
      container.querySelector('[data-testid="lead-portal-invite"]'),
    ).toBeNull();
  });
});
