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

export function closestElement(elements, point, threshold = 0.045) {
  let closest = null;
  let best = threshold;
  for (const element of elements) {
    const center = {
      x: (element.x1 + element.x2) / 2,
      y: (element.y1 + element.y2) / 2,
    };
    const value = Math.hypot(center.x - point.x, center.y - point.y);
    if (value < best) {
      best = value;
      closest = element;
    }
  }
  return closest;
}
