import axios from "axios";
import { resolveTenantSlug } from "./tenant";

const PRODUCTION_BACKEND_URL = "https://api.gbconstruction.it";

export function backendUrlForHostname(hostname) {
  const host = String(hostname || "")
    .trim()
    .toLowerCase();
  const isLocal = host === "localhost" || host === "127.0.0.1";
  const isVercelPreview = host.endsWith(".vercel.app");
  return isLocal || isVercelPreview ? "" : PRODUCTION_BACKEND_URL;
}

function defaultBackendUrl() {
  if (typeof window === "undefined") return "";
  return backendUrlForHostname(window.location.hostname);
}

export const BACKEND_URL = (
  process.env.REACT_APP_BACKEND_URL || defaultBackendUrl()
).replace(/\/$/, "");
export const API = `${BACKEND_URL}/api`;

const client = axios.create({
  baseURL: API,
  withCredentials: true,
});

export const API_PERFORMANCE_EVENT = "gb:api-performance";

function monotonicNow() {
  return typeof performance !== "undefined" && performance.now
    ? performance.now()
    : Date.now();
}

function recordApiPerformance(config, response) {
  const startedAt = Number(config?.metadata?.startedAt);
  if (!Number.isFinite(startedAt)) return null;

  const durationMs = Math.max(0, monotonicNow() - startedAt);
  const serverDuration = Number(response?.headers?.["x-response-time-ms"]);
  const detail = {
    method: String(config?.method || "get").toUpperCase(),
    url: String(config?.url || ""),
    status: Number(response?.status) || null,
    durationMs,
    serverDurationMs: Number.isFinite(serverDuration) ? serverDuration : null,
  };
  if (typeof window !== "undefined" && typeof CustomEvent !== "undefined") {
    window.dispatchEvent(new CustomEvent(API_PERFORMANCE_EVENT, { detail }));
  }
  return durationMs;
}

let apiAccessToken = null;

export function setApiAccessToken(token) {
  apiAccessToken = typeof token === "string" && token.trim() ? token : null;
}

client.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  config.metadata = { ...config.metadata, startedAt: monotonicNow() };
  if (apiAccessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${apiAccessToken}`;
  }
  if (!config.headers["X-Tenant-Slug"]) {
    config.headers["X-Tenant-Slug"] = resolveTenantSlug();
  }
  return config;
});

client.interceptors.response.use(
  (response) => {
    response.durationMs = recordApiPerformance(response.config, response);
    return response;
  },
  (error) => {
    error.durationMs = recordApiPerformance(error?.config, error?.response);
    return Promise.reject(error);
  },
);

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

/**
 * Con `responseType: "blob"` axios applica lo stesso responseType anche alle
 * risposte di errore: il body JSON del backend (es. 409 con `detail`) arriva
 * come Blob binario invece che come oggetto, quindi `error.response.data.detail`
 * risulta sempre undefined e il messaggio reale non si vede mai. Qui il Blob
 * viene riletto come testo e riparsato prima di formattare il dettaglio.
 */
export async function extractErrorDetail(error) {
  const data = error?.response?.data;
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      const text =
        typeof data.text === "function"
          ? await data.text()
          : await new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result || ""));
              reader.onerror = () => reject(reader.error);
              reader.readAsText(data);
            });
      return formatApiErrorDetail(text ? JSON.parse(text)?.detail : null);
    } catch {
      return formatApiErrorDetail(null);
    }
  }
  return formatApiErrorDetail(data?.detail);
}

export default client;
