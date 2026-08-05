import client, { backendUrlForHostname, setApiAccessToken } from "./api";

function inspectRequest(config) {
  return Promise.resolve({
    data: {
      authorization: config.headers.Authorization || null,
      tenant: config.headers["X-Tenant-Slug"] || null,
    },
    status: 200,
    statusText: "OK",
    headers: {},
    config,
  });
}

afterEach(() => {
  setApiAccessToken(null);
});

test("usa il proxy same-origin nelle Preview Vercel", () => {
  expect(
    backendUrlForHostname(
      "gb-construction-git-develop-capitale-personales-projects.vercel.app",
    ),
  ).toBe("");
  expect(
    backendUrlForHostname(
      "gb-construction-9kc585bds-capitale-personales-projects.vercel.app",
    ),
  ).toBe("");
});

test("mantiene l'API ufficiale sui domini GB Construction", () => {
  expect(backendUrlForHostname("app.gbconstruction.it")).toBe(
    "https://api.gbconstruction.it",
  );
  expect(backendUrlForHostname("gbconstruction.it")).toBe(
    "https://api.gbconstruction.it",
  );
});

test("aggiunge il bearer Supabase alle richieste API", async () => {
  setApiAccessToken("supabase-session");
  const response = await client.get("/auth/me", { adapter: inspectRequest });

  expect(response.data.authorization).toBe("Bearer supabase-session");
  expect(response.data.tenant).toBe("gbconstruction");
});

test("mantiene un header Authorization esplicito", async () => {
  setApiAccessToken("supabase-session");
  const response = await client.get("/auth/me", {
    headers: { Authorization: "Bearer explicit-session" },
    adapter: inspectRequest,
  });

  expect(response.data.authorization).toBe("Bearer explicit-session");
});
