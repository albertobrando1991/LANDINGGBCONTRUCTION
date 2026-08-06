import { supabase, supabaseConfigured } from "./supabase";

export const PORTAL_BUCKETS = new Set(["documenti", "foto-cantiere"]);
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function portalSummary(data = {}) {
  const cantieri = data.cantieri || [];
  const sal = data.sal || [];
  const varianti = data.varianti || [];
  return {
    cantieri: cantieri.length,
    avanzamento: cantieri.length
      ? Math.round(
          cantieri.reduce(
            (sum, item) => sum + Number(item.avanzamento || 0),
            0,
          ) / cantieri.length,
        )
      : 0,
    salApprovati: sal.length,
    variantiDaApprovare: varianti.filter((item) => !item.approvata).length,
  };
}

export function portalAssetsByType(assets = []) {
  return {
    foto: assets.filter((item) => item.tipo === "foto"),
    documenti: assets.filter((item) => item.tipo === "documento"),
  };
}

export function validatePortalAsset(asset) {
  if (!PORTAL_BUCKETS.has(asset?.bucket))
    throw new Error("Archivio non valido.");
  const tenantId = String(asset?.tenant_id || "");
  const cantiereId = String(asset?.cantiere_id || "");
  if (!UUID_RE.test(tenantId) || !UUID_RE.test(cantiereId)) {
    throw new Error("Riferimento cantiere non valido.");
  }
  const prefix = `${tenantId}/cantiere-${cantiereId}/`;
  if (!String(asset?.storage_path || "").startsWith(prefix)) {
    throw new Error("Percorso file non autorizzato.");
  }
  return asset;
}

export async function createPortalAssetUrl(asset) {
  if (!supabaseConfigured || !supabase) {
    throw new Error("Archivio cliente non configurato.");
  }
  validatePortalAsset(asset);
  const { data, error } = await supabase.storage
    .from(asset.bucket)
    .createSignedUrl(asset.storage_path, 5 * 60, {
      download: asset.tipo === "documento" ? asset.titolo : false,
    });
  if (error || !data?.signedUrl) {
    throw new Error(error?.message || "File non disponibile.");
  }
  return data.signedUrl;
}
