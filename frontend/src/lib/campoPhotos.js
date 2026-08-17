import * as tus from "tus-js-client";
import client from "./api";
import { SUPABASE_URL, supabase, supabaseConfigured } from "./supabase";
import { canUseTenantStorage, tenantIdFromUser } from "./storage";
import { mapLimit } from "./network";
import { compressWithSurface, computeTargetSize } from "./photoCompression";
import { compressPhotoInWorker } from "./photoCompressorClient";

export const CAMPO_PHOTO_BUCKET = "foto-cantiere";
export const MAX_CAMPO_PHOTOS = 5;
export const MAX_RILIEVO_PHOTOS = 12;
export const MAX_RILIEVO_GENERAL_PHOTOS = 30;
export const MAX_CAMPO_PHOTO_SOURCE_BYTES = 20 * 1024 * 1024;
export const MAX_CAMPO_PHOTO_EDGE = 1600;

const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const CAMPO_WORKER_ENABLED = process.env.REACT_APP_CAMPO_WORKER === "true";
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function requirePhotoFile(file) {
  if (!file || !file.size) throw new Error("Seleziona una foto non vuota.");
  if (!ALLOWED_PHOTO_TYPES.has(file.type)) {
    throw new Error("Formato foto non supportato. Usa JPG, PNG o WebP.");
  }
  if (file.size > MAX_CAMPO_PHOTO_SOURCE_BYTES) {
    throw new Error("La foto supera il limite di 20 MB.");
  }
}

function loadImage(file) {
  if (typeof createImageBitmap === "function") return createImageBitmap(file);
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("La foto non puo essere letta."));
    };
    image.src = url;
  });
}

function newPhotoId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function compressedPhoto(blob, id) {
  const safeId = String(id).toLowerCase();
  const name = `foto-${safeId}.jpg`;
  const compressed = new File([blob], name, {
    type: "image/jpeg",
    lastModified: Date.now(),
  });
  return {
    id: safeId,
    name,
    type: "image/jpeg",
    size: compressed.size,
    blob: compressed,
  };
}

async function compressOnMainThread(file, id) {
  const image = await loadImage(file);
  const sourceWidth = image.width || image.naturalWidth;
  const sourceHeight = image.height || image.naturalHeight;
  const size = computeTargetSize(
    sourceWidth,
    sourceHeight,
    MAX_CAMPO_PHOTO_EDGE,
  );
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  try {
    const blob = await compressWithSurface(image, canvas, 0.78);
    return compressedPhoto(blob, id);
  } finally {
    image.close?.();
  }
}

function canUseCompressionWorker() {
  return (
    CAMPO_WORKER_ENABLED &&
    typeof Worker !== "undefined" &&
    typeof OffscreenCanvas !== "undefined" &&
    typeof OffscreenCanvas.prototype?.convertToBlob === "function"
  );
}

export async function compressCampoPhoto(file, id = newPhotoId()) {
  requirePhotoFile(file);
  if (canUseCompressionWorker()) {
    try {
      const blob = await compressPhotoInWorker({
        id,
        file,
        maxEdge: MAX_CAMPO_PHOTO_EDGE,
        quality: 0.78,
      });
      return compressedPhoto(blob, id);
    } catch {
      // Fallback per Safari/iPad datati o worker interrotti.
    }
  }
  return compressOnMainThread(file, id);
}

export function campoPhotoPath({ tenantId, cantiereId, clientUuid, photoId }) {
  for (const [label, value] of [
    ["Tenant", tenantId],
    ["Cantiere", cantiereId],
    ["Misura", clientUuid],
    ["Foto", photoId],
  ]) {
    if (!UUID_RE.test(String(value || "")))
      throw new Error(`${label} non valido.`);
  }
  return `${tenantId}/cantiere-${cantiereId}/libretto-${clientUuid}/${photoId}.jpg`;
}

export function rilievoPhotoPath({
  tenantId,
  rilievoId,
  ambienteClientUuid,
  photoId,
}) {
  for (const [label, value] of [
    ["Tenant", tenantId],
    ["Rilievo", rilievoId],
    ["Ambiente", ambienteClientUuid],
    ["Foto", photoId],
  ]) {
    if (!UUID_RE.test(String(value || "")))
      throw new Error(`${label} non valido.`);
  }
  return `${tenantId}/rilievo-${rilievoId}/ambiente-${ambienteClientUuid}/${photoId}.jpg`;
}

export function rilievoGeneralPhotoPath({ tenantId, rilievoId, photoId }) {
  for (const [label, value] of [
    ["Tenant", tenantId],
    ["Rilievo", rilievoId],
    ["Foto", photoId],
  ]) {
    if (!UUID_RE.test(String(value || "")))
      throw new Error(`${label} non valido.`);
  }
  return `${tenantId}/rilievo-${rilievoId}/generali/${photoId}.jpg`;
}

