jest.mock("./supabase", () => ({
  SUPABASE_URL: "https://example.supabase.co",
  supabase: null,
  supabaseConfigured: false,
}));

jest.mock("./storage", () => ({
  canUseTenantStorage: jest.fn(() => false),
  tenantIdFromUser: jest.fn(() => ""),
}));

import {
  campoPhotoPath,
  rilievoGeneralPhotoPath,
  rilievoPhotoPath,
  uploadCampoPhotos,
} from "./campoPhotos";

const TENANT = "10000000-0000-4000-8000-000000000001";
const CANTIERE = "20000000-0000-4000-8000-000000000001";
const CLIENT = "30000000-0000-4000-8000-000000000001";
const PHOTO = "40000000-0000-4000-8000-000000000001";

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
