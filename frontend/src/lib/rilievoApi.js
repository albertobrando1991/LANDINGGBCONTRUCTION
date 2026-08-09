import client from "./api";

export const loadRilievi = async () =>
  (await client.get("/campo/rilievi")).data;

export const loadRilievo = async (rilievoId) =>
  (await client.get(`/campo/rilievi/${rilievoId}`)).data;

export const createRilievo = async (body) =>
  (await client.post("/campo/rilievi", body)).data;

export const patchRilievo = async (rilievoId, body) =>
  (await client.patch(`/campo/rilievi/${rilievoId}`, body)).data;

export const saveRilievoAmbiente = async (
  rilievoId,
  ambienteClientUuid,
  body,
) =>
  (
    await client.put(
      `/campo/rilievi/${rilievoId}/ambienti/${ambienteClientUuid}`,
      body,
    )
  ).data;

export const archiveRilievoAmbiente = async (rilievoId, ambienteClientUuid) =>
  (
    await client.delete(
      `/campo/rilievi/${rilievoId}/ambienti/${ambienteClientUuid}`,
    )
  ).data;