function resumableEndpoint() {
  const url = new URL(SUPABASE_URL);
  if (url.hostname.endsWith(".supabase.co")) {
    const projectId = url.hostname.split(".")[0];
    return `https://${projectId}.storage.supabase.co/storage/v1/upload/resumable`;
  }
  return new URL("/storage/v1/upload/resumable", url).toString();
}

async function uploadOne({ path, photo, accessToken, onProgress }) {
  return new Promise((resolve, reject) => {
    const upload = new tus.Upload(photo.blob, {
      endpoint: resumableEndpoint(),
      retryDelays: [0, 3000, 5000, 10000, 20000],
      chunkSize: 6 * 1024 * 1024,
      uploadDataDuringCreation: true,
      removeFingerprintOnSuccess: true,
      headers: {
        authorization: `Bearer ${accessToken}`,
        "x-upsert": "true",
      },
      metadata: {
        bucketName: CAMPO_PHOTO_BUCKET,
        objectName: path,
        contentType: photo.type || "image/jpeg",
        cacheControl: "3600",
      },
      onError: reject,
      onProgress: (uploaded, total) => onProgress?.(uploaded, total),
      onSuccess: () => resolve(path),
    });
    upload
      .findPreviousUploads()
      .then((previous) => {
        if (previous.length) upload.resumeFromPreviousUpload(previous[0]);
        upload.start();
      })
      .catch(reject);
  });
}

function aggregateProgress(photos, onProgress) {
  const uploaded = photos.map(() => 0);
  const totals = photos.map((photo) => photo.size || photo.blob?.size || 0);
  return (index, done, total = totals[index]) => {
    uploaded[index] = Math.min(done, total || done);
    if (total) totals[index] = total;
    onProgress?.({
      uploaded: uploaded.reduce((sum, value) => sum + value, 0),
      total: totals.reduce((sum, value) => sum + value, 0),
      count: photos.length,
    });
  };
}

export async function uploadCampoPhotos({
  user,
  cantiereId,
  clientUuid,
  photos,
  onProgress,
}) {
  if (!photos?.length) return [];
  if (!supabaseConfigured || !supabase || !canUseTenantStorage(user)) {
    throw new Error("Le foto richiedono una sessione Supabase interna valida.");
  }
  const tenantId = tenantIdFromUser(user);
  const { data, error } = await supabase.auth.getSession();
  const accessToken = data?.session?.access_token;
  if (error || !accessToken)
    throw new Error("Sessione Storage non disponibile.");

  const reportProgress = aggregateProgress(photos, onProgress);
  return mapLimit(photos, 3, async (photo, index) => {
    const path = campoPhotoPath({
      tenantId,
      cantiereId,
      clientUuid,
      photoId: photo.id,
    });
    return uploadOne({
      path,
      photo,
      accessToken,
      onProgress: (uploaded, total) => reportProgress(index, uploaded, total),
    });
  });
}

export async function uploadRilievoPhotos({
  rilievoId,
  ambienteClientUuid,
  photos,
  onProgress,
}) {
  if (!photos?.length) return [];
  const reportProgress = aggregateProgress(photos, onProgress);
  return mapLimit(photos, 3, async (photo, index) => {
    const form = new FormData();
    form.append("tipo", "foto_ambiente");
    form.append("ambiente_client_uuid", ambienteClientUuid);
    form.append("client_asset_uuid", photo.id);
    form.append("file", photo.blob, photo.name || "foto.jpg");
    const size = photo.size || photo.blob.size;
    const { data } = await client.post(
      `/campo/rilievi/${rilievoId}/assets`,
      form,
      {
        onUploadProgress: ({ loaded, total }) =>
          reportProgress(index, loaded, total || size),
      },
    );
    reportProgress(index, size, size);
    return data.path;
  });
}

export async function uploadRilievoGeneralPhotos({
  rilievoId,
  photos,
  onProgress,
}) {
  if (!photos?.length) return [];
  const reportProgress = aggregateProgress(photos, onProgress);
  return mapLimit(photos, 3, async (photo, index) => {
    const form = new FormData();
    form.append("tipo", "foto_generale");
    form.append("client_asset_uuid", photo.id);
    form.append("file", photo.blob, photo.name || "foto.jpg");
    const size = photo.size || photo.blob.size;
    const { data } = await client.post(
      `/campo/rilievi/${rilievoId}/assets`,
      form,
      {
        onUploadProgress: ({ loaded, total }) =>
          reportProgress(index, loaded, total || size),
      },
    );
    reportProgress(index, size, size);
    return data.path;
  });
}

export async function createRilievoPhotoUrls(paths, rilievoId) {
  if (!paths?.length || !rilievoId) return [];
  const { data } = await client.post(
    `/campo/rilievi/${rilievoId}/assets/urls`,
    { bucket: CAMPO_PHOTO_BUCKET, paths },
  );
  return data || [];
}
