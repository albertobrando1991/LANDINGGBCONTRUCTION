const AUTH_CALLBACK_KEY = "gb-auth-callback";
const AUTH_CALLBACK_MAX_AGE_MS = 2 * 60 * 60 * 1000;
const PASSWORD_CALLBACK_TYPES = new Set(["invite", "recovery"]);

function callbackTypeFromLocation(location) {
  if (!location) return "";
  const search = new URLSearchParams(location.search || "");
  const hash = new URLSearchParams(String(location.hash || "").replace(/^#/, ""));
  return String(search.get("type") || hash.get("type") || "").toLowerCase();
}

export function captureAuthCallback(location, storage) {
  const type = callbackTypeFromLocation(location);
  if (!PASSWORD_CALLBACK_TYPES.has(type) || !storage) return type;
  storage.setItem(
    AUTH_CALLBACK_KEY,
    JSON.stringify({ type, capturedAt: Date.now() }),
  );
  return type;
}

export function pendingPasswordCallback(storage) {
  if (!storage) return false;
  try {
    const value = JSON.parse(storage.getItem(AUTH_CALLBACK_KEY) || "null");
    if (
      !PASSWORD_CALLBACK_TYPES.has(value?.type) ||
      Date.now() - Number(value?.capturedAt || 0) > AUTH_CALLBACK_MAX_AGE_MS
    ) {
      storage.removeItem(AUTH_CALLBACK_KEY);
      return false;
    }
    return true;
  } catch {
    storage.removeItem(AUTH_CALLBACK_KEY);
    return false;
  }
}

export function clearAuthCallback(storage) {
  storage?.removeItem(AUTH_CALLBACK_KEY);
}

export function browserSessionStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}
