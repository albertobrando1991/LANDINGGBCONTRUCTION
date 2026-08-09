import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardLayout from "./DashboardLayout";

const mockLocation = { pathname: "/dashboard" };
const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => {
  const ReactModule = require("react");
  return {
    Outlet: () => ReactModule.createElement("div", null, "Pagina dashboard"),
    useLocation: () => mockLocation,
    useNavigate: () => mockNavigate,
    NavLink: ({ to, end, className, children, onClick, ...props }) =>
      ReactModule.createElement(
        "a",
        {
          href: to,
          className:
            typeof className === "function"
              ? className({
                  isActive: end ? mockLocation.pathname === to : false,
                })
              : className,
          onClick: (event) => {
            event.preventDefault();
            onClick?.(event);
          },
          ...props,
        },
        children,
      ),
  };
});

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { name: "GB Staff", role: "admin" },
    logout: jest.fn(),
  }),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn().mockResolvedValue({ data: { counts: { nuovo: 2 } } }),
  },
}));

jest.mock("@/lib/computiPrefetch", () => ({
  prefetchComputi: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/dashboard/Avatar", () => ({
  Avatar: () => <span aria-hidden="true">GB</span>,
}));

jest.mock("@/dashboard/EmailComposeModal", () => () => null);

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  DropdownMenuTrigger: ({ children }) => children,
  DropdownMenuLabel: ({ children }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
}));

function tap(element) {
  element.dispatchEvent(
    new MouseEvent("click", { bubbles: true, cancelable: true }),
  );
}

describe("DashboardLayout mobile navigation", () => {
  let container;
  let root;

  beforeEach(async () => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    root = createRoot(container);

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <DashboardLayout />
        </QueryClientProvider>,
      );
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    document.body.style.overflow = "";
  });

  test("apre e chiude il drawer dal pulsante superiore", async () => {
    const toggle = container.querySelector('[data-testid="sidebar-toggle"]');
    expect(toggle).not.toBeNull();
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    await act(async () => tap(toggle));

    expect(
      container.querySelector('#dashboard-mobile-nav[role="dialog"]'),
    ).not.toBeNull();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.body.style.overflow).toBe("hidden");

    await act(async () => {
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    });

    expect(container.querySelector("#dashboard-mobile-nav")).toBeNull();
    expect(document.activeElement).toBe(toggle);
  });

  test("offre un secondo accesso dal menu inferiore e chiude dopo la navigazione", async () => {
    const bottomToggle = container.querySelector(
      '[data-testid="sidebar-toggle-bottom"]',
    );
    expect(bottomToggle).not.toBeNull();
    expect(bottomToggle.getAttribute("aria-controls")).toBe(
      "dashboard-mobile-nav",
    );

    await act(async () => tap(bottomToggle));
    const drawer = container.querySelector("#dashboard-mobile-nav");
    const prezzarioLink = Array.from(drawer.querySelectorAll("a")).find(
      (link) => link.textContent.includes("Prezzario"),
    );
    expect(prezzarioLink).toBeDefined();

    await act(async () => tap(prezzarioLink));

    expect(container.querySelector("#dashboard-mobile-nav")).toBeNull();
    expect(prezzarioLink.getAttribute("href")).toBe("/dashboard/prezzario");
    expect(document.activeElement).toBe(bottomToggle);
  });
});
