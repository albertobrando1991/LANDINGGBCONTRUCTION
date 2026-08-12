const mockDb = new Map();

jest.mock("idb-keyval", () => ({
  createStore: () => ({}),
  set: async (key, value) => mockDb.set(key, value),
  get: async (key) => mockDb.get(key),
  keys: async () => Array.from(mockDb.keys()),
  del: async (key) => mockDb.delete(key),
}));

jest.mock("./api", () => ({
  __esModule: true,
  default: { request: jest.fn() },
}));

import client from "./api";
import {
  enqueueOfflineOperation,
  listOfflineOperations,
  runOrQueueJson,
  syncOfflineOperations,
} from "./offlineStore";

beforeEach(() => {
  mockDb.clear();
  jest.clearAllMocks();
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });
});

test("accorpa patch offline dello stesso cantiere senza perdere campi", async () => {
  await enqueueOfflineOperation({
    id: "11111111-1111-4111-8111-111111111111",
    type: "json",
    tenant_slug: "gbconstruction",
    user_id: "user-1",
    method: "patch",
    url: "/cantieri/c1",
    data: { avanzamento: 40 },
    coalesce_key: "cantiere:c1",
  });
  await enqueueOfflineOperation({
    id: "22222222-2222-4222-8222-222222222222",
    type: "json",
    tenant_slug: "gbconstruction",
    user_id: "user-1",
    method: "patch",
    url: "/cantieri/c1",
    data: { criticita: "Materiale in ritardo" },
    coalesce_key: "cantiere:c1",
  });

  const queued = await listOfflineOperations("gbconstruction", "user-1");
  expect(queued).toHaveLength(1);
  expect(queued[0].data).toEqual({
    avanzamento: 40,
    criticita: "Materiale in ritardo",
  });
});

test("assegna un client_id stabile e rimuove solo dopo il sync riuscito", async () => {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: false,
  });
  const saved = await runOrQueueJson({
    tenantSlug: "gbconstruction",
    userId: "user-1",
    method: "post",
    url: "/cantieri/c1/presenze",
    data: { personale_id: "persona-1" },
    clientId: true,
  });
  expect(saved.queued).toBe(true);
  expect(saved.operation.data.client_id).toBe(saved.operation.id);

  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: true,
  });
  client.request.mockRejectedValueOnce(new Error("offline"));
  const failed = await syncOfflineOperations("gbconstruction", "user-1");
  expect(failed.failures).toHaveLength(1);
  expect(await listOfflineOperations("gbconstruction", "user-1")).toHaveLength(
    1,
  );

  client.request.mockResolvedValueOnce({ data: { id: saved.operation.id } });
  const completed = await syncOfflineOperations("gbconstruction", "user-1");
  expect(completed.synced).toBe(1);
  expect(await listOfflineOperations("gbconstruction", "user-1")).toHaveLength(
    0,
  );
});

test("un secondo salvataggio della stessa presenza riusa lo stesso client_id", async () => {
  Object.defineProperty(navigator, "onLine", {
    configurable: true,
    value: false,
  });
  const options = {
    tenantSlug: "gbconstruction",
    userId: "user-1",
    method: "post",
    url: "/cantieri/c1/presenze",
    coalesceKey: "presenza:c1:p1:2026-08-12",
    clientId: true,
  };
  const first = await runOrQueueJson({
    ...options,
    data: { personale_id: "p1", unita_presenti: 1 },
  });
  const second = await runOrQueueJson({
    ...options,
    data: { personale_id: "p1", unita_presenti: 3 },
  });

  const [queued] = await listOfflineOperations("gbconstruction", "user-1");
  expect(queued.id).toBe(first.operation.id);
  expect(queued.id).toBe(second.operation.id);
  expect(queued.data.client_id).toBe(first.operation.id);
  expect(queued.data.unita_presenti).toBe(3);
});
