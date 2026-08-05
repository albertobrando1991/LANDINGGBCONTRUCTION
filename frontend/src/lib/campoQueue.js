import { createStore, del, get, keys, set } from "idb-keyval";

const campoStore = createStore("gb-campo", "offline-data");
const QUEUE_PREFIX = "queue:";
const CACHE_PREFIX = "cache:";

function tenantPart(tenantSlug) {
  return String(tenantSlug || "gbconstruction")
    .trim()
    .toLowerCase();
}

function queueKey(tenantSlug, clientUuid) {
  return `${QUEUE_PREFIX}${tenantPart(tenantSlug)}:${clientUuid}`;
}

function cacheKey(tenantSlug, name) {
  return `${CACHE_PREFIX}${tenantPart(tenantSlug)}:${name}`;
}

export async function enqueueCampoMeasurement(item) {
  const key = queueKey(item.tenant_slug, item.body.client_uuid);
  const existing = await get(key, campoStore);
  const queued = {
    ...item,
    tenant_slug: tenantPart(item.tenant_slug),
    queued_at:
      existing?.queued_at || item.queued_at || new Date().toISOString(),
  };
  await set(key, queued, campoStore);
  return queued;
}

export async function listQueuedCampoMeasurements(tenantSlug) {
  const prefix = `${QUEUE_PREFIX}${tenantPart(tenantSlug)}:`;
  const storedKeys = (await keys(campoStore)).filter(
    (key) => typeof key === "string" && key.startsWith(prefix),
  );
  const items = await Promise.all(
    storedKeys.map((key) => get(key, campoStore)),
  );
  return items
    .filter(Boolean)
    .sort((a, b) => String(a.queued_at).localeCompare(String(b.queued_at)));
}

export async function removeQueuedCampoMeasurement(tenantSlug, clientUuid) {
  await del(queueKey(tenantSlug, clientUuid), campoStore);
}

export async function replaceQueuedCampoMeasurement(item) {
  return enqueueCampoMeasurement(item);
}

export async function syncQueuedCampoMeasurements(sendFn, tenantSlug) {
  const queued = await listQueuedCampoMeasurements(tenantSlug);
  const failures = [];
  let synced = 0;

  // L'ordine e intenzionale: il libretto e append-only e deve riflettere la
  // sequenza in cui l'operatore ha registrato rilievi e rettifiche.
  for (const item of queued) {
    try {
      await sendFn(item);
      await removeQueuedCampoMeasurement(
        item.tenant_slug,
        item.body.client_uuid,
      );
      synced += 1;
    } catch (error) {
      failures.push({ item, error });
    }
  }

  return { synced, failures, total: queued.length };
}

export function isRetryableCampoError(error) {
  const status = error?.response?.status;
  return (
    !error?.response ||
    status === 408 ||
    status === 429 ||
    Number(status) >= 500
  );
}

export async function cacheCampoBootstrap(tenantSlug, cantieri) {
  await set(
    cacheKey(tenantSlug, "bootstrap"),
    { saved_at: new Date().toISOString(), data: cantieri },
    campoStore,
  );
}

export async function readCampoBootstrap(tenantSlug) {
  return (await get(cacheKey(tenantSlug, "bootstrap"), campoStore))?.data;
}

export async function cacheCampoMisure(tenantSlug, cantiereId, misure) {
  await set(
    cacheKey(tenantSlug, `misure:${cantiereId}`),
    { saved_at: new Date().toISOString(), data: misure },
    campoStore,
  );
}

export async function readCampoMisure(tenantSlug, cantiereId) {
  return (await get(cacheKey(tenantSlug, `misure:${cantiereId}`), campoStore))
    ?.data;
}
