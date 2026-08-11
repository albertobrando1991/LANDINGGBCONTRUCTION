import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import client from "@/lib/api";
import CantiereDetail from "./CantiereDetail";

const mockNavigate = jest.fn();
const mockParams = {
  id: "64b64c8f2f9b2d7a1c000001",
  section: "presenze",
};

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { role: "admin", name: "Admin GB" } }),
}));
jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
  formatApiErrorDetail: jest.fn((detail) => detail || "Errore"),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));
jest.mock("react-router-dom", () => {
  const actualReact = jest.requireActual("react");
  return {
    Link: ({ to, children, ...props }) =>
      actualReact.createElement("a", { href: to, ...props }, children),
    useNavigate: () => mockNavigate,
    useParams: () => mockParams,
  };
});
jest.mock("@/dashboard/pages/Cantieri", () => ({
  CantiereCard: () => <div data-testid="overview-card">Panoramica editor</div>,
}));
jest.mock("@/dashboard/CantierePresenze", () => (props) => (
  <div data-testid="presenze-section">
    Presenze dedicate: {String(props.standalone)}
  </div>
));
jest.mock("@/dashboard/CantierePersonale", () => () => (
  <div data-testid="squadra-section">Squadra</div>
));
jest.mock("@/dashboard/CantiereDocuments", () => () => (
  <div data-testid="documenti-section">Documenti</div>
));
jest.mock("@/dashboard/CantierePortalAccess", () => () => (
  <div data-testid="portale-section">Portale</div>
));

const CANTIERE = {
  id: "64b64c8f2f9b2d7a1c000001",
  cliente: "Cliente Demo",
  indirizzo: "Via Roma 1",
  avanzamento: 30,
  stato: "attivo",
};

test("apre la sezione presenze dedicata senza montare la panoramica", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  jest.clearAllMocks();
  client.get.mockImplementation((url) => {
    if (url === `/cantieri/${CANTIERE.id}`) {
      return Promise.resolve({ data: CANTIERE });
    }
    return Promise.resolve({ data: [] });
  });
  const container = document.createElement("div");
  const root = createRoot(container);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <CantiereDetail />
      </QueryClientProvider>,
    );
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 25));
  });

  expect(container.textContent).toContain("Cliente Demo");
  expect(container.textContent).toContain("Presenze dedicate: true");
  expect(container.querySelector('[data-testid="overview-card"]')).toBeNull();
  expect(
    container.querySelector('a[aria-current="page"]').textContent,
  ).toContain("Presenze");
  expect(client.get).toHaveBeenCalledWith("/personale");
  expect(client.get).toHaveBeenCalledWith("/personale/assegnazioni");

  await act(async () => root.unmount());
});
