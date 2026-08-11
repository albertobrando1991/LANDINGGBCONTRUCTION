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
