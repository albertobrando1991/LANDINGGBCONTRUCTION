const mockDb = new Map();

jest.mock("idb-keyval", () => ({
  createStore: () => ({}),
  set: async (key, value) => mockDb.set(key, value),
  get: async (key) => mockDb.get(key),
  keys: async () => Array.from(mockDb.keys()),
  del: async (key) => mockDb.delete(key),
}));

import {
  createOfflineRilievo,
  enqueueRilievoOperation,
  listRilievoOperations,
  promoteCachedRilievo,
  readCachedRilievo,
  resolveRilievoId,
  saveRilievoIdResolution,
  syncRilievoOperations,
  upsertCachedRilievo,
} from "./rilievoQueue";

const RILIEVO_ID = "10000000-0000-4000-8000-000000000001";
const AMBIENTE_ID = "20000000-0000-4000-8000-000000000001";

beforeEach(() => mockDb.clear());

function roomOperation(overrides = {}) {
  return {
    kind: "ambiente",
    entity_id: `${RILIEVO_ID}:${AMBIENTE_ID}`,
    rilievo_id: RILIEVO_ID,
    ambiente_client_uuid: AMBIENTE_ID,
    body: { nome: "Cucina", foto_paths: [] },
    photos: [{ id: "30000000-0000-4000-8000-000000000001" }],
    ...overrides,
  };
}

test("accorpa gli autosalvataggi dello stesso ambiente mantenendo la coda", async () => {
  await enqueueRilievoOperation("gbconstruction", roomOperation());
  await enqueueRilievoOperation(
    "gbconstruction",
    roomOperation({ body: { nome: "Cucina principale", foto_paths: [] } }),
  );

  const queued = await listRilievoOperations("gbconstruction");
  expect(queued).toHaveLength(1);
  expect(queued[0].body.nome).toBe("Cucina principale");
  expect(queued[0].photos).toHaveLength(1);
});

test("rimuove una modifica solo dopo la sincronizzazione riuscita", async () => {
  await enqueueRilievoOperation("gbconstruction", roomOperation());

  const failed = await syncRilievoOperations("gbconstruction", async () => {
    throw new Error("offline");
  });
  expect(failed.failures).toHaveLength(1);
  expect(await listRilievoOperations("gbconstruction")).toHaveLength(1);

  const sent = [];
  const completed = await syncRilievoOperations(
    "gbconstruction",
    async (operation) => sent.push(operation.body.nome),
  );
  expect(completed.synced).toBe(1);
  expect(sent).toEqual(["Cucina"]);
  expect(await listRilievoOperations("gbconstruction")).toHaveLength(0);
});

test("conserva offline tavola, planimetria e foto generali", async () => {
  const plan = new Blob(["planimetria"], { type: "image/png" });
  const photo = new Blob(["foto"], { type: "image/jpeg" });
  await enqueueRilievoOperation("gbconstruction", {
    kind: "tavola",
    entity_id: RILIEVO_ID,
    rilievo_id: RILIEVO_ID,
    body: {
      elementi: [{ id: "muro-1", tipo: "muro" }],
      foto_paths: [],
    },
    plan_file: plan,
    plan_preview: plan,
    photos: [{ id: "foto-1", blob: photo }],
  });

  const [queued] = await listRilievoOperations("gbconstruction");
  expect(queued.kind).toBe("tavola");
  expect(queued.plan_file).toBe(plan);
  expect(queued.photos[0].blob).toBe(photo);
});

test("ordina creazione, contenuti e completamento dello stesso rilievo", async () => {
  await enqueueRilievoOperation("gbconstruction", {
    kind: "rilievo-stato",
    entity_id: RILIEVO_ID,
    rilievo_id: RILIEVO_ID,
    body: { stato: "completato" },
  });
  await enqueueRilievoOperation("gbconstruction", roomOperation());
  await enqueueRilievoOperation("gbconstruction", {
    kind: "rilievo-crea",
    entity_id: RILIEVO_ID,
    rilievo_id: RILIEVO_ID,
    body: { client_uuid: RILIEVO_ID, cliente: "Cliente" },
  });

  const queued = await listRilievoOperations("gbconstruction");
  expect(queued.map((item) => item.kind)).toEqual([
    "rilievo-crea",
    "ambiente",
    "rilievo-stato",
  ]);
});

test("non completa un rilievo se una dipendenza precedente fallisce", async () => {
  await enqueueRilievoOperation("gbconstruction", roomOperation());
  await enqueueRilievoOperation("gbconstruction", {
    kind: "rilievo-stato",
    entity_id: RILIEVO_ID,
    rilievo_id: RILIEVO_ID,
    body: { stato: "completato" },
  });
  const sent = [];
  const result = await syncRilievoOperations(
    "gbconstruction",
    async (operation) => {
      sent.push(operation.kind);
      if (operation.kind === "ambiente") throw new Error("upload non riuscito");
    },
  );

  expect(sent).toEqual(["ambiente"]);
  expect(result.failures).toHaveLength(2);
  expect(result.failures[1].blocked).toBe(true);
  expect(await listRilievoOperations("gbconstruction")).toHaveLength(2);
});

test("mantiene la risoluzione locale-server e promuove la cache", async () => {
  const local = createOfflineRilievo(
    {
      client_uuid: RILIEVO_ID,
      cliente: "Cliente offline",
      data_rilievo: "2026-08-17",
    },
    RILIEVO_ID,
  );
  await upsertCachedRilievo("gbconstruction", local);
  const serverId = "40000000-0000-4000-8000-000000000001";
  await saveRilievoIdResolution("gbconstruction", RILIEVO_ID, serverId);
  const promoted = await promoteCachedRilievo("gbconstruction", RILIEVO_ID, {
    id: serverId,
    client_uuid: RILIEVO_ID,
    cliente: "Cliente offline",
    stato: "bozza",
  });

  expect(await resolveRilievoId("gbconstruction", RILIEVO_ID)).toBe(serverId);
  expect(promoted.offline_pending).toBe(false);
  expect(await readCachedRilievo("gbconstruction", RILIEVO_ID)).toBeUndefined();
  expect((await readCachedRilievo("gbconstruction", serverId)).id).toBe(
    serverId,
  );
});
