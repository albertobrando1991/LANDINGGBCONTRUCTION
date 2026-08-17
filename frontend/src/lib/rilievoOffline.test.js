jest.mock("./rilievoApi", () => ({ loadRilievo: jest.fn() }));
jest.mock("./rilievoAssets", () => ({
  createRilievoPlanUrls: jest.fn(),
}));
jest.mock("./campoPhotos", () => ({
  createRilievoPhotoUrls: jest.fn(),
}));
jest.mock("./offlineStorage", () => ({
  requestPersistentOfflineStorage: jest.fn(),
}));
jest.mock("./rilievoQueue", () => ({
  cacheRilievoAsset: jest.fn(),
  cacheRilievoOfflinePack: jest.fn(async (_slug, _id, pack) => pack),
  readCachedRilievoAsset: jest.fn(),
  upsertCachedRilievo: jest.fn(),
}));

import { prepareRilievoOffline } from "./rilievoOffline";
import { loadRilievo } from "./rilievoApi";
import { createRilievoPlanUrls } from "./rilievoAssets";
import { createRilievoPhotoUrls } from "./campoPhotos";
import { requestPersistentOfflineStorage } from "./offlineStorage";
import {
  cacheRilievoAsset,
  cacheRilievoOfflinePack,
  readCachedRilievoAsset,
  upsertCachedRilievo,
} from "./rilievoQueue";

const RILIEVO_ID = "10000000-0000-4000-8000-000000000001";

beforeEach(() => {
  jest.clearAllMocks();
  requestPersistentOfflineStorage.mockResolvedValue({ persisted: true });
  readCachedRilievoAsset.mockResolvedValue(undefined);
  cacheRilievoOfflinePack.mockImplementation(async (_slug, _id, pack) => pack);
});

test("prepara dettaglio, planimetria e foto per l'uso offline", async () => {
  const rilievo = {
    id: RILIEVO_ID,
    planimetria_preview_path: "tenant/preview.png",
    planimetria_path: "tenant/plan.pdf",
    foto_paths: ["tenant/generale.jpg"],
    ambienti: [{ foto_paths: ["tenant/cucina.jpg"] }],
  };
  loadRilievo.mockResolvedValue(rilievo);
  createRilievoPlanUrls.mockImplementation(async (paths) =>
    paths.map((path) => ({ path, url: `https://storage/${path}` })),
  );
  createRilievoPhotoUrls.mockImplementation(async (paths) =>
    paths.map((path) => ({ path, url: `https://storage/${path}` })),
  );
  const blob = new Blob(["asset"], { type: "application/octet-stream" });
  const fetchFn = jest.fn(async () => ({
    ok: true,
    blob: async () => blob,
  }));

  const result = await prepareRilievoOffline({
    tenantSlug: "gbconstruction",
    rilievoId: RILIEVO_ID,
    fetchFn,
  });

  expect(upsertCachedRilievo).toHaveBeenCalledWith("gbconstruction", rilievo);
  expect(fetchFn).toHaveBeenCalledTimes(4);
  expect(cacheRilievoAsset).toHaveBeenCalledTimes(4);
  expect(cacheRilievoOfflinePack).toHaveBeenCalledWith(
    "gbconstruction",
    RILIEVO_ID,
    expect.objectContaining({
      ready: true,
      assets_total: 4,
      assets_cached: 4,
      persistent: true,
    }),
  );
  expect(result.failures).toEqual([]);
});

test("segnala un pacchetto parziale senza perdere gli allegati riusciti", async () => {
  loadRilievo.mockResolvedValue({
    id: RILIEVO_ID,
    foto_paths: ["tenant/ok.jpg", "tenant/ko.jpg"],
    ambienti: [],
  });
  createRilievoPlanUrls.mockResolvedValue([]);
  createRilievoPhotoUrls.mockImplementation(async (paths) =>
    paths.map((path) => ({ path, url: `https://storage/${path}` })),
  );
  const fetchFn = jest.fn(async (url) => {
    if (url.endsWith("ko.jpg")) return { ok: false, status: 503 };
    return { ok: true, blob: async () => new Blob(["ok"]) };
  });

  const result = await prepareRilievoOffline({
    tenantSlug: "gbconstruction",
    rilievoId: RILIEVO_ID,
    fetchFn,
  });

  expect(result.pack.ready).toBe(false);
  expect(result.pack.assets_cached).toBe(1);
  expect(result.failures).toHaveLength(1);
  expect(cacheRilievoAsset).toHaveBeenCalledTimes(1);
});
