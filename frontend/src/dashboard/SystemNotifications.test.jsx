import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SystemNotifications from "./SystemNotifications";
import client from "@/lib/api";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onSelect, ...props }) => (
    <button
      type="button"
      onClick={() => onSelect?.({ preventDefault: jest.fn() })}
      {...props}
    >
      {children}
    </button>
  ),
  DropdownMenuTrigger: ({ children }) => children,
  DropdownMenuLabel: ({ children }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
}));

const notification = {
  id: "0123456789abcdef01234567",
  kind: "lead_sla",
  severity: "urgent",
  title: "Lead da contattare subito",
  message: "Mario Rossi attende una risposta.",
  href: "/dashboard/lead/64b4e3f04bd0c2c5a2a10001",
  occurred_at: new Date().toISOString(),
  read: false,
};

async function settle() {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
}

describe("SystemNotifications", () => {
  let container;
  let root;
  let queryClient;

  beforeEach(async () => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockNavigate.mockReset();
    client.get.mockResolvedValue({
      data: { items: [notification], unread_count: 1 },
    });
    client.post.mockResolvedValue({ data: { ok: true } });
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SystemNotifications />
        </QueryClientProvider>,
      );
    });
    await settle();
  });

  afterEach(async () => {
    queryClient.clear();
    await act(async () => root.unmount());
    container.remove();
  });

  test("mostra il badge reale e apre la destinazione segnando l'avviso come letto", async () => {
    expect(client.get).toHaveBeenCalledWith("/notifications");
    expect(
      container
        .querySelector('[data-testid="notifications-trigger"]')
        .getAttribute("aria-label"),
    ).toBe("1 notifiche da leggere");

    const item = container.querySelector(
      `[data-testid="notification-${notification.id}"]`,
    );
    await act(async () => item.click());

    expect(client.post).toHaveBeenCalledWith(
      `/notifications/${notification.id}/read`,
    );
    expect(mockNavigate).toHaveBeenCalledWith(notification.href);
  });

  test("permette di segnare tutte le notifiche come lette", async () => {
    const readAll = container.querySelector(
      '[data-testid="notifications-read-all"]',
    );
    expect(readAll).not.toBeNull();

    await act(async () => readAll.click());

    expect(client.post).toHaveBeenCalledWith("/notifications/read-all");
  });
});
