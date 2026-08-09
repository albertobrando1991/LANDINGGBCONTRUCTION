import { createStore, del, get, keys, set } from "idb-keyval";

const store = createStore("gb-campo-rilievi", "offline-data");

function tenantPart(value) {
  return String(value || "gbconstruction")
    .trim()
    .toLowerCase();
}

function operationKey(tenantSlug, operation) {
  return `queue:${tenantPart(tenantSlug)}:${operation.kind}:${operation.entity_id}`;
}

function cacheKey(tenantSlug, name) {
  return `cache:${tenantPart(tenantSlug)}:${name}`;
}

export async function enqueueRilievoOperation(tenantSlug, operation) {
  const key = operationKey(tenantSlug, operation);
  const existing = await get(key, store);
  const value = {
    ...existing,
    ...operation,
    tenant_slug: tenantPart(tenantSlug),
    queued_at: existing?.queued_at || new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  await set(key, value, store);
  return value;
}

export async function listRilievoOperations(tenantSlug) {
  const prefix = `queue:${tenantPart(tenantSlug)}:`;
  const storedKeys = (await keys(store)).filter(
    (key) => typeof key === "string" && key.startsWith(prefix),
  );
  const operations = await Promise.all(
    storedKeys.map((key) => get(key, store)),
  );
  return operations
    .filter(Boolean)
    .sort((a, b) => String(a.queued_at).localeCompare(String(b.queued_at)));
}

export async function removeRilievoOperation(tenantSlug, operation) {
  await del(operationKey(tenantSlug, operation), store);
}

export async function syncRilievoOperations(tenantSlug, send) {
  const operations = await listRilievoOperations(tenantSlug);
  const failures = [];
  let synced = 0;
  for (const operation of operations) {
    try {
      await send(operation);
      await removeRilievoOperation(tenantSlug, operation);
      synced += 1;
    } catch (error) {
      failures.push({ operation, error });
    }
  }
  return { total: operations.length, synced, failures };
}

export async function cacheRilievi(tenantSlug, rilievi) {
  await set(
    cacheKey(tenantSlug, "lista"),
    { saved_at: new Date().toISOString(), data: rilievi },
    store,
  );
}

export async function readCachedRilievi(tenantSlug) {
  return (await get(cacheKey(tenantSlug, "lista"), store))?.data;
}

export async function cacheRilievo(tenantSlug, rilievo) {
  await set(
    cacheKey(tenantSlug, `dettaglio:${rilievo.id}`),
    { saved_at: new Date().toISOString(), data: rilievo },
    store,
  );
}

export async function readCachedRilievo(tenantSlug, rilievoId) {
  return (await get(cacheKey(tenantSlug, `dettaglio:${rilievoId}`), store))
    ?.data;
}
