import { mapLimit, prefersLightMedia, prefersReducedEffects } from "./network";

const originalConnection = Object.getOwnPropertyDescriptor(
  window.navigator,
  "connection",
);
const originalHardwareConcurrency = Object.getOwnPropertyDescriptor(
  window.navigator,
  "hardwareConcurrency",
);
const originalDeviceMemory = Object.getOwnPropertyDescriptor(
  window.navigator,
  "deviceMemory",
);
const originalMatchMedia = window.matchMedia;

function setConnection(value) {
  Object.defineProperty(window.navigator, "connection", {
    value,
    configurable: true,
    writable: true,
  });
}

function setNavigatorCapability(name, value) {
  Object.defineProperty(window.navigator, name, {
    value,
    configurable: true,
  });
}

function restoreNavigatorCapability(name, descriptor) {
  if (descriptor) {
    Object.defineProperty(window.navigator, name, descriptor);
    return;
  }
  delete window.navigator[name];
}

afterEach(() => {
  if (originalConnection) {
    Object.defineProperty(window.navigator, "connection", originalConnection);
  } else {
    delete window.navigator.connection;
  }
  restoreNavigatorCapability(
    "hardwareConcurrency",
    originalHardwareConcurrency,
  );
  restoreNavigatorCapability("deviceMemory", originalDeviceMemory);
  window.matchMedia = originalMatchMedia;
});

test("resta sulla versione pesante quando la Network Information API manca", () => {
  setConnection(undefined);
  expect(prefersLightMedia()).toBe(false);
});

test("alleggerisce quando l'utente ha attivato il risparmio dati", () => {
  setConnection({ saveData: true, effectiveType: "4g" });
  expect(prefersLightMedia()).toBe(true);
});

test.each(["slow-2g", "2g", "3g"])(
  "alleggerisce sulle reti lente (%s)",
  (effectiveType) => {
    setConnection({ saveData: false, effectiveType });
    expect(prefersLightMedia()).toBe(true);
  },
);

test("resta sulla versione pesante su 4g senza risparmio dati", () => {
  setConnection({ saveData: false, effectiveType: "4g" });
  expect(prefersLightMedia()).toBe(false);
});

test("resta sulla versione pesante se effectiveType e sconosciuto", () => {
  setConnection({ saveData: false, effectiveType: undefined });
  expect(prefersLightMedia()).toBe(false);
});

test.each([
  ["CPU", 4, 8],
  ["memoria", 8, 4],
])("riduce gli effetti con %s limitata", (_label, cpu, memory) => {
  setConnection({ saveData: false, effectiveType: "4g" });
  setNavigatorCapability("hardwareConcurrency", cpu);
  setNavigatorCapability("deviceMemory", memory);
  window.matchMedia = jest.fn(() => ({ matches: false }));

  expect(prefersReducedEffects()).toBe(true);
});

test("mantiene gli effetti su un dispositivo capace e senza preferenze ridotte", () => {
  setConnection({ saveData: false, effectiveType: "4g" });
  setNavigatorCapability("hardwareConcurrency", 8);
  setNavigatorCapability("deviceMemory", 8);
  window.matchMedia = jest.fn(() => ({ matches: false }));

  expect(prefersReducedEffects()).toBe(false);
});

test("mapLimit preserva l'ordine e limita le operazioni concorrenti", async () => {
  let active = 0;
  let peak = 0;
  const resolvers = [];
  const promise = mapLimit([1, 2, 3, 4], 2, async (value) => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise((resolve) => resolvers.push(resolve));
    active -= 1;
    return value * 10;
  });

  await Promise.resolve();
  expect(active).toBe(2);
  resolvers.shift()();
  resolvers.shift()();
  await Promise.resolve();
  await Promise.resolve();
  expect(active).toBe(2);
  resolvers.shift()();
  resolvers.shift()();

  await expect(promise).resolves.toEqual([10, 20, 30, 40]);
  expect(peak).toBe(2);
});
