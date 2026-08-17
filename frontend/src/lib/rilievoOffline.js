import { mapLimit } from "./network";
import { loadRilievo } from "./rilievoApi";
import { createRilievoPlanUrls } from "./rilievoAssets";
import { createRilievoPhotoUrls } from "./campoPhotos";
import {
  cacheRilievoAsset,
  cacheRilievoOfflinePack,
  readCachedRilievoAsset,
  upsertCachedRilievo,
} from "./rilievoQueue";
import { requestPersistentOfflineStorage } from "./offlineStorage";

function unique(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function assetPaths(rilievo) {
  return {
    plans: unique([rilievo.planimetria_preview_path, rilievo.planimetria_path]),
    photos: unique([
      ...(rilievo.foto_paths || []),
      ...(rilievo.ambienti || []).flatMap(
        (ambiente) => ambiente.foto_paths || [],
      ),
    ]),
  };
}

async function downloadAssets(tenantSlug, items, fetchFn) {
  let bytes = 0;
  const failures = [];
  await mapLimit(items, 3, async (item) => {
    try {
      const existing = await readCachedRilievoAsset(tenantSlug, item.path);
      if (existing) {
        bytes += Number(existing.size || 0);
        return;
      }
      const response = await fetchFn(item.url, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      await cacheRilievoAsset(tenantSlug, item.path, blob);
      bytes += Number(blob.size || 0);
    } catch (error) {
      failures.push({ path: item.path, error });
    }
  });
  return { bytes, failures };
}

export async function prepareRilievoOffline({
  tenantSlug,
  rilievoId,
  fetchFn = fetch,
}) {
  const storage = await requestPersistentOfflineStorage();
  const rilievo = await loadRilievo(rilievoId);
  await upsertCachedRilievo(tenantSlug, rilievo);
  const paths = assetPaths(rilievo);
  const [planUrls, photoUrls] = await Promise.all([
    createRilievoPlanUrls(paths.plans, rilievoId),
    createRilievoPhotoUrls(paths.photos, rilievoId),
  ]);
  const assets = [
    ...planUrls.map((item) => ({ ...item, bucket: "planimetrie" })),
    ...photoUrls.map((item) => ({ ...item, bucket: "foto-cantiere" })),
  ];
  const downloaded = await downloadAssets(tenantSlug, assets, fetchFn);
  const pack = await cacheRilievoOfflinePack(tenantSlug, rilievoId, {
    ready: downloaded.failures.length === 0,
    assets_total: assets.length,
    assets_cached: assets.length - downloaded.failures.length,
    bytes: downloaded.bytes,
    persistent: storage.persisted,
    rilievo_updated_at: rilievo.updated_at || null,
    failed_paths: downloaded.failures.map((item) => item.path),
  });
  return { rilievo, pack, failures: downloaded.failures, storage };
}

export async function loadOfflinePhotoPreviews({
  tenantSlug,
  paths,
  rilievoId,
  isOnline,
}) {
  const previews = [];
  const missing = [];
  for (const path of paths || []) {
    const blob = await readCachedRilievoAsset(tenantSlug, path);
    if (blob) {
      previews.push({ path, url: URL.createObjectURL(blob), local: true });
    } else {
      missing.push(path);
    }
  }
  if (isOnline && missing.length && rilievoId) {
    previews.push(...(await createRilievoPhotoUrls(missing, rilievoId)));
  }
  return previews;
}

export async function loadOfflinePlanPreview({
  tenantSlug,
  path,
  rilievoId,
  isOnline,
}) {
  if (!path) return { url: "", local: false };
  const blob = await readCachedRilievoAsset(tenantSlug, path);
  if (blob) return { url: URL.createObjectURL(blob), local: true };
  if (!isOnline || !rilievoId) return { url: "", local: false };
  const [remote] = await createRilievoPlanUrls([path], rilievoId);
  return { url: remote?.url || "", local: false };
}
