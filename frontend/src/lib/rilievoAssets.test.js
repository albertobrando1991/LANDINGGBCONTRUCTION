jest.mock("./api", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));
jest.mock("./supabase", () => ({
  supabase: null,
  supabaseConfigured: false,
}));
jest.mock("./storage", () => ({
  canUseTenantStorage: jest.fn(() => false),
  sanitizeStorageFilename: (value) => value,
  tenantIdFromUser: jest.fn(() => ""),
}));

import {
  createRilievoPlanUrl,
  MAX_RILIEVO_PLAN_BYTES,
  rilievoPlanPath,
  uploadRilievoPlan,
  validateRilievoPlan,
} from "./rilievoAssets";
import client from "./api";

const TENANT = "10000000-0000-4000-8000-000000000001";
const RILIEVO = "20000000-0000-4000-8000-000000000001";

beforeEach(() => jest.clearAllMocks());

test("valida formati e dimensione della planimetria", () => {
  expect(
    validateRilievoPlan({
      name: "casa.pdf",
      type: "application/pdf",
      size: 1024,
    }),
  ).toBe("application/pdf");
  expect(() =>
    validateRilievoPlan({
      name: "casa.pdf",
      type: "application/pdf",
      size: MAX_RILIEVO_PLAN_BYTES + 1,
    }),
  ).toThrow("25 MB");
});

test("genera un path planimetria tenant-scoped", () => {
  expect(
    rilievoPlanPath({
      tenantId: TENANT,
      rilievoId: RILIEVO,
      filename: "casa.pdf",
      kind: "originale",
    }),
  ).toBe(`${TENANT}/rilievo-${RILIEVO}/planimetria/originale-casa.pdf`);
});

test("carica la planimetria tramite backend anche senza sessione Supabase", async () => {
  client.post
    .mockResolvedValueOnce({
      data: {
        path: `${TENANT}/rilievo-${RILIEVO}/planimetria/originale.pdf`,
        mime_type: "application/pdf",
      },
    })
    .mockResolvedValueOnce({
      data: {
        path: `${TENANT}/rilievo-${RILIEVO}/planimetria/preview.png`,
        mime_type: "image/png",
      },
    });
  const file = new File(["%PDF-1.4"], "casa.pdf", {
    type: "application/pdf",
  });

  const result = await uploadRilievoPlan({
    user: { auth_provider: "legacy" },
    rilievoId: RILIEVO,
    file,
    previewBlob: new Blob(["png"], { type: "image/png" }),
  });

  expect(client.post).toHaveBeenCalledTimes(2);
  expect(result.planimetria_preview_path).toContain("preview.png");
});

test("richiede al backend una URL temporanea per riaprire la planimetria", async () => {
  const path = `${TENANT}/rilievo-${RILIEVO}/planimetria/originale.pdf`;
  client.post.mockResolvedValueOnce({
    data: [{ path, url: "https://storage.example/signed" }],
  });

  await expect(createRilievoPlanUrl(path, RILIEVO)).resolves.toBe(
    "https://storage.example/signed",
  );
  expect(client.post).toHaveBeenCalledWith(
    `/campo/rilievi/${RILIEVO}/assets/urls`,
    { bucket: "planimetrie", paths: [path] },
  );
});
