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

let apiAccessToken = null;

export function setApiAccessToken(token) {
  apiAccessToken = typeof token === "string" && token.trim() ? token : null;
}

client.interceptors.request.use((config) => {
  config.headers = config.headers || {};
  if (apiAccessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${apiAccessToken}`;
  }
  if (!config.headers["X-Tenant-Slug"]) {
    config.headers["X-Tenant-Slug"] = resolveTenantSlug();
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
