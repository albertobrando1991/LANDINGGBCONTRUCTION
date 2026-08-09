import client from "./api";
import {
  fetchComputi,
  fetchComputo,
  prefetchComputi,
  prefetchComputo,
} from "./computiPrefetch";

jest.mock("./api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));
jest.mock("../dashboard/pages/Computi", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("../dashboard/pages/ComputoEditor", () => ({
  __esModule: true,
  default: () => null,
}));

beforeEach(() => {
  client.get.mockReset();
});

test("usa le stesse chiavi cache della pagina computi e dell'editor", async () => {
  const prefetchQuery = jest.fn().mockResolvedValue(undefined);
  const queryClient = { prefetchQuery };

  await prefetchComputi(queryClient);
  await prefetchComputo(queryClient, "computo-1");

  expect(prefetchQuery).toHaveBeenNthCalledWith(
    1,
    expect.objectContaining({ queryKey: ["computi"], queryFn: fetchComputi }),
  );
  expect(prefetchQuery).toHaveBeenNthCalledWith(
    2,
    expect.objectContaining({
      queryKey: ["computo", "computo-1"],
      queryFn: fetchComputo,
    }),
  );
});

test("riusa l'id della query per caricare il singolo computo", async () => {
  client.get.mockResolvedValue({ data: { id: "computo-2" } });

  await expect(
    fetchComputo({ queryKey: ["computo", "computo-2"] }),
  ).resolves.toEqual({ id: "computo-2" });
  expect(client.get).toHaveBeenCalledWith("/computi/computo-2");
});
