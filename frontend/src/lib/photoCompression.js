export function computeTargetSize(width, height, maxEdge) {
  const sourceWidth = Number(width);
  const sourceHeight = Number(height);
  const edge = Number(maxEdge);
  if (
    !Number.isFinite(sourceWidth) ||
    !Number.isFinite(sourceHeight) ||
    !Number.isFinite(edge) ||
    sourceWidth <= 0 ||
    sourceHeight <= 0 ||
    edge <= 0
  ) {
    throw new Error("Dimensioni foto non valide.");
  }
  const scale = Math.min(1, edge / Math.max(sourceWidth, sourceHeight));
  return {
    width: Math.max(1, Math.round(sourceWidth * scale)),
    height: Math.max(1, Math.round(sourceHeight * scale)),
  };
}

export async function compressWithSurface(bitmap, surface, quality = 0.78) {
  const context = surface.getContext?.("2d");
  if (!context) {
    throw new Error("Compressione foto non supportata dal dispositivo.");
  }
  context.drawImage(bitmap, 0, 0, surface.width, surface.height);
  if (typeof surface.convertToBlob === "function") {
    return surface.convertToBlob({ type: "image/jpeg", quality });
  }
  if (typeof surface.toBlob !== "function") {
    throw new Error("Compressione della foto non riuscita.");
  }
  return new Promise((resolve, reject) => {
    surface.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("Compressione della foto non riuscita.")),
      "image/jpeg",
      quality,
    );
  });
}
