import { DEFAULT_TENANT_SLUG, resolveTenantSlug } from "./tenant";

describe("resolveTenantSlug", () => {
  test("mantiene il tenant GB sugli hostname di produzione", () => {
    for (const hostname of [
      "gbconstruction.it",
      "www.gbconstruction.it",
      "app.gbconstruction.it",
    ]) {
      expect(resolveTenantSlug({ search: "", hostname })).toBe(
        DEFAULT_TENANT_SLUG,
      );
    }
  });

  test("non usa i sottodomini alantis per selezionare il tenant", () => {
    expect(resolveTenantSlug({ search: "", hostname: "demo.alantis.it" })).toBe(
      DEFAULT_TENANT_SLUG,
    );
  });

  test("accetta una query tenant valida per i test controllati", () => {
    expect(
      resolveTenantSlug({ search: "?tenant=demo", hostname: "localhost" }),
    ).toBe("demo");
  });

  test("ignora slug non validi", () => {
    expect(
      resolveTenantSlug({ search: "?tenant=../demo", hostname: "localhost" }),
    ).toBe(DEFAULT_TENANT_SLUG);
  });
});
