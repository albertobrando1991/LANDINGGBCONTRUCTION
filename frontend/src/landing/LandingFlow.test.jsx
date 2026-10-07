import React, { act } from "react";
import { createRoot } from "react-dom/client";
import Landing from "./Landing";
import Packages from "./Packages";
import BookingModal from "./BookingModal";
import client from "@/lib/api";
import { openBooking } from "@/lib/booking";

jest.mock("framer-motion", () => {
  const React = require("react");
  const cache = {};
  return {
    AnimatePresence: ({ children }) => <>{children}</>,
    motion: new Proxy({}, { get: (_, tag) => {
      if (!cache[tag]) cache[tag] = React.forwardRef(
        ({ initial, animate, exit, transition, whileInView, viewport, ...props }, ref) =>
          React.createElement(tag, { ...props, ref }),
      );
      return cache[tag];
    } }),
  };
});
jest.mock("@/landing/Navbar", () => () => null);
jest.mock("@/landing/ImmersiveHero", () => () => null);
jest.mock("@/landing/SocialProof", () => () => null);
jest.mock("@/landing/SecondChance", () => () => null);
jest.mock("@/landing/Team", () => () => null);
jest.mock("@/landing/Footer", () => () => null);
jest.mock("@/landing/MobileStickyCTA", () => () => null);
jest.mock("@/landing/Output", () => () => null);
jest.mock("@/landing/ContactGate", () => ({ config }) => <pre data-testid="gate-config">{JSON.stringify(config)}</pre>);
jest.mock("@/components/Tilt3D", () => ({ children }) => <>{children}</>);
jest.mock("@/components/ui/slider", () => ({ Slider: ({ value, onValueChange }) => (
  <input aria-label="Metri quadri" type="range" value={value[0]} onChange={(e) => onValueChange([Number(e.target.value)])} />
) }));
jest.mock("@/lib/api", () => ({ __esModule: true, default: { get: jest.fn(), post: jest.fn() }, formatApiErrorDetail: jest.fn() }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

let container;
let root;
async function click(element) {
  expect(element).not.toBeNull();
  await act(async () => element.click());
  await act(async () => jest.advanceTimersByTime(700));
}
function byTestId(id) { return container.querySelector(`[data-testid="${id}"]`); }

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  jest.useFakeTimers();
  window.matchMedia = jest.fn(() => ({ matches: false, addListener() {}, removeListener() {} }));
  window.scrollTo = jest.fn();
  client.get.mockReset();
  client.post.mockReset();
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  jest.useRealTimers();
});

test("le risposte sopravvivono al ritorno dai dettagli e la destinazione delle CTA resta presente", async () => {
  await act(async () => root.render(<Landing />));
  await click(byTestId("tipo-villa"));
  await click(byTestId("config-next"));
  await click(byTestId("config-next"));
  await click(byTestId("intervento-premium"));
  await click(byTestId("config-next"));
  await click(byTestId("config-next"));
  await click(byTestId("stile-industrial"));
  await click(byTestId("config-next"));
  await click(byTestId("tempo-subito"));
  await click(byTestId("config-next"));
  expect(document.querySelectorAll("#configuratore")).toHaveLength(1);
  expect(container.querySelector("#quick-details").parentElement.hidden).toBe(false);
  await click([...container.querySelectorAll("#quick-details button")].find((button) => button.textContent.includes("Indietro")));
  expect(container.querySelector('[aria-label="Configura la tua stima"]').textContent).toContain("Step 6 di 6");
  expect(byTestId("tempo-subito").className).toContain("bg-brand");
  await click(byTestId("config-next"));
  await click([...container.querySelectorAll("#quick-details button")].find((button) => button.textContent.includes("Salta e continua")));
  expect(JSON.parse(byTestId("gate-config").textContent)).toMatchObject({ tipo_immobile: "villa", livello: "premium", stile: "Industrial loft", tempistiche: "Subito" });
  expect(document.querySelectorAll("#configuratore")).toHaveLength(1);
});

test("la CTA del pacchetto chiude il dialogo e trasferisce il focus al percorso preventivo", async () => {
  await act(async () => root.render(<><Packages /><div id="configuratore" tabIndex={-1}>Configuratore</div></>));
  await click(byTestId("package-essenziale"));
  const dialog = document.querySelector('[role="dialog"]');
  expect(dialog).not.toBeNull();
  await click([...dialog.querySelectorAll("button")].find((button) => button.textContent.includes("Avvia la stima gratuita")));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(document.activeElement).toBe(document.getElementById("configuratore"));
  expect(window.scrollTo).toHaveBeenCalled();
});

test("un errore calendario offre un nuovo tentativo senza dichiarare esaurite le disponibilità", async () => {
  client.get.mockRejectedValueOnce(new Error("Rete non disponibile"))
    .mockResolvedValueOnce({ data: [{ id: "slot-test", date: "2027-01-11", start: "09:00", end: "10:00" }] });
  await act(async () => root.render(<BookingModal />));
  await act(async () => openBooking());
  expect(container.querySelector('[role="alert"]').textContent).toContain("Non riusciamo a caricare");
  expect(container.textContent).not.toContain("non ci sono orari");
  await click([...container.querySelectorAll("button")].find((button) => button.textContent === "Riprova"));
  expect(container.querySelector('[role="alert"]')).toBeNull();
  expect(container.textContent).toContain("09:00");
  expect(client.post).not.toHaveBeenCalled();
});

test("un calendario vuoto offre un contatto diretto senza mostrare un errore tecnico", async () => {
  client.get.mockResolvedValueOnce({ data: [] });
  await act(async () => root.render(<BookingModal />));
  await act(async () => openBooking());
  expect(container.querySelector('[role="alert"]')).toBeNull();
  expect(container.textContent).toContain("non ci sono orari prenotabili online");
  expect(container.querySelector('a[href^="https://wa.me/"]')).not.toBeNull();
  expect(client.post).not.toHaveBeenCalled();
});
