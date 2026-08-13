// Rilevamento rete lenta tramite Network Information API.
// Serve a degradare i media pesanti (sequenze di frame, video, poster UHD)
// prima di scaricarli, non dopo che l'utente ha gia atteso a vuoto.

const SLOW_EFFECTIVE_TYPES = new Set(["slow-2g", "2g", "3g"]);

function readConnection() {
  if (typeof navigator === "undefined") return null;

  return (
    navigator.connection ||
    navigator.mozConnection ||
    navigator.webkitConnection ||
    null
  );
}

/**
 * True quando conviene servire la variante leggera dei media.
 * L'API non e supportata ovunque (es. Safari): in quel caso resta false,
 * cioe nessuna degradazione se non sappiamo nulla della rete.
 */
export function prefersLightMedia() {
  const connection = readConnection();
  if (!connection) return false;

  if (connection.saveData) return true;
  return SLOW_EFFECTIVE_TYPES.has(connection.effectiveType);
}

/**
 * Disattiva gli effetti decorativi continui sui dispositivi che dichiarano
 * poche risorse, una rete limitata o la preferenza di ridurre il movimento.
 * I valori assenti non vengono interpretati come un dispositivo lento.
 */
export function prefersReducedEffects() {
  if (typeof window === "undefined" || typeof navigator === "undefined") {
    return false;
  }

  const reducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hardwareConcurrency = Number(navigator.hardwareConcurrency);
  const deviceMemory = Number(navigator.deviceMemory);
  const hasLimitedCpu =
    Number.isFinite(hardwareConcurrency) &&
    hardwareConcurrency > 0 &&
    hardwareConcurrency <= 4;
  const hasLimitedMemory =
    Number.isFinite(deviceMemory) && deviceMemory > 0 && deviceMemory <= 4;

  return (
    reducedMotion || hasLimitedCpu || hasLimitedMemory || prefersLightMedia()
  );
}

export async function mapLimit(items, limit, iteratee) {
  const values = Array.from(items || []);
  const concurrency = Math.max(1, Math.floor(Number(limit) || 1));
  const results = new Array(values.length);
  let cursor = 0;

  const worker = async () => {
    while (cursor < values.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await iteratee(values[index], index, values);
    }
  };

  await Promise.all(
    Array.from({ length: Math.min(concurrency, values.length) }, worker),
  );
  return results;
}
