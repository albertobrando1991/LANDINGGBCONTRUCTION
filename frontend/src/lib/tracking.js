const TRACKING_KEYS = new Set(["fbclid", "gclid", "msclkid"]);

function isTrackingKey(key) {
  return key.startsWith("utm_") || TRACKING_KEYS.has(key);
}

export function captureTrackingParams() {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  let stored = {};
  try {
    stored = JSON.parse(window.sessionStorage.getItem("gb_lead_tracking") || "{}");
  } catch {
    stored = {};
  }

  const current = {};
  params.forEach((value, key) => {
    if (isTrackingKey(key) && value) current[key] = value;
  });
  if (document.referrer) current.referrer = document.referrer;
  current.landing_path = `${window.location.pathname}${window.location.search}`;

  const merged = { ...stored, ...current };
  window.sessionStorage.setItem("gb_lead_tracking", JSON.stringify(merged));
  return merged;
}

export function getLeadTracking() {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem("gb_lead_tracking") || "{}");
  } catch {
    return {};
  }
}
