let worker = null;
let active = null;
const queue = [];

function disposeWorker(error) {
  worker?.terminate?.();
  worker = null;
  if (active) {
    clearTimeout(active.timer);
    active.reject(error);
    active = null;
  }
  while (queue.length) queue.shift().reject(error);
}

function runNext() {
  if (active || !queue.length) return;
  if (!worker) {
    try {
      worker = new Worker(
        new URL("./photoCompressor.worker.js", import.meta.url),
        {
          type: "module",
        },
      );
    } catch (error) {
      queue.shift()?.reject(error);
      runNext();
      return;
    }
    worker.onmessage = (event) => {
      if (!active || event.data?.id !== active.id) return;
      const current = active;
      active = null;
      clearTimeout(current.timer);
      if (event.data.error) current.reject(new Error(event.data.error));
      else current.resolve(event.data.blob);
      runNext();
    };
    worker.onerror = () =>
      disposeWorker(new Error("Worker foto non disponibile."));
  }

  active = queue.shift();
  active.timer = setTimeout(() => {
    disposeWorker(new Error("Compressione foto scaduta."));
  }, active.timeoutMs);
  try {
    worker.postMessage({
      id: active.id,
      file: active.file,
      maxEdge: active.maxEdge,
      quality: active.quality,
    });
  } catch (error) {
    disposeWorker(error);
  }
}

export function compressPhotoInWorker({
  id,
  file,
  maxEdge = 1600,
  quality = 0.78,
  timeoutMs = 15_000,
}) {
  return new Promise((resolve, reject) => {
    queue.push({
      id,
      file,
      maxEdge,
      quality,
      timeoutMs,
      resolve,
      reject,
      timer: null,
    });
    runNext();
  });
}
