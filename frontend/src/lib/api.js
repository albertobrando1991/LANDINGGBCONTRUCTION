import axios from "axios";

const PRODUCTION_BACKEND_URL = "https://api.gbconstruction.it";

function defaultBackendUrl() {
  if (typeof window === "undefined") return "";
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  return isLocal ? "" : PRODUCTION_BACKEND_URL;
}

export const BACKEND_URL = (
  process.env.REACT_APP_BACKEND_URL || defaultBackendUrl()
).replace(/\/$/, "");
export const API = `${BACKEND_URL}/api`;

const client = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Landing GB Construction: tenant fisso (no subdominio alantis su questo deploy)
const DEFAULT_TENANT_SLUG =
  process.env.REACT_APP_DEFAULT_TENANT_SLUG || "gbconstruction";

client.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  if (!config.headers["X-Tenant-Slug"]) {
    config.headers["X-Tenant-Slug"] = DEFAULT_TENANT_SLUG;
  }
  return config;
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Si è verificato un errore. Riprova.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default client;
