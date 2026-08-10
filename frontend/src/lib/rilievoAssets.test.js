jest.mock("./api", () => ({ post: jest.fn() }));
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
  MAX_RILIEVO_PLAN_BYTES,
  rilievoPlanPath,
  validateRilievoPlan,
} from "./rilievoAssets";

const TENANT = "10000000-0000-4000-8000-000000000001";
const RILIEVO = "20000000-0000-4000-8000-000000000001";

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
