import { createStore, del, get, set } from "idb-keyval";
import { resolveTenantSlug } from "./tenant";

const store = createStore("gb-offline-v1", "data");

function key() {
  return `last-user:${resolveTenantSlug()}`;
}

export async function cacheOfflineUser(user) {
  if (!user || typeof user !== "object") return;
  try {
    await set(key(), { user, saved_at: new Date().toISOString() }, store);
  } catch {
    // L'autenticazione online resta valida anche se lo storage locale e negato.
  }
}

export async function readOfflineUser() {
  try {
    return (await get(key(), store))?.user || null;
  } catch {
    return null;
  }
}

export async function clearOfflineUser() {
  try {
    await del(key(), store);
  } catch {
    // Nessuna sessione locale da rimuovere se IndexedDB non e disponibile.
  }
}
