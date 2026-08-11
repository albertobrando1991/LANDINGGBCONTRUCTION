import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Cantieri, {
  CantiereCard,
  CantiereSummaryCard,
  filterCantieri,
} from "./Cantieri";
import client from "@/lib/api";
import { toast } from "sonner";

let mockUser = { role: "admin", name: "Admin GB" };

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
  formatApiErrorDetail: jest.fn((detail) => detail || "Errore inatteso"),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));
jest.mock("react-router-dom", () => {
  const actualReact = jest.requireActual("react");
  return {
    Link: ({ to, children, ...props }) =>
      actualReact.createElement("a", { href: to, ...props }, children),
  };
});

jest.mock("@/dashboard/CantiereDocuments", () => () => null);
jest.mock("@/dashboard/CantierePortalAccess", () => () => null);
jest.mock("@/dashboard/CantiereQuickPhotoModal", () => () => null);
jest.mock("@/dashboard/CantierePresenze", () => () => null);
jest.mock("@/campo/DictationHint", () => () => null);

const CANTIERE = {
  id: "64b64c8f2f9b2d7a1c000001",
  cliente: "Cliente Demo",
  indirizzo: "Via Roma 1",
  importo: 85000,
  avanzamento: 30,
  milestone: "Impianti",
  milestone_data: "2026-08-20",
  capocantiere: "Giovanni",
  criticita: null,
  stato: "attivo",
  updated_at: "2026-08-11T10:00:00Z",
  fasi: [{ nome: "Demolizioni", stato: "completata" }],
};

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

describe("elenco compatto dei cantieri", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    mockUser = { role: "admin", name: "Admin GB" };
    client.get.mockImplementation((url) => {
      if (url === "/cantieri") return Promise.resolve({ data: [CANTIERE] });
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
          <Cantieri />
        </QueryClientProvider>,
      );
    });
    await flush();
  }

  test("mostra una sintesi che apre la schermata dedicata", async () => {
    await renderPage();

    const summary = container.querySelector(
      `[data-testid="cantiere-summary-${CANTIERE.id}"]`,
    );
    expect(summary).not.toBeNull();
    expect(summary.textContent).toContain("Cliente Demo");
    expect(summary.textContent).toContain("30%");
    expect(
      summary.querySelector(`a[href="/dashboard/cantieri/${CANTIERE.id}"]`),
    ).not.toBeNull();
    expect(
      container.querySelector(`[data-testid="delete-cantiere-${CANTIERE.id}"]`),
    ).toBeNull();
  });

  test("la card compatta non incorpora i moduli operativi", async () => {
    await act(async () => {
      root.render(<CantiereSummaryCard cantiere={CANTIERE} />);
    });

    expect(container.textContent).not.toContain("Presenze giornaliere");
    expect(container.textContent).not.toContain("Squadra assegnata");
    expect(
      container.querySelector('[aria-label="Milestone cantiere"]'),
    ).toBeNull();
  });

  test("l'elenco resta disponibile anche ai ruoli staff", async () => {
    mockUser = { role: "staff", name: "Staff GB" };
    await renderPage();

    expect(
      container.querySelector(
        `[data-testid="cantiere-summary-${CANTIERE.id}"]`,
      ),
    ).not.toBeNull();
    expect(client.delete).not.toHaveBeenCalled();
  });
});

describe("integrita e azioni rapide della scheda panoramica", () => {
  let container;
  let root;
  let props;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    props = {
      cantiere: CANTIERE,
      staffNames: ["Giovanni"],
      onSave: jest.fn().mockResolvedValue(CANTIERE),
      onAtomicSave: jest.fn().mockResolvedValue(CANTIERE),
      onComplete: jest.fn(),
      onDelete: jest.fn(),
      saving: false,
      deleting: false,
      canDelete: false,
      quickPhotoEnabled: false,
    };
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  const renderCard = async (nextProps = props) => {
    await act(async () => {
      root.render(<CantiereCard {...nextProps} />);
    });
    await flush();
  };

  test("la bozza sporca sopravvive al rerender con un nuovo oggetto", async () => {
    await renderCard();
    const milestone = container.querySelector(
      '[aria-label="Milestone cantiere"]',
    );
    const setValue = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    ).set;
    await act(async () => {
      setValue.call(milestone, "Milestone locale");
      milestone.dispatchEvent(new Event("input", { bubbles: true }));
    });

    await renderCard({ ...props, cantiere: { ...CANTIERE } });

    expect(
      container.querySelector('[aria-label="Milestone cantiere"]').value,
    ).toBe("Milestone locale");
    expect(
      container.querySelector(`[data-testid="save-status-${CANTIERE.id}"]`)
        .textContent,
    ).toContain("Modifiche non salvate");
  });

  test("ripristina lo stato fase se il salvataggio atomico fallisce", async () => {
    let rejectSave;
    props.onAtomicSave.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectSave = reject;
      }),
    );
    await renderCard();
    const phase = container.querySelector(
      '[aria-label^="Demolizioni, Completata"]',
    );

    await act(async () => phase.click());
    expect(container.textContent).toContain("Da iniziare");

    await act(async () => {
      rejectSave(new Error("rete assente"));
      await Promise.resolve();
    });
    await flush();

    expect(container.textContent).toContain("Completata");
    expect(props.onAtomicSave).toHaveBeenCalledWith(CANTIERE.id, {
      fasi: [{ nome: "Demolizioni", stato: "da_iniziare" }],
    });
    expect(toast.error).toHaveBeenCalledWith(
      "Stato fase non aggiornato",
      expect.any(Object),
    );
  });

  test("offre annulla per cinque secondi dopo il cambio fase", async () => {
    await renderCard();
    const phase = container.querySelector(
      '[aria-label^="Demolizioni, Completata"]',
    );
    await act(async () => phase.click());
    await flush();

    expect(toast.success).toHaveBeenCalledWith("Demolizioni: Da iniziare", {
      duration: 5000,
      action: expect.objectContaining({ label: "Annulla" }),
    });
    const options = toast.success.mock.calls.find(
      ([message]) => message === "Demolizioni: Da iniziare",
    )[1];
    await act(async () => options.action.onClick());
    await flush();

    expect(props.onAtomicSave).toHaveBeenLastCalledWith(CANTIERE.id, {
      fasi: [{ nome: "Demolizioni", stato: "completata" }],
    });
  });

  test("lascia presenze, squadra e documenti fuori dalla panoramica", async () => {
    await renderCard();

    expect(container.textContent).not.toContain("Presenze giornaliere");
    expect(container.textContent).not.toContain("Squadra assegnata");
    expect(container.textContent).not.toContain("Archivio documenti");
  });
});

test("i filtri criticita, capocantiere e personale sono componibili", () => {
  const list = [
    { id: "1", capocantiere: "Giovanni", criticita: "Materiale in ritardo" },
    { id: "2", capocantiere: "Giovanni", criticita: "" },
    { id: "3", capocantiere: "Vincenzo", criticita: "Permesso" },
  ];
  expect(
    filterCantieri(list, {
      criticalOnly: true,
      foreman: "Giovanni",
      mineOnly: true,
      userName: "giovanni",
    }),
  ).toEqual([list[0]]);
});
