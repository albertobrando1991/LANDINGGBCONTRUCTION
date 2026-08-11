export const ECONOMICS_CATEGORIES = [
  "materiali",
  "manodopera",
  "subappalto",
  "noleggio",
  "trasporto",
  "utenze",
  "professionisti",
  "altro",
];

export const FIXED_COST_CATEGORIES = [
  "affitto",
  "assicurazioni",
  "leasing",
  "software",
  "stipendi_amministrativi",
  "utenze_sede",
  "consulenze",
  "altro",
];

export function filterEconomics(data, cantiereId) {
  if (!data || !cantiereId) return data;
  const belongs = (row) => row.cantiere_id === cantiereId;
  return {
    ...data,
    cantieri: (data.cantieri || []).filter(belongs),
    spese: (data.spese || []).filter(belongs),
    incassi: (data.incassi || []).filter(belongs),
    scadenze: (data.scadenze || []).filter(belongs),
  };
}

export function summarizeMargins(rows = []) {
  const summary = rows.reduce(
    (acc, row) => ({
      ricavi_maturati: acc.ricavi_maturati + Number(row.ricavi_maturati || 0),
      costi_registrati:
        acc.costi_registrati + Number(row.costi_registrati || 0),
      incassato: acc.incassato + Number(row.incassato || 0),
      da_incassare: acc.da_incassare + Number(row.da_incassare || 0),
      scadenze_aperte: acc.scadenze_aperte + Number(row.scadenze_aperte || 0),
      scadenze_scadute:
        acc.scadenze_scadute + Number(row.scadenze_scadute || 0),
    }),
    {
      ricavi_maturati: 0,
      costi_registrati: 0,
      incassato: 0,
      da_incassare: 0,
      scadenze_aperte: 0,
      scadenze_scadute: 0,
    },
  );
  summary.margine = summary.ricavi_maturati - summary.costi_registrati;
  summary.margine_percentuale = summary.ricavi_maturati
    ? (summary.margine / summary.ricavi_maturati) * 100
    : null;
  return summary;
}

export function isOverdue(item, today = new Date()) {
  if (!item || item.stato !== "aperta") return false;
  const day = new Date(today);
  day.setHours(0, 0, 0, 0);
  return new Date(`${item.data_scadenza}T00:00:00`) < day;
}

export function summarizeFixedMonthlyCosts(rows = [], today = new Date()) {
  const reference = new Date(today);
  reference.setHours(0, 0, 0, 0);
  return rows.reduce((total, item) => {
    if (!item?.attivo) return total;
    const starts = item.data_inizio
      ? new Date(`${item.data_inizio}T00:00:00`)
      : null;
    const ends = item.data_fine ? new Date(`${item.data_fine}T00:00:00`) : null;
    if (starts && starts > reference) return total;
    if (ends && ends < reference) return total;
    return total + Number(item.importo_mensile || 0);
  }, 0);
}
