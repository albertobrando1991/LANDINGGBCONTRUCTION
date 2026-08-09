import client from "./api";

export const loadComputiPage = () => import("../dashboard/pages/Computi");

export const loadComputoEditorPage = () =>
  import("../dashboard/pages/ComputoEditor");

export const fetchComputi = async () => (await client.get("/computi")).data;

export const fetchComputo = async ({ queryKey }) =>
  (await client.get(`/computi/${queryKey[1]}`)).data;

export function prefetchComputi(queryClient) {
  void loadComputiPage();
  return queryClient.prefetchQuery({
    queryKey: ["computi"],
    queryFn: fetchComputi,
    staleTime: 60_000,
  });
}

export function prefetchComputo(queryClient, computoId) {
  if (!computoId) return Promise.resolve();
  void loadComputoEditorPage();
  return queryClient.prefetchQuery({
    queryKey: ["computo", computoId],
    queryFn: fetchComputo,
    staleTime: 60_000,
  });
}
