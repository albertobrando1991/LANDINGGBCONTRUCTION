import client from "./api";
import { sanitizeStorageFilename } from "./storage";

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

async function uploadAsset(rilievoId, tipo, file, filename = file.name) {
  const form = new FormData();
  form.append("tipo", tipo);
  form.append("file", file, filename || "asset-rilievo");
  const { data } = await client.post(
    `/campo/rilievi/${rilievoId}/assets`,
    form,
  );
  return data;
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

export async function uploadRilievoPlan({ rilievoId, file, previewBlob }) {
  const mimeType = validateRilievoPlan(file);
  const source = await uploadAsset(rilievoId, "planimetria", file);

  let previewPath = source.path;
  if (mimeType === "application/pdf") {
    const data =
      previewBlob || (await createRilievoPlanPreview({ rilievoId, file }));
    const preview = await uploadAsset(
      rilievoId,
      "planimetria_preview",
      data,
      "preview.png",
    );
    previewPath = preview.path;
  }

  return {
    planimetria_path: source.path,
    planimetria_preview_path: previewPath,
    planimetria_filename: file.name,
    planimetria_mime_type: source.mime_type || mimeType,
  };
}

export async function createRilievoPlanUrl(path, rilievoId) {
  if (!path || !rilievoId) return "";
  const { data } = await client.post(
    `/campo/rilievi/${rilievoId}/assets/urls`,
    { bucket: RILIEVO_PLAN_BUCKET, paths: [path] },
  );
  return data?.[0]?.url || "";
}
