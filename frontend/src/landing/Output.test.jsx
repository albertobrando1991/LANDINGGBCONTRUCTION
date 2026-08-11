import React, { act } from "react";
import { createRoot } from "react-dom/client";
import Output from "./Output";

jest.mock("framer-motion", () => {
  const React = require("react");
  const cache = {};
  return {
    motion: new Proxy(
      {},
      {
        get: (_, tag) => {
          if (!cache[tag]) {
            cache[tag] = React.forwardRef(
              (
                {
                  initial,
                  animate,
                  whileInView,
                  viewport,
                  transition,
                  ...props
                },
                ref,
              ) => React.createElement(tag, { ...props, ref }),
            );
          }
          return cache[tag];
        },
      },
    ),
  };
});

jest.mock("@/components/Tilt3D", () => ({ children }) => <>{children}</>);
jest.mock("@/lib/assets", () => ({
  WHATSAPP: "https://wa.me/390000000000",
  PROPOSAL_POSTERS: {
    essenziale: "/brand/gb-essenziale.png",
    premium: "/brand/gb-premium.png",
    luxury: "/brand/gb-luxury.png",
  },
}));
jest.mock("@/lib/api", () => ({ BACKEND_URL: "http://localhost:8000" }));
jest.mock("@/lib/booking", () => ({ openBooking: jest.fn() }));

const estimate = {
  input: { mq: 90, bagni: 2, camere: 3 },
  pacchetti: {
    essenziale: { range_basso: 60000, range_alto: 70000 },
    premium: { range_basso: 75000, range_alto: 90000 },
    luxury: { range_basso: 100000, range_alto: 130000 },
  },
};

describe("Output render premium", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  test("sostituisce la falsa generazione automatica con l'offerta da 300 euro", async () => {
    const onStart = jest.fn();

    await act(async () => {
      root.render(
        <Output estimate={estimate} onStartRenderRequest={onStart} />,
      );
    });

    expect(container.textContent).not.toContain(
      "Stiamo generando un'anteprima visiva",
    );
    expect(container.textContent).toContain(
      "Vuoi ricevere un'anteprima visiva del tuo progetto?",
    );
    expect(container.textContent).toContain("€300");
    expect(
      container.querySelectorAll('img[alt^="Esempio render professionale"]'),
    ).toHaveLength(3);

    const button = container.querySelector(
      '[data-testid="render-request-start"]',
    );
    await act(async () => button.click());
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  test("dopo l'invio mostra lo stato e non permette una seconda richiesta", async () => {
    await act(async () => {
      root.render(
        <Output
          estimate={estimate}
          renderRequest={{ id: "request-1", status: "requested" }}
        />,
      );
    });

    expect(
      container.querySelector('[data-testid="render-request-sent"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="render-request-start"]'),
    ).toBeNull();
  });
});
