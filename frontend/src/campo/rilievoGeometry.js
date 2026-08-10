export function normalizedLength(shape, canvasRatio = 1) {
  return Math.hypot(shape.x2 - shape.x1, (shape.y2 - shape.y1) * canvasRatio);
}

export function metersFor(shape, calibration, canvasRatio = 1) {
  if (!calibration?.metri || !calibration?.distanza_normalizzata) return null;
  return Number(
    (
      (normalizedLength(shape, canvasRatio) * Number(calibration.metri)) /
      Number(calibration.distanza_normalizzata)
    ).toFixed(3),
  );
}

export function roomMetrics(shape, calibration, canvasRatio = 1) {
  if (!calibration?.metri || !calibration?.distanza_normalizzata) return null;
  const scale =
    Number(calibration.metri) / Number(calibration.distanza_normalizzata);
  const width = Math.abs(shape.x2 - shape.x1) * scale;
  const height = Math.abs(shape.y2 - shape.y1) * canvasRatio * scale;
  return {
    width: Number(width.toFixed(3)),
    height: Number(height.toFixed(3)),
    area: Number((width * height).toFixed(3)),
  };
}

export const MIN_PLAN_ZOOM = 1;
export const MAX_PLAN_ZOOM = 5;
const MIN_PLAN_PAN = 0.2;

export function clampPlanView(view) {
  const zoom = Math.max(
    MIN_PLAN_ZOOM,
    Math.min(MAX_PLAN_ZOOM, Number(view?.zoom) || MIN_PLAN_ZOOM),
  );
  // Keep a small, bounded pan range even at 100% zoom. Without it the
  // "Sposta" tool receives the drag correctly, but x/y are clamped back to
  // zero and the plan appears immovable.
  const limit = Math.max(MIN_PLAN_PAN, (zoom - 1) / 2);
  return {
    zoom,
    x: Math.max(-limit, Math.min(limit, Number(view?.x) || 0)),
    y: Math.max(-limit, Math.min(limit, Number(view?.y) || 0)),
  };
}

export function planToViewport(point, view) {
  const current = clampPlanView(view);
  return {
    x: (point.x - 0.5) * current.zoom + 0.5 + current.x,
    y: (point.y - 0.5) * current.zoom + 0.5 + current.y,
  };
}

export function viewportToPlan(point, view) {
  const current = clampPlanView(view);
  return {
    x: (point.x - 0.5 - current.x) / current.zoom + 0.5,
    y: (point.y - 0.5 - current.y) / current.zoom + 0.5,
  };
}

export function zoomPlanAt(view, nextZoom, focal = { x: 0.5, y: 0.5 }) {
  const current = clampPlanView(view);
  const anchor = viewportToPlan(focal, current);
  return clampPlanView({
    zoom: nextZoom,
    x: focal.x - ((anchor.x - 0.5) * nextZoom + 0.5),
    y: focal.y - ((anchor.y - 0.5) * nextZoom + 0.5),
  });
}

export function panPlanBy(view, delta) {
  const current = clampPlanView(view);
  return clampPlanView({
    ...current,
    x: current.x + delta.x,
    y: current.y + delta.y,
  });
}

function pointDistance(point, target, canvasRatio) {
  return Math.hypot(point.x - target.x, (point.y - target.y) * canvasRatio);
}

function segmentDistance(element, point, canvasRatio) {
  const start = { x: element.x1, y: element.y1 * canvasRatio };
  const end = { x: element.x2, y: element.y2 * canvasRatio };
  const target = { x: point.x, y: point.y * canvasRatio };
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (!lengthSquared) return Math.hypot(target.x - start.x, target.y - start.y);
  const position = Math.max(
    0,
    Math.min(
      1,
      ((target.x - start.x) * dx + (target.y - start.y) * dy) / lengthSquared,
    ),
  );
  return Math.hypot(
    target.x - (start.x + position * dx),
    target.y - (start.y + position * dy),
  );
}

function roomDistance(element, point, threshold, canvasRatio) {
  const left = Math.min(element.x1, element.x2);
  const right = Math.max(element.x1, element.x2);
  const top = Math.min(element.y1, element.y2);
  const bottom = Math.max(element.y1, element.y2);
  const inside =
    point.x >= left && point.x <= right && point.y >= top && point.y <= bottom;
  if (inside) return threshold * 0.7;
  return pointDistance(
    point,
    {
      x: Math.max(left, Math.min(right, point.x)),
      y: Math.max(top, Math.min(bottom, point.y)),
    },
    canvasRatio,
  );
}

export function closestElement(
  elements,
  point,
  threshold = 0.045,
  canvasRatio = 1,
) {
  let closest = null;
  let best = threshold;
  for (const element of elements) {
    const value =
      element.tipo === "ambiente"
        ? roomDistance(element, point, threshold, canvasRatio)
        : element.tipo === "nota"
          ? pointDistance(point, { x: element.x1, y: element.y1 }, canvasRatio)
          : segmentDistance(element, point, canvasRatio);
    if (value < best) {
      best = value;
      closest = element;
    }
  }
  return closest;
}
