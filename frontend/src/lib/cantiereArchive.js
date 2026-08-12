import client from "./api";
import { runOrQueueFile } from "./offlineStore";

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

export async function uploadOrQueueCantiereArchive({
  cantiereId,
  file,
  tenantSlug,
  userId,
  label = "Documento cantiere",
}) {
  return runOrQueueFile({
    tenantSlug,
    userId,
    url: `/cantieri/${cantiereId}/archivio`,
    file,
    label,
  });
}

export async function downloadCantiereArchive(cantiereId, path) {
  return (
    await client.get(`/cantieri/${cantiereId}/archivio/download`, {
      params: { path },
      responseType: "blob",
    })
  ).data;
}
