import { compressWithSurface, computeTargetSize } from "./photoCompression";

self.onmessage = async (event) => {
  const { id, file, maxEdge = 1600, quality = 0.78 } = event.data || {};
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
    const size = computeTargetSize(bitmap.width, bitmap.height, maxEdge);
    const surface = new OffscreenCanvas(size.width, size.height);
    const blob = await compressWithSurface(bitmap, surface, quality);
    self.postMessage({ id, blob });
  } catch (error) {
    self.postMessage({
      id,
      error: error?.message || "Compressione worker non riuscita.",
    });
  } finally {
    bitmap?.close?.();
  }
};
