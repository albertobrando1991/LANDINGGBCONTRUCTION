import * as tus from "tus-js-client";
import { SUPABASE_URL, supabase, supabaseConfigured } from "./supabase";
import { canUseTenantStorage, tenantIdFromUser } from "./storage";

export const CAMPO_PHOTO_BUCKET = "foto-cantiere";
export const MAX_CAMPO_PHOTOS = 5;
export const MAX_RILIEVO_PHOTOS = 12;
export const MAX_CAMPO_PHOTO_SOURCE_BYTES = 20 * 1024 * 1024;
export const MAX_CAMPO_PHOTO_EDGE = 1600;

const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
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

function canvasBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob
          ? resolve(blob)
          : reject(new Error("Compressione della foto non riuscita.")),
      "image/jpeg",
      0.78,
    );
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

export async function compressCampoPhoto(file, id = newPhotoId()) {
  requirePhotoFile(file);
  const image = await loadImage(file);
  const sourceWidth = image.width || image.naturalWidth;
  const sourceHeight = image.height || image.naturalHeight;
  const scale = Math.min(
    1,
    MAX_CAMPO_PHOTO_EDGE / Math.max(sourceWidth, sourceHeight),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sourceWidth * scale));
  canvas.height = Math.max(1, Math.round(sourceHeight * scale));
  const context = canvas.getContext("2d");
  if (!context)
    throw new Error("Compressione foto non supportata dal dispositivo.");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  image.close?.();
  const blob = await canvasBlob(canvas);
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

  const paths = [];
  for (let index = 0; index < photos.length; index += 1) {
    const photo = photos[index];
    const path = campoPhotoPath({
      tenantId,
      cantiereId,
      clientUuid,
      photoId: photo.id,
    });
    paths.push(
      await uploadOne({
        path,
        photo,
        accessToken,
        onProgress: (uploaded, total) =>
          onProgress?.({ index, count: photos.length, uploaded, total }),
      }),
    );
  }
  return paths;
}

export async function uploadRilievoPhotos({
  user,
  rilievoId,
  ambienteClientUuid,
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

  const paths = [];
  for (let index = 0; index < photos.length; index += 1) {
    const photo = photos[index];
    const path = rilievoPhotoPath({
      tenantId,
      rilievoId,
      ambienteClientUuid,
      photoId: photo.id,
    });
    paths.push(
      await uploadOne({
        path,
        photo,
        accessToken,
        onProgress: (uploaded, total) =>
          onProgress?.({ index, count: photos.length, uploaded, total }),
      }),
    );
  }
  return paths;
}

export async function createRilievoPhotoUrls(paths) {
  if (!paths?.length || !supabaseConfigured || !supabase) return [];
  const { data, error } = await supabase.storage
    .from(CAMPO_PHOTO_BUCKET)
    .createSignedUrls(paths, 5 * 60);
  if (error) throw new Error(error.message || "Foto non disponibili.");
  return (data || []).map((item, index) => ({
    path: paths[index],
    url: item.signedUrl,
  }));
}
