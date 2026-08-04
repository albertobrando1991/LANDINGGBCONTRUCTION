import client, { setApiAccessToken } from "./api";

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
