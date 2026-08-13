import { queryRetryDelay, shouldRetryQuery } from "./queryPolicy";

test("non ripete errori client definitivi", () => {
  for (const status of [400, 401, 403, 404, 409, 422]) {
    expect(shouldRetryQuery(0, { response: { status } })).toBe(false);
  }
});

test("ripete solo due volte errori temporanei o di rete", () => {
  expect(shouldRetryQuery(0, {})).toBe(true);
  expect(shouldRetryQuery(1, { response: { status: 503 } })).toBe(true);
  expect(shouldRetryQuery(2, { response: { status: 503 } })).toBe(false);
  expect(shouldRetryQuery(0, { response: { status: 429 } })).toBe(true);
});

test("limita il backoff e rispetta Retry-After", () => {
  expect(queryRetryDelay(0)).toBe(500);
  expect(queryRetryDelay(5)).toBe(2000);
  expect(
    queryRetryDelay(0, { response: { headers: { "retry-after": "3" } } }),
  ).toBe(3000);
});
