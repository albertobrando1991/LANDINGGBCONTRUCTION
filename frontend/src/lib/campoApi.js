import client from "./api";

export async function loadCampoCantieri() {
  return (await client.get("/campo/cantieri")).data;
}

export async function loadCampoMisure(cantiereId) {
  return (
    await client.get(`/cantieri/${cantiereId}/libretto-misure`, {
      params: { limit: 30 },
    })
  ).data;
}

export async function sendCampoMeasurement(cantiereId, body) {
  return (await client.post(`/cantieri/${cantiereId}/libretto-misure`, body))
    .data;
}

function optionalNumber(value) {
  if (value === "" || value == null) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function buildCampoMeasurementPayload(values, clientUuid) {
  const absoluteQuantity = Math.abs(Number(values.qta));
  const payload = {
    client_uuid: clientUuid,
    data_misura: values.data_misura,
    qta: values.mode === "rettifica" ? -absoluteQuantity : absoluteQuantity,
    parti: Math.max(1, Number.parseInt(values.parti || "1", 10) || 1),
    foto_paths: [],
  };
  const description = String(values.descrizione || "").trim();
  if (description) payload.descrizione = description;
  if (values.computo_voce_id) {
    payload.computo_voce_id = values.computo_voce_id;
  }
  for (const field of ["lunghezza", "larghezza", "altezza"]) {
    const parsed = optionalNumber(values[field]);
    if (parsed !== undefined) payload[field] = parsed;
  }
  return payload;
}
