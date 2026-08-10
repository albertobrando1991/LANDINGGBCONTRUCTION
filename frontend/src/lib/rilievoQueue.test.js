const mockDb = new Map();

jest.mock("idb-keyval", () => ({
  createStore: () => ({}),
  set: async (key, value) => mockDb.set(key, value),
  get: async (key) => mockDb.get(key),
  keys: async () => Array.from(mockDb.keys()),
  del: async (key) => mockDb.delete(key),
}));

import {
  enqueueRilievoOperation,
  listRilievoOperations,
  syncRilievoOperations,
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
