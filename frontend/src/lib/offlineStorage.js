export async function requestPersistentOfflineStorage() {
  if (!globalThis.navigator?.storage) {
    return { supported: false, persisted: false };
  }
  let persisted = false;
  try {
    persisted = Boolean(await navigator.storage.persisted?.());
    if (!persisted && navigator.storage.persist) {
      persisted = Boolean(await navigator.storage.persist());
    }
  } catch {
    persisted = false;
  }
  let estimate = {};
  try {
    estimate = (await navigator.storage.estimate?.()) || {};
  } catch {
    estimate = {};
  }
  return {
    supported: true,
    persisted,
    usage: Number(estimate.usage || 0),
    quota: Number(estimate.quota || 0),
  };
}
