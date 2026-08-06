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
