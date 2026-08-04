export const DEFAULT_TENANT_SLUG =
  process.env.REACT_APP_DEFAULT_TENANT_SLUG || "gbconstruction";

export function resolveTenantSlug() {
  if (typeof window === "undefined") return DEFAULT_TENANT_SLUG;

  const params = new URLSearchParams(window.location.search);
  const querySlug = (params.get("tenant") || "").trim().toLowerCase();
  if (querySlug) return querySlug;

  const host = window.location.hostname.toLowerCase();
  const base = (process.env.REACT_APP_BASE_DOMAIN || "alantis.it").toLowerCase();
  if (host.endsWith(`.${base}`)) {
    const slug = host.slice(0, -(base.length + 1));
    if (slug && !slug.includes(".")) return slug;
  }

  return DEFAULT_TENANT_SLUG;
}
