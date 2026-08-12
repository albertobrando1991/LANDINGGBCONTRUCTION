import { createStore, del, get, keys, set } from "idb-keyval";
import client from "./api";

// Un solo object store evita upgrade concorrenti della stessa IndexedDB su
// Safari/iOS; i prefissi separano coda, cache e sessione senza collisioni.
const queueStore = createStore("gb-offline-v1", "data");
const cacheStore = queueStore;
const QUEUE_EVENT = "gb:offline-queue-changed";

function normalizePart(value, fallback) {
  return String(value || fallback)
    .trim()
    .toLowerCase();
}

function scopePrefix(tenantSlug, userId) {
  return `${normalizePart(tenantSlug, "gbconstruction")}:${normalizePart(
    userId,
    "anonymous",
  )}`;
}

function operationKey(operation) {
  const scope = scopePrefix(operation.tenant_slug, operation.user_id);
  return operation.coalesce_key
    ? `operation:${scope}:coalesced:${operation.coalesce_key}`
    : `operation:${scope}:${operation.id}`;
}

function emitQueueChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(QUEUE_EVENT));
  }
}

export function createOfflineId() {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function isRetryableOfflineError(error) {
  const status = error?.response?.status;
  return (
    !error?.response ||
    status === 408 ||
    status === 429 ||
    Number(status) >= 500
  );
}

export async function putOfflineCache(tenantSlug, userId, name, data) {
  try {
    await set(
      `cache:${scopePrefix(tenantSlug, userId)}:${name}`,
      { data, saved_at: new Date().toISOString() },
      cacheStore,
    );
  } catch {
    // Il salvataggio online non deve fallire se IndexedDB non e disponibile.
  }
  return data;
}

export async function getOfflineCache(tenantSlug, userId, name) {
  return (
    await get(`cache:${scopePrefix(tenantSlug, userId)}:${name}`, cacheStore)
  )?.data;
}

export async function loadWithOfflineCache({
  tenantSlug,
  userId,
  cacheKey,
  load,
}) {
  try {
    const data = await load();
    await putOfflineCache(tenantSlug, userId, cacheKey, data);
    return data;
  } catch (error) {
    if (!isRetryableOfflineError(error)) throw error;
    const cached = await getOfflineCache(tenantSlug, userId, cacheKey);
    if (cached === undefined) throw error;
    return cached;
  }
}

export async function enqueueOfflineOperation(operation) {
  const next = {
    ...operation,
    id: operation.id || createOfflineId(),
    tenant_slug: normalizePart(operation.tenant_slug, "gbconstruction"),
    user_id: normalizePart(operation.user_id, "anonymous"),
    queued_at: operation.queued_at || new Date().toISOString(),
    updated_at: new Date().toISOString(),
    attempts: Number(operation.attempts || 0),
  };
  const key = operationKey(next);
  const existing = await get(key, queueStore);
  if (existing && next.coalesce_key && next.type === "json") {
    next.id = existing.id;
    next.queued_at = existing.queued_at;
    next.attempts = existing.attempts || 0;
    if (next.data?.client_id) {
      next.data = { ...next.data, client_id: existing.id };
    }
    if (existing.method === "patch" && next.method === "patch") {
      next.data = { ...existing.data, ...next.data };
    }
  }
  await set(key, next, queueStore);
  emitQueueChanged();
  return next;
}

export async function listOfflineOperations(tenantSlug, userId) {
  const prefix = `operation:${scopePrefix(tenantSlug, userId)}:`;
  let storedKeys;
  try {
    storedKeys = (await keys(queueStore)).filter(
      (key) => typeof key === "string" && key.startsWith(prefix),
    );
  } catch {
    return [];
  }
  const operations = await Promise.all(
    storedKeys.map((key) => get(key, queueStore)),
  );
  return operations
    .filter(Boolean)
    .sort((a, b) => String(a.queued_at).localeCompare(String(b.queued_at)));
}

export async function removeOfflineOperation(operation) {
  await del(operationKey(operation), queueStore);
  emitQueueChanged();
}

async function markAttempt(operation, error) {
  await set(
    operationKey(operation),
    {
      ...operation,
      attempts: Number(operation.attempts || 0) + 1,
      last_error: String(error?.message || "Sincronizzazione non riuscita"),
      updated_at: new Date().toISOString(),
    },
    queueStore,
  );
}

async function sendOperation(operation) {
  if (operation.type === "file") {
    const form = new FormData();
    form.append("client_id", operation.id);
    const file =
      typeof File !== "undefined"
        ? new File([operation.file_blob], operation.file_name, {
            type: operation.file_type,
            lastModified: operation.file_last_modified,
          })
        : operation.file_blob;
    form.append("file", file, operation.file_name);
    return client.request({
      method: operation.method,
      url: operation.url,
      data: form,
      headers: { "Content-Type": "multipart/form-data" },
    });
  }
  return client.request({
    method: operation.method,
    url: operation.url,
    data: operation.data,
    params: operation.params,
  });
}

export async function syncOfflineOperations(tenantSlug, userId) {
  const operations = await listOfflineOperations(tenantSlug, userId);
  const failures = [];
  let synced = 0;
  for (const operation of operations) {
    try {
      await sendOperation(operation);
      await removeOfflineOperation(operation);
      synced += 1;
    } catch (error) {
      if (operation.ignore_statuses?.includes(error?.response?.status)) {
        await removeOfflineOperation(operation);
        synced += 1;
        continue;
      }
      await markAttempt(operation, error);
      failures.push({ operation, error });
    }
  }
  emitQueueChanged();
  return { total: operations.length, synced, failures };
}

export async function runOrQueueJson({
  tenantSlug,
  userId,
  method,
  url,
  data,
  params,
  label,
  coalesceKey,
  clientId = false,
  ignoreStatuses = [],
}) {
  const id = createOfflineId();
  const body = clientId ? { ...data, client_id: id } : data;
  const operation = {
    id,
    type: "json",
    tenant_slug: tenantSlug,
    user_id: userId,
    method: String(method || "post").toLowerCase(),
    url,
    data: body,
    params,
    label,
    coalesce_key: coalesceKey,
    ignore_statuses: ignoreStatuses,
  };
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return {
      queued: true,
      operation: await enqueueOfflineOperation(operation),
    };
  }
  try {
    const response = await sendOperation(operation);
    return { queued: false, data: response.data, response };
  } catch (error) {
    if (!isRetryableOfflineError(error)) throw error;
    return {
      queued: true,
      operation: await enqueueOfflineOperation(operation),
    };
  }
}

export async function runOrQueueFile({ tenantSlug, userId, url, file, label }) {
  const operation = {
    id: createOfflineId(),
    type: "file",
    tenant_slug: tenantSlug,
    user_id: userId,
    method: "post",
    url,
    file_blob: file,
    file_name: file.name || "documento",
    file_type: file.type || "application/octet-stream",
    file_last_modified: file.lastModified || Date.now(),
    label,
  };
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return {
      queued: true,
      operation: await enqueueOfflineOperation(operation),
    };
  }
  try {
    const response = await sendOperation(operation);
    return { queued: false, data: response.data, response };
  } catch (error) {
    if (!isRetryableOfflineError(error)) throw error;
    return {
      queued: true,
      operation: await enqueueOfflineOperation(operation),
    };
  }
}

export const OFFLINE_QUEUE_EVENT = QUEUE_EVENT;
