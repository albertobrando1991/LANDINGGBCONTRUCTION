export const SAL_STATI = {
  bozza: {
    label: "Bozza",
    tone: "border-slate-500/30 bg-slate-500/10 text-slate-300",
  },
  emesso: {
    label: "Emesso",
    tone: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  },
  approvato: {
    label: "Approvato",
    tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  },
};

export function azioneStatoSal(stato) {
  if (stato === "bozza") return { stato: "emesso", label: "Emetti SAL" };
  if (stato === "emesso")
    return { stato: "approvato", label: "Segna approvato" };
  return null;
}

export function periodoMensile(reference = new Date()) {
  const year = reference.getFullYear();
  const month = reference.getMonth();
  const pad = (value) => String(value).padStart(2, "0");
  const end = new Date(year, month + 1, 0).getDate();
  return {
    periodo_da: `${year}-${pad(month + 1)}-01`,
    periodo_a: `${year}-${pad(month + 1)}-${pad(end)}`,
  };
}

export function riepilogoSal(items = []) {
  return items.reduce(
    (acc, item) => ({
      totale: acc.totale + 1,
      maturato: acc.maturato + Number(item?.totale_periodo || 0),
      approvati: acc.approvati + (item?.stato === "approvato" ? 1 : 0),
      eccedenze: acc.eccedenze + (item?.contiene_eccedenze ? 1 : 0),
    }),
    { totale: 0, maturato: 0, approvati: 0, eccedenze: 0 },
  );
}
