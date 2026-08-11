import client from "./api";

export async function listCantiereArchive(cantiereId) {
  return (await client.get(`/cantieri/${cantiereId}/archivio`)).data;
}

export async function uploadCantiereArchive(cantiereId, file) {
  const form = new FormData();
  form.append("file", file);
  return (
    await client.post(`/cantieri/${cantiereId}/archivio`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  ).data;
}

export async function downloadCantiereArchive(cantiereId, path) {
  return (
    await client.get(`/cantieri/${cantiereId}/archivio/download`, {
      params: { path },
      responseType: "blob",
    })
  ).data;
}
