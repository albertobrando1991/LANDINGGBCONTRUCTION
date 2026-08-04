export const DEFAULT_TENANT_SLUG =
  process.env.REACT_APP_DEFAULT_TENANT_SLUG || "gbconstruction";

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$/;

export function resolveTenantSlug(location) {
  const currentLocation =
    location || (typeof window !== "undefined" ? window.location : null);
  if (!currentLocation) return DEFAULT_TENANT_SLUG;

  const params = new URLSearchParams(currentLocation.search || "");
  const querySlug = (params.get("tenant") || "").trim().toLowerCase();
  if (SLUG_PATTERN.test(querySlug)) return querySlug;

  // La produzione resta su gbconstruction.it: l'hostname non cambia tenant.
  return DEFAULT_TENANT_SLUG;
}
