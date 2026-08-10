import client from "./api";
import { supabase, supabaseConfigured } from "./supabase";
import {
  canUseTenantStorage,
  sanitizeStorageFilename,
  tenantIdFromUser,
} from "./storage";

export const RILIEVO_PLAN_BUCKET = "planimetrie";
export const MAX_RILIEVO_PLAN_BYTES = 25 * 1024 * 1024;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PLAN_MIME = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/webp",
]);

function requireStorage(user) {
  if (!supabaseConfigured || !supabase || !canUseTenantStorage(user)) {
    throw new Error(
      "La planimetria richiede una sessione Supabase interna valida.",
    );
  }
  return supabase.storage.from(RILIEVO_PLAN_BUCKET);
}

export function validateRilievoPlan(file) {
  if (!file?.size) throw new Error("Seleziona una planimetria non vuota.");
  if (!PLAN_MIME.has(file.type)) {
    throw new Error("Formato non supportato. Usa PDF, JPG, PNG o WebP.");
  }
  if (file.size > MAX_RILIEVO_PLAN_BYTES) {
    throw new Error("La planimetria supera il limite di 25 MB.");
  }
  return file.type;
}

export function rilievoPlanPath({ tenantId, rilievoId, filename, kind }) {
  if (!UUID_RE.test(String(tenantId || "")))
    throw new Error("Tenant non valido.");
  if (!UUID_RE.test(String(rilievoId || "")))
    throw new Error("Rilievo non valido.");
  const suffix =
    kind === "preview" ? "preview.png" : sanitizeStorageFilename(filename);
  return `${tenantId}/rilievo-${rilievoId}/planimetria/${kind}-${suffix}`;
}

async function upload(storage, path, file, contentType) {
  const { error } = await storage.upload(path, file, {
    cacheControl: "3600",
    contentType,
    upsert: true,
  });
  if (error)
    throw new Error(error.message || "Upload planimetria non riuscito.");
  return path;
}

export async function createRilievoPlanPreview({ rilievoId, file }) {
  const mimeType = validateRilievoPlan(file);
  if (mimeType !== "application/pdf") return file;
  const form = new FormData();
  form.append("planimetria", file);
  const { data } = await client.post(
    `/campo/rilievi/${rilievoId}/planimetria/preview`,
    form,
    { responseType: "blob" },
  );
  return data;
}

export async function uploadRilievoPlan({
  user,
  rilievoId,
  file,
  previewBlob,
}) {
  const mimeType = validateRilievoPlan(file);
  const tenantId = tenantIdFromUser(user);
  const storage = requireStorage(user);
  const sourcePath = rilievoPlanPath({
    tenantId,
    rilievoId,
    filename: file.name,
    kind: "originale",
  });
  await upload(storage, sourcePath, file, mimeType);

  let previewPath = sourcePath;
  if (mimeType === "application/pdf") {
    const data =
      previewBlob || (await createRilievoPlanPreview({ rilievoId, file }));
    previewPath = rilievoPlanPath({
      tenantId,
      rilievoId,
      filename: "preview.png",
      kind: "preview",
    });
    await upload(storage, previewPath, data, "image/png");
  }

  return {
    planimetria_path: sourcePath,
    planimetria_preview_path: previewPath,
    planimetria_filename: file.name,
    planimetria_mime_type: mimeType,
  };
}

export async function createRilievoPlanUrl(path) {
  if (!path || !supabaseConfigured || !supabase) return "";
  const { data, error } = await supabase.storage
    .from(RILIEVO_PLAN_BUCKET)
    .createSignedUrl(path, 5 * 60);
  if (error || !data?.signedUrl) {
    throw new Error(error?.message || "Planimetria non disponibile.");
  }
  return data.signedUrl;
}
