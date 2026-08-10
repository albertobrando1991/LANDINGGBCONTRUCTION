import {
  clampPlanView,
  closestElement,
  metersFor,
  normalizedLength,
  panPlanBy,
  planToViewport,
  roomMetrics,
  viewportToPlan,
  zoomPlanAt,
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
    { id: "muro", tipo: "muro", x1: 0.1, y1: 0.1, x2: 0.3, y2: 0.1 },
    { id: "quota", tipo: "quota", x1: 0.7, y1: 0.7, x2: 0.9, y2: 0.7 },
  ];

  expect(closestElement(elements, { x: 0.8, y: 0.7 })?.id).toBe("quota");
  expect(closestElement(elements, { x: 0.12, y: 0.11 })?.id).toBe("muro");
  expect(closestElement(elements, { x: 0.5, y: 0.5 })).toBeNull();
});

test("riconosce un ambiente toccandone l'interno", () => {
  const elements = [
    {
      id: "camera",
      tipo: "ambiente",
      x1: 0.1,
      y1: 0.1,
      x2: 0.6,
      y2: 0.5,
    },
  ];

  expect(closestElement(elements, { x: 0.2, y: 0.3 })?.id).toBe("camera");
  expect(closestElement(elements, { x: 0.8, y: 0.8 })).toBeNull();
});

test("preferisce una linea precisa a un ambiente sottostante", () => {
  const elements = [
    {
      id: "camera",
      tipo: "ambiente",
      x1: 0.1,
      y1: 0.1,
      x2: 0.8,
      y2: 0.8,
    },
    { id: "muro", tipo: "muro", x1: 0.2, y1: 0.4, x2: 0.7, y2: 0.4 },
  ];

  expect(closestElement(elements, { x: 0.6, y: 0.405 })?.id).toBe("muro");
});

test("zoom e spostamento mantengono le coordinate della planimetria", () => {
  const point = { x: 0.3, y: 0.7 };
  const view = { zoom: 2.5, x: 0.2, y: -0.15 };

  expect(viewportToPlan(planToViewport(point, view), view)).toEqual(point);
});

test("lo zoom conserva il punto sotto le dita", () => {
  const focal = { x: 0.2, y: 0.75 };
  const before = { zoom: 1.5, x: 0.1, y: -0.1 };
  const planPoint = viewportToPlan(focal, before);
  const after = zoomPlanAt(before, 3, focal);

  expect(planToViewport(planPoint, after).x).toBeCloseTo(focal.x);
  expect(planToViewport(planPoint, after).y).toBeCloseTo(focal.y);
});

test("limita zoom e trascinamento senza perdere la tavola", () => {
  expect(clampPlanView({ zoom: 99, x: 99, y: -99 })).toEqual({
    zoom: 5,
    x: 2,
    y: -2,
  });
  expect(panPlanBy({ zoom: 2, x: 0, y: 0 }, { x: 2, y: -2 })).toEqual({
    zoom: 2,
    x: 0.5,
    y: -0.5,
  });
});

test("consente di spostare la planimetria anche a zoom 100%", () => {
  expect(panPlanBy({ zoom: 1, x: 0, y: 0 }, { x: 0.12, y: -0.08 })).toEqual({
    zoom: 1,
    x: 0.12,
    y: -0.08,
  });

  expect(panPlanBy({ zoom: 1, x: 0, y: 0 }, { x: 2, y: -2 })).toEqual({
    zoom: 1,
    x: 0.2,
    y: -0.2,
  });
});
