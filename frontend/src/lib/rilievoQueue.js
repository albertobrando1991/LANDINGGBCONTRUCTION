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

function resolutionKey(tenantSlug, localId) {
  return `resolution:${tenantPart(tenantSlug)}:${localId}`;
}

function assetKey(tenantSlug, path) {
  return `asset:${tenantPart(tenantSlug)}:${path}`;
}

function operationGroup(operation) {
  return String(
    operation.local_rilievo_id ||
      operation.rilievo_id ||
      operation.entity_id ||
      "",
  );
}

function operationPriority(operation) {
  if (operation.kind === "rilievo-crea") return 0;
  if (operation.kind === "rilievo-stato" && operation.body?.stato === "bozza")
    return 1;
  if (operation.kind === "rilievo") return 2;
  if (operation.kind === "rilievo-stato") return 4;
  return 3;
}

function summarizeRilievo(rilievo) {
  const hasAmbienti = Array.isArray(rilievo.ambienti);
  const ambienti = hasAmbienti ? rilievo.ambienti : [];
  return {
    ...rilievo,
    n_ambienti: hasAmbienti ? ambienti.length : Number(rilievo.n_ambienti || 0),
    n_foto: Number(
      hasAmbienti
        ? (rilievo.foto_paths || []).length +
            ambienti.reduce(
              (total, ambiente) => total + (ambiente.foto_paths || []).length,
              0,
            )
        : rilievo.n_foto || 0,
    ),
  };
}

export function createOfflineRilievo(body, localId) {
  const now = new Date().toISOString();
  return summarizeRilievo({
    ...body,
    id: localId,
    client_uuid: body.client_uuid || localId,
    stato: "bozza",
    ambienti: [],
    foto_paths: [],
    planimetria_data: null,
    planimetria_path: null,
    planimetria_preview_path: null,
    offline_pending: true,
    created_at: now,
    updated_at: now,
  });
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

export const replaceRilievoOperation = enqueueRilievoOperation;

export async function listRilievoOperations(tenantSlug) {
  const prefix = `queue:${tenantPart(tenantSlug)}:`;
  const storedKeys = (await keys(store)).filter(
    (key) => typeof key === "string" && key.startsWith(prefix),
  );
  const operations = await Promise.all(
    storedKeys.map((key) => get(key, store)),
  );
  const available = operations.filter(Boolean);
  const groupStarts = new Map();
  for (const operation of available) {
    const group = operationGroup(operation);
    const queuedAt = String(operation.queued_at);
    const current = groupStarts.get(group);
    if (!current || queuedAt < current) groupStarts.set(group, queuedAt);
  }
  return available.sort((a, b) => {
    const groupA = operationGroup(a);
    const groupB = operationGroup(b);
    const groupOrder = String(groupStarts.get(groupA)).localeCompare(
      String(groupStarts.get(groupB)),
    );
    if (groupOrder) return groupOrder;
    if (groupA !== groupB) return groupA.localeCompare(groupB);
    const priority = operationPriority(a) - operationPriority(b);
    if (priority) return priority;
    return String(a.queued_at).localeCompare(String(b.queued_at));
  });
}

export async function removeRilievoOperation(tenantSlug, operation) {
  await del(operationKey(tenantSlug, operation), store);
}

export async function syncRilievoOperations(tenantSlug, send) {
  const operations = await listRilievoOperations(tenantSlug);
  const failures = [];
  const blockedGroups = new Set();
  let synced = 0;
  for (const operation of operations) {
    const group = operationGroup(operation);
    if (blockedGroups.has(group)) {
      failures.push({ operation, blocked: true });
      continue;
    }
    try {
      await send(operation);
      await removeRilievoOperation(tenantSlug, operation);
      synced += 1;
    } catch (error) {
      blockedGroups.add(group);
      failures.push({ operation, error, blocked: false });
    }
  }
  return { total: operations.length, synced, failures };
}

export async function saveRilievoIdResolution(tenantSlug, localId, serverId) {
  await set(
    resolutionKey(tenantSlug, localId),
    { server_id: serverId, saved_at: new Date().toISOString() },
    store,
  );
}

export async function resolveRilievoId(tenantSlug, rilievoId) {
  const resolution = await get(resolutionKey(tenantSlug, rilievoId), store);
  return resolution?.server_id || rilievoId;
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

export async function mergeRemoteRilievi(tenantSlug, remoteRilievi) {
  const cached = (await readCachedRilievi(tenantSlug)) || [];
  const pending = cached.filter((item) => item.offline_pending);
  const ids = new Set(remoteRilievi.map((item) => item.id));
  const merged = [
    ...pending.filter((item) => !ids.has(item.id)),
    ...remoteRilievi,
  ];
  await cacheRilievi(tenantSlug, merged);
  return merged;
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

export async function upsertCachedRilievo(tenantSlug, rilievo) {
  const normalized = summarizeRilievo(rilievo);
  await cacheRilievo(tenantSlug, normalized);
  const list = (await readCachedRilievi(tenantSlug)) || [];
  const exists = list.some((item) => item.id === normalized.id);
  await cacheRilievi(
    tenantSlug,
    exists
      ? list.map((item) =>
          item.id === normalized.id ? summarizeRilievo(normalized) : item,
        )
      : [summarizeRilievo(normalized), ...list],
  );
  return normalized;
}

export async function promoteCachedRilievo(tenantSlug, localId, serverRilievo) {
  const local = await readCachedRilievo(tenantSlug, localId);
  const promoted = summarizeRilievo({
    ...(local || {}),
    ...serverRilievo,
    id: serverRilievo.id,
    ambienti: local?.ambienti || serverRilievo.ambienti || [],
    offline_pending: false,
  });
  await del(cacheKey(tenantSlug, `dettaglio:${localId}`), store);
  await cacheRilievo(tenantSlug, promoted);
  const list = (await readCachedRilievi(tenantSlug)) || [];
  const withoutLocal = list.filter(
    (item) => item.id !== localId && item.id !== promoted.id,
  );
  await cacheRilievi(tenantSlug, [promoted, ...withoutLocal]);
  return promoted;
}

export async function cacheRilievoReferences(tenantSlug, name, data) {
  await set(
    cacheKey(tenantSlug, `riferimenti:${name}`),
    { saved_at: new Date().toISOString(), data },
    store,
  );
}

export async function readCachedRilievoReferences(tenantSlug, name) {
  return (await get(cacheKey(tenantSlug, `riferimenti:${name}`), store))?.data;
}

export async function cacheRilievoAsset(tenantSlug, path, blob) {
  await set(
    assetKey(tenantSlug, path),
    { saved_at: new Date().toISOString(), path, blob },
    store,
  );
}

export async function readCachedRilievoAsset(tenantSlug, path) {
  return (await get(assetKey(tenantSlug, path), store))?.blob;
}

export async function cacheRilievoOfflinePack(tenantSlug, rilievoId, pack) {
  const value = { ...pack, saved_at: new Date().toISOString() };
  await set(cacheKey(tenantSlug, `offline-pack:${rilievoId}`), value, store);
  return value;
}

export async function readRilievoOfflinePack(tenantSlug, rilievoId) {
  return get(cacheKey(tenantSlug, `offline-pack:${rilievoId}`), store);
}
