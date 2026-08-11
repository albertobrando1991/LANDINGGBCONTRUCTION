export function filterPersonale(list = [], { tipo = "", attivo = null } = {}) {
  return list.filter((item) => {
    if (tipo && item.tipo !== tipo) return false;
    if (attivo !== null && Boolean(item.attivo) !== Boolean(attivo))
      return false;
    return true;
  });
}

export function groupAssegnazioniPerCantiere(assegnazioni = []) {
  const grouped = new Map();
  for (const assegnazione of assegnazioni) {
    const cantiereId = String(assegnazione.cantiere_id || "");
    if (!cantiereId) continue;
    const current = grouped.get(cantiereId) || [];
    current.push(assegnazione);
    grouped.set(cantiereId, current);
  }
  return grouped;
}

function localDay(value) {
  const day = value instanceof Date ? new Date(value) : new Date(value);
  if (Number.isNaN(day.getTime())) return null;
  day.setHours(0, 0, 0, 0);
  return day;
}

export function isAssegnazioneAttiva(assegnazione, today = new Date()) {
  if (!assegnazione || assegnazione.stato === "concluso") return false;
  const reference = localDay(today);
  if (!reference) return false;
  if (assegnazione.data_da) {
    const from = localDay(`${assegnazione.data_da}T00:00:00`);
    if (from && from > reference) return false;
  }
  if (!assegnazione.data_a) return true;
  const until = localDay(`${assegnazione.data_a}T00:00:00`);
  return Boolean(until && until >= reference);
}

export function formatRuoloLabel(tipo, ruolo) {
  const custom = String(ruolo || "").trim();
  if (custom) return custom;
  return tipo === "subappaltatore"
    ? "Squadra subappaltata"
    : "Personale interno";
}

export function assegnazioneMatchesCantiere(assegnazione, cantiereId) {
  const target = String(cantiereId || "");
  return [assegnazione?.cantiere_id, assegnazione?.cantiere_legacy_id]
    .filter(Boolean)
    .some((value) => String(value) === target);
}
