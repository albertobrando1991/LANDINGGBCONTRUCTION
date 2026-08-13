import client, {
  API_PERFORMANCE_EVENT,
  backendUrlForHostname,
  extractErrorDetail,
  setApiAccessToken,
} from "./api";

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

test("misura tutte le richieste API e separa tempo server da rete e client", async () => {
  const measurements = [];
  const listener = (event) => measurements.push(event.detail);
  window.addEventListener(API_PERFORMANCE_EVENT, listener);
  const response = await client.get("/cantieri", {
    adapter: async (config) => ({
      data: [],
      status: 200,
      statusText: "OK",
      headers: { "x-response-time-ms": "12.5" },
      config,
    }),
  });
  window.removeEventListener(API_PERFORMANCE_EVENT, listener);

  expect(response.durationMs).toBeGreaterThanOrEqual(0);
  expect(measurements.at(-1)).toEqual(
    expect.objectContaining({
      method: "GET",
      url: "/cantieri",
      status: 200,
      serverDurationMs: 12.5,
    }),
  );
});

test("legge il dettaglio di un errore JSON normale", async () => {
  const error = { response: { data: { detail: "Conferma il computo prima" } } };
  await expect(extractErrorDetail(error)).resolves.toBe(
    "Conferma il computo prima",
  );
});

test("legge il dettaglio anche quando axios scarica l'errore come Blob", async () => {
  // Con responseType: "blob" axios applica lo stesso parsing anche alle
  // risposte di errore: il body JSON del backend arriva come Blob binario.
  const blob = new Blob(
    [JSON.stringify({ detail: "Computo non confermato" })],
    {
      type: "application/json",
    },
  );
  const error = { response: { data: blob } };

  await expect(extractErrorDetail(error)).resolves.toBe(
    "Computo non confermato",
  );
});

test("usa il messaggio generico quando non c'e nulla da leggere", async () => {
  await expect(extractErrorDetail({})).resolves.toBe(
    "Si è verificato un errore. Riprova.",
  );
  const brokenBlob = new Blob(["<html>502</html>"], { type: "text/html" });
  await expect(
    extractErrorDetail({ response: { data: brokenBlob } }),
  ).resolves.toBe("Si è verificato un errore. Riprova.");
});
