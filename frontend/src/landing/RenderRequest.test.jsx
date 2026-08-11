import React, { act } from "react";
import { createRoot } from "react-dom/client";
import RenderRequest from "./RenderRequest";
import client from "@/lib/api";

jest.mock("framer-motion", () => {
  const React = require("react");
  const cache = {};
  return {
    AnimatePresence: ({ children }) => <>{children}</>,
    motion: new Proxy(
      {},
      {
        get: (_, tag) => {
          if (!cache[tag]) {
            cache[tag] = React.forwardRef(
              ({ initial, animate, exit, transition, ...props }, ref) =>
                React.createElement(tag, { ...props, ref }),
            );
          }
          return cache[tag];
        },
      },
    ),
  };
});

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { post: jest.fn() },
  formatApiErrorDetail: jest.fn((detail) => detail || "Errore inatteso"),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe("RenderRequest pubblico", () => {
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

  test("invia il brief commerciale senza esporre AI Architect", async () => {
    client.post.mockResolvedValue({
      data: {
        id: "64b64c8f2f9b2d7a1c000002",
        status: "requested",
        price_eur: 300,
      },
    });

    await act(async () => {
      root.render(
        <RenderRequest
          baseConfig={{ mq: 95, stile: "Moderno minimal" }}
          leadId="64b64c8f2f9b2d7a1c000001"
          onComplete={jest.fn()}
          onSkip={jest.fn()}
        />,
      );
    });

    expect(container.textContent).not.toMatch(/AI Architect/i);

    const fileInput = container.querySelector('input[type="file"]');
    const plan = new File(["planimetria"], "casa.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(fileInput, "files", {
      configurable: true,
      value: [plan],
    });
    await act(async () => {
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    });

    const continueButton = [...container.querySelectorAll("button")].find(
      (button) => button.textContent.includes("Continua"),
    );
    await act(async () => continueButton.click());

    const submitButton = [...container.querySelectorAll("button")].find(
      (button) => button.textContent.includes("Invia richiesta"),
    );
    await act(async () => {
      submitButton.click();
      await Promise.resolve();
    });

    const [endpoint, payload] = client.post.mock.calls[0];
    expect(endpoint).toBe("/render-requests");
    expect(payload.get("lead_id")).toBe("64b64c8f2f9b2d7a1c000001");
    expect(payload.get("sqm")).toBe("95");
    expect(JSON.parse(payload.get("requested_rooms"))).toEqual([
      "Soggiorno",
      "Cucina",
      "Camera matrimoniale",
      "Bagno",
    ]);
    expect(container.textContent).toContain("Ora se ne occupa il team GB");
    expect(container.textContent).not.toMatch(/AI Architect/i);
  });
});
