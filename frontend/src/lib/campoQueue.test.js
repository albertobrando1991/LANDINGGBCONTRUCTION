const mockDb = new Map();

jest.mock("idb-keyval", () => ({
  createStore: () => ({}),
  set: async (key, value) => mockDb.set(key, value),
  get: async (key) => mockDb.get(key),
  keys: async () => Array.from(mockDb.keys()),
  del: async (key) => mockDb.delete(key),
}));

import {
  enqueueCampoMeasurement,
  listQueuedCampoMeasurements,
  replaceQueuedCampoMeasurement,
  syncQueuedCampoMeasurements,
} from "./campoQueue";

const UUID = "10000000-0000-4000-8000-000000000001";

beforeEach(() => mockDb.clear());

function queuedItem(overrides = {}) {
  return {
    tenant_slug: "gbconstruction",
    cantiere_id: "20000000-0000-4000-8000-000000000001",
    body: { client_uuid: UUID, qta: 2, foto_paths: [] },
    photos: [{ id: "30000000-0000-4000-8000-000000000001" }],
    ...overrides,
  };
}

test("mantiene foto e client_uuid nella coda IndexedDB", async () => {
  await enqueueCampoMeasurement(queuedItem());
  const items = await listQueuedCampoMeasurements("gbconstruction");
  expect(items).toHaveLength(1);
  expect(items[0].body.client_uuid).toBe(UUID);
  expect(items[0].photos).toHaveLength(1);
});

test("rimuove una misura soltanto dopo una sincronizzazione riuscita", async () => {
  await enqueueCampoMeasurement(queuedItem());
  const failed = await syncQueuedCampoMeasurements(async () => {
    throw new Error("offline");
  }, "gbconstruction");
  expect(failed.failures).toHaveLength(1);
  expect(await listQueuedCampoMeasurements("gbconstruction")).toHaveLength(1);

  const sent = [];
  const completed = await syncQueuedCampoMeasurements(
    async (item) => sent.push(item.body.client_uuid),
    "gbconstruction",
  );
  expect(completed.synced).toBe(1);
  expect(sent).toEqual([UUID]);
  expect(await listQueuedCampoMeasurements("gbconstruction")).toHaveLength(0);
});

test("persiste i path caricati prima del post della misura", async () => {
  const item = await enqueueCampoMeasurement(queuedItem());
  await replaceQueuedCampoMeasurement({
    ...item,
    body: { ...item.body, foto_paths: ["tenant/cantiere/foto.jpg"] },
    photos: [],
  });
  const [stored] = await listQueuedCampoMeasurements("gbconstruction");
  expect(stored.body.foto_paths).toEqual(["tenant/cantiere/foto.jpg"]);
  expect(stored.photos).toEqual([]);
});

test("non supera una misura fallita per preservare l'ordine del libretto", async () => {
  await enqueueCampoMeasurement(queuedItem());
  await enqueueCampoMeasurement(
    queuedItem({
      body: {
        client_uuid: "40000000-0000-4000-8000-000000000001",
        qta: 3,
        foto_paths: [],
      },
    }),
  );
  const sent = [];
  const result = await syncQueuedCampoMeasurements(async (item) => {
    sent.push(item.body.client_uuid);
    throw new Error("connessione interrotta");
  }, "gbconstruction");

  expect(sent).toEqual([UUID]);
  expect(result.failures).toHaveLength(1);
  expect(await listQueuedCampoMeasurements("gbconstruction")).toHaveLength(2);
});
