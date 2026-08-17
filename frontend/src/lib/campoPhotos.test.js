jest.mock("./supabase", () => ({
  SUPABASE_URL: "https://example.supabase.co",
  supabase: null,
  supabaseConfigured: false,
}));

jest.mock("./api", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

jest.mock("./storage", () => ({
  canUseTenantStorage: jest.fn(() => false),
  tenantIdFromUser: jest.fn(() => ""),
}));

jest.mock("./photoCompressorClient", () => ({
  compressPhotoInWorker: jest.fn(),
}));

import {
  campoPhotoPath,
  rilievoGeneralPhotoPath,
  rilievoPhotoPath,
  uploadCampoPhotos,
  uploadRilievoGeneralPhotos,
} from "./campoPhotos";
import client from "./api";

const TENANT = "10000000-0000-4000-8000-000000000001";
const CANTIERE = "20000000-0000-4000-8000-000000000001";
const CLIENT = "30000000-0000-4000-8000-000000000001";
const PHOTO = "40000000-0000-4000-8000-000000000001";

beforeEach(() => jest.clearAllMocks());

test("genera un path foto tenant-scoped accettato dal backend", () => {
  expect(
    campoPhotoPath({
      tenantId: TENANT,
      cantiereId: CANTIERE,
      clientUuid: CLIENT,
      photoId: PHOTO,
    }),
  ).toBe(`${TENANT}/cantiere-${CANTIERE}/libretto-${CLIENT}/${PHOTO}.jpg`);
});

test("rifiuta identificatori non UUID nel path storage", () => {
  expect(() =>
    campoPhotoPath({
      tenantId: "../altro-tenant",
      cantiereId: CANTIERE,
      clientUuid: CLIENT,
      photoId: PHOTO,
    }),
  ).toThrow("Tenant non valido");
});

test("genera un path foto ambiente tenant-scoped", () => {
  expect(
    rilievoPhotoPath({
      tenantId: TENANT,
      rilievoId: CANTIERE,
      ambienteClientUuid: CLIENT,
      photoId: PHOTO,
    }),
  ).toBe(`${TENANT}/rilievo-${CANTIERE}/ambiente-${CLIENT}/${PHOTO}.jpg`);
});

test("genera un path foto generale del rilievo tenant-scoped", () => {
  expect(
    rilievoGeneralPhotoPath({
      tenantId: TENANT,
      rilievoId: CANTIERE,
      photoId: PHOTO,
    }),
  ).toBe(`${TENANT}/rilievo-${CANTIERE}/generali/${PHOTO}.jpg`);
});

test("non tenta upload foto senza sessione Supabase interna", async () => {
  await expect(
    uploadCampoPhotos({
      user: {},
      cantiereId: CANTIERE,
      clientUuid: CLIENT,
      photos: [{ id: PHOTO, blob: new Blob(["foto"], { type: "image/jpeg" }) }],
    }),
  ).rejects.toThrow("sessione Supabase interna");
});

test("carica le foto rilievo tramite backend con autenticazione legacy", async () => {
  const path = `${TENANT}/rilievo-${CANTIERE}/generali/${PHOTO}.jpg`;
  client.post.mockResolvedValueOnce({ data: { path } });

  await expect(
    uploadRilievoGeneralPhotos({
      user: { auth_provider: "legacy" },
      rilievoId: CANTIERE,
      photos: [
        {
          id: PHOTO,
          name: "foto.jpg",
          size: 4,
          blob: new Blob(["foto"], { type: "image/jpeg" }),
        },
      ],
    }),
  ).resolves.toEqual([path]);
  expect(client.post).toHaveBeenCalledWith(
    `/campo/rilievi/${CANTIERE}/assets`,
    expect.any(FormData),
    expect.objectContaining({ onUploadProgress: expect.any(Function) }),
  );
  expect(client.post.mock.calls[0][1].get("client_asset_uuid")).toBe(PHOTO);
});

test("carica al massimo tre foto insieme e mantiene l'ordine", async () => {
  let active = 0;
  let peak = 0;
  const progress = jest.fn();
  client.post.mockImplementation(async (_url, form, config) => {
    active += 1;
    peak = Math.max(peak, active);
    config.onUploadProgress({ loaded: 2, total: 4 });
    await new Promise((resolve) => setTimeout(resolve, 5));
    const file = form.get("file");
    config.onUploadProgress({ loaded: 4, total: 4 });
    active -= 1;
    return { data: { path: `path/${file.name}` } };
  });
  const photos = [0, 1, 2, 3].map((index) => ({
    id: `${PHOTO.slice(0, -1)}${index}`,
    name: `foto-${index}.jpg`,
    size: 4,
    blob: new File(["foto"], `foto-${index}.jpg`, { type: "image/jpeg" }),
  }));

  await expect(
    uploadRilievoGeneralPhotos({
      rilievoId: CANTIERE,
      photos,
      onProgress: progress,
    }),
  ).resolves.toEqual(photos.map((photo) => `path/${photo.name}`));
  expect(peak).toBe(3);
  expect(progress).toHaveBeenLastCalledWith({
    uploaded: 16,
    total: 16,
    count: 4,
  });
});
