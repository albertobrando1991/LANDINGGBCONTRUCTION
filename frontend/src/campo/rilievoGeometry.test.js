import {
  closestElement,
  metersFor,
  normalizedLength,
  roomMetrics,
} from "./rilievoGeometry";

test("calcola una quota in metri dalla calibrazione normalizzata", () => {
  const calibration = { metri: 4, distanza_normalizzata: 0.4 };
  const quota = { x1: 0.1, y1: 0.2, x2: 0.4, y2: 0.2 };

  expect(normalizedLength(quota)).toBeCloseTo(0.3);
  expect(metersFor(quota, calibration)).toBe(3);
});

test("considera il rapporto del canvas nelle quote verticali", () => {
  const calibration = { metri: 4, distanza_normalizzata: 0.2 };
  const quotaVerticale = { x1: 0.2, y1: 0.1, x2: 0.2, y2: 0.3 };

  expect(metersFor(quotaVerticale, calibration, 0.5)).toBe(2);
});

test("calcola lati e superficie di un ambiente calibrato", () => {
  const calibration = { metri: 4, distanza_normalizzata: 0.4 };
  const room = { x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 };

  expect(roomMetrics(room, calibration, 0.75)).toEqual({
    width: 4,
    height: 3,
    area: 12,
  });
});

test("non inventa misure quando la tavola non e calibrata", () => {
  expect(metersFor({ x1: 0, y1: 0, x2: 1, y2: 0 }, null)).toBeNull();
});

test("seleziona l'elemento piu vicino al punto indicato", () => {
  const elements = [
    { id: "muro", x1: 0.1, y1: 0.1, x2: 0.3, y2: 0.1 },
    { id: "quota", x1: 0.7, y1: 0.7, x2: 0.9, y2: 0.7 },
  ];

  expect(closestElement(elements, { x: 0.8, y: 0.7 })?.id).toBe("quota");
  expect(closestElement(elements, { x: 0.5, y: 0.5 })).toBeNull();
});
