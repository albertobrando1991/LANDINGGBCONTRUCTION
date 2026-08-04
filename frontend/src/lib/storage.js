import { supabase, supabaseConfigured } from "./supabase";

export const DOCUMENT_BUCKET = "documenti";
export const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;
export const SIGNED_URL_TTL_SECONDS = 5 * 60;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const DOCUMENT_MIME_BY_EXTENSION = {
  pdf: "application/pdf",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls: "application/vnd.ms-excel",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

const ALLOWED_DOCUMENT_MIME = new Set(
  Object.values(DOCUMENT_MIME_BY_EXTENSION),
);
const INTERNAL_STORAGE_ROLES = new Set([
  "owner",
  "admin",
  "staff",
  "operations",
]);

function requireStorage() {
  if (!supabaseConfigured || !supabase) {
    throw new Error("Supabase Storage non configurato in questo ambiente.");
  }
  return supabase.storage.from(DOCUMENT_BUCKET);
}

function safeSegment(value, label) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (!normalized || !/^[a-z0-9_-]+$/.test(normalized)) {
    throw new Error(`${label} non valido.`);
  }
  return normalized;
}

export function tenantIdFromUser(user) {
  const memberships = Array.isArray(user?.app_tenants) ? user.app_tenants : [];
  const membership = memberships.find(
    (item) => item && (item.t || item.tenant_id || item.id),
  );
  return String(membership?.t || membership?.tenant_id || membership?.id || "");
}

export function canUseTenantStorage(user) {
  return (
    supabaseConfigured &&
    user?.auth_provider === "supabase" &&
    INTERNAL_STORAGE_ROLES.has(user?.role) &&
    UUID_RE.test(tenantIdFromUser(user))
  );
}

export function sanitizeStorageFilename(filename) {
  const cleaned = String(filename || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[-_.]+|[-_.]+$/g, "");
  return cleaned || "documento";
}

export function cantiereDocumentPrefix({ tenantId, cantiereId }) {
  if (!UUID_RE.test(String(tenantId || ""))) {
    throw new Error("Tenant Storage non valido.");
  }
  return `${tenantId}/cantiere-${safeSegment(cantiereId, "Cantiere")}`;
}

export function cantiereDocumentPath({
  tenantId,
  cantiereId,
  filename,
  nonce,
}) {
  const prefix = cantiereDocumentPrefix({ tenantId, cantiereId });
  const unique = safeSegment(
    nonce || `${Date.now()}-${globalThis.crypto?.randomUUID?.() || "upload"}`,
    "Identificatore file",
  );
  return `${prefix}/${unique}-${sanitizeStorageFilename(filename)}`;
}

export function displayStorageFilename(filename) {
  return String(filename || "").replace(/^\d{10,}-[0-9a-f-]{8,}-/i, "");
}

export function documentContentType(file) {
  const extension = String(file?.name || "")
    .split(".")
    .pop()
    ?.toLowerCase();
  const inferred = DOCUMENT_MIME_BY_EXTENSION[extension];
  const mime = ALLOWED_DOCUMENT_MIME.has(file?.type) ? file.type : inferred;
  if (!mime || !ALLOWED_DOCUMENT_MIME.has(mime)) {
    throw new Error("Formato non supportato. Usa PDF, immagini, Word o Excel.");
  }
  return mime;
}

export function validateCantiereDocument(file) {
  if (!file || !file.size) {
    throw new Error("Seleziona un documento non vuoto.");
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    throw new Error("Il documento supera il limite di 25 MB.");
  }
  return documentContentType(file);
}

export async function uploadCantiereDocument({ tenantId, cantiereId, file }) {
  const contentType = validateCantiereDocument(file);
  const path = cantiereDocumentPath({
    tenantId,
    cantiereId,
    filename: file.name,
  });
  const { data, error } = await requireStorage().upload(path, file, {
    cacheControl: "3600",
    contentType,
    upsert: false,
  });
  if (error) throw new Error(error.message || "Upload documento non riuscito.");
  return { ...data, path, displayName: file.name };
}

export async function listCantiereDocuments({ tenantId, cantiereId }) {
  const prefix = cantiereDocumentPrefix({ tenantId, cantiereId });
  const { data, error } = await requireStorage().list(prefix, {
    limit: 100,
    offset: 0,
    sortBy: { column: "created_at", order: "desc" },
  });
  if (error)
    throw new Error(error.message || "Elenco documenti non disponibile.");
  return (data || [])
    .filter((item) => item?.id)
    .map((item) => ({
      id: item.id,
      name: item.name,
      displayName: displayStorageFilename(item.name),
      path: `${prefix}/${item.name}`,
      createdAt: item.created_at,
      size: Number(item.metadata?.size || 0),
      contentType: item.metadata?.mimetype || item.metadata?.contentType || "",
    }));
}

export async function createCantiereDocumentUrl({
  tenantId,
  cantiereId,
  path,
  downloadName,
}) {
  const prefix = `${cantiereDocumentPrefix({ tenantId, cantiereId })}/`;
  if (!String(path || "").startsWith(prefix)) {
    throw new Error("Percorso documento non autorizzato.");
  }
  const { data, error } = await requireStorage().createSignedUrl(
    path,
    SIGNED_URL_TTL_SECONDS,
    { download: sanitizeStorageFilename(downloadName) },
  );
  if (error || !data?.signedUrl) {
    throw new Error(error?.message || "Download documento non disponibile.");
  }
  return data.signedUrl;
}
