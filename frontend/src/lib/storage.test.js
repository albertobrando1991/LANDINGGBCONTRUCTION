import { supabase } from "./supabase";
import {
  canUseTenantStorage,
  cantiereDocumentPath,
  createCantiereDocumentUrl,
  displayStorageFilename,
  listCantiereDocuments,
  tenantIdFromUser,
  uploadCantiereDocument,
  validateCantiereDocument,
} from "./storage";

jest.mock("./supabase", () => {
  const bucket = {
    upload: jest.fn(),
    list: jest.fn(),
    createSignedUrl: jest.fn(),
  };
  return {
    supabaseConfigured: true,
    supabase: {
      storage: { from: jest.fn(() => bucket) },
      __bucket: bucket,
    },
  };
});

const TENANT_ID = "a0000000-0000-4000-8000-000000000001";
const CANTIERE_ID = "64b64c0aa111111111111111";

beforeEach(() => {
  jest.clearAllMocks();
  supabase.storage.from.mockImplementation(() => supabase.__bucket);
});

test("abilita Storage solo per una sessione Supabase interna al tenant", () => {
  const staff = {
    auth_provider: "supabase",
    role: "staff",
    app_tenants: [{ t: TENANT_ID, r: "staff" }],
  };
  expect(tenantIdFromUser(staff)).toBe(TENANT_ID);
  expect(canUseTenantStorage(staff)).toBe(true);
  expect(canUseTenantStorage({ ...staff, role: "client" })).toBe(false);
  expect(canUseTenantStorage({ ...staff, auth_provider: "legacy" })).toBe(
    false,
  );
});

test("costruisce un path tenant-scoped e ripristina il nome visibile", () => {
  const path = cantiereDocumentPath({
    tenantId: TENANT_ID,
    cantiereId: CANTIERE_ID,
    filename: "Computo metrico n° 4.pdf",
    nonce: "1700000000000-abcdef12",
  });
  expect(path).toBe(
    `${TENANT_ID}/cantiere-${CANTIERE_ID}/1700000000000-abcdef12-Computo-metrico-n-4.pdf`,
  );
  expect(displayStorageFilename(path.split("/").pop())).toBe(
    "Computo-metrico-n-4.pdf",
  );
});

test("rifiuta formati e dimensioni non ammessi", () => {
  expect(() =>
    validateCantiereDocument({
      name: "script.exe",
      type: "application/octet-stream",
      size: 100,
    }),
  ).toThrow("Formato non supportato");
  expect(() =>
    validateCantiereDocument({
      name: "enorme.pdf",
      type: "application/pdf",
      size: 26 * 1024 * 1024,
    }),
  ).toThrow("25 MB");
});

test("carica senza upsert nel bucket documenti", async () => {
  supabase.__bucket.upload.mockResolvedValue({
    data: { path: "saved" },
    error: null,
  });
  const file = { name: "SAL.pdf", type: "application/pdf", size: 1024 };

  const result = await uploadCantiereDocument({
    tenantId: TENANT_ID,
    cantiereId: CANTIERE_ID,
    file,
  });

  expect(supabase.storage.from).toHaveBeenCalledWith("documenti");
  expect(supabase.__bucket.upload).toHaveBeenCalledWith(
    expect.stringMatching(
      new RegExp(`^${TENANT_ID}/cantiere-${CANTIERE_ID}/.+-SAL\\.pdf$`),
    ),
    file,
    {
      cacheControl: "3600",
      contentType: "application/pdf",
      upsert: false,
    },
  );
  expect(result.displayName).toBe("SAL.pdf");
});

test("lista i file e firma soltanto path dello stesso cantiere", async () => {
  const storedName = "1700000000000-abcdef12-SAL.pdf";
  const expectedPath = `${TENANT_ID}/cantiere-${CANTIERE_ID}/${storedName}`;
  supabase.__bucket.list.mockResolvedValue({
    data: [
      {
        id: "object-1",
        name: storedName,
        created_at: "2026-08-04T12:00:00Z",
        metadata: { size: 2048, mimetype: "application/pdf" },
      },
    ],
    error: null,
  });
  supabase.__bucket.createSignedUrl.mockResolvedValue({
    data: { signedUrl: "https://storage.test/signed" },
    error: null,
  });

  const rows = await listCantiereDocuments({
    tenantId: TENANT_ID,
    cantiereId: CANTIERE_ID,
  });
  expect(rows[0]).toMatchObject({
    id: "object-1",
    displayName: "SAL.pdf",
    path: expectedPath,
    size: 2048,
  });

  await expect(
    createCantiereDocumentUrl({
      tenantId: TENANT_ID,
      cantiereId: CANTIERE_ID,
      path: expectedPath,
      downloadName: "SAL.pdf",
    }),
  ).resolves.toBe("https://storage.test/signed");
  expect(supabase.__bucket.createSignedUrl).toHaveBeenCalledWith(
    expectedPath,
    300,
    { download: "SAL.pdf" },
  );

  await expect(
    createCantiereDocumentUrl({
      tenantId: TENANT_ID,
      cantiereId: CANTIERE_ID,
      path: `${TENANT_ID}/cantiere-altro/segreto.pdf`,
      downloadName: "segreto.pdf",
    }),
  ).rejects.toThrow("non autorizzato");
});
