import { compressWithSurface, computeTargetSize } from "./photoCompression";

test.each([
  [4000, 3000, 1600, { width: 1600, height: 1200 }],
  [800, 1200, 1600, { width: 800, height: 1200 }],
  [3000, 4000, 1600, { width: 1200, height: 1600 }],
])(
  "calcola il target senza deformare %sx%s",
  (width, height, edge, expected) => {
    expect(computeTargetSize(width, height, edge)).toEqual(expected);
  },
);

test("comprime usando una superficie OffscreenCanvas compatibile", async () => {
  const blob = new Blob(["jpeg"], { type: "image/jpeg" });
  const drawImage = jest.fn();
  const surface = {
    width: 1600,
    height: 1200,
    getContext: () => ({ drawImage }),
    convertToBlob: jest.fn().mockResolvedValue(blob),
  };
  await expect(compressWithSurface({}, surface, 0.78)).resolves.toBe(blob);
  expect(drawImage).toHaveBeenCalledWith({}, 0, 0, 1600, 1200);
});
