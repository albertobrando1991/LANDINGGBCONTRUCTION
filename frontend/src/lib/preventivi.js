export const PREVENTIVO_STATI = {
  bozza: { label: "Bozza", tone: "bg-slate-500/15 text-slate-300" },
  inviato: { label: "Inviato", tone: "bg-blue-500/15 text-blue-300" },
  accettato: {
    label: "Accettato",
    tone: "bg-emerald-500/15 text-emerald-300",
  },
  rifiutato: { label: "Rifiutato", tone: "bg-red-500/15 text-red-300" },
  scaduto: { label: "Scaduto", tone: "bg-amber-500/15 text-amber-300" },
};

export const AZIONI_PREVENTIVO = [
  { stato: "accettato", label: "Segna accettato", tone: "success" },
  { stato: "rifiutato", label: "Segna rifiutato", tone: "danger" },
  { stato: "scaduto", label: "Segna scaduto", tone: "neutral" },
];

export function azioniPerPreventivo(stato) {
  return stato === "inviato" ? AZIONI_PREVENTIVO : [];
}

export function preventivoGestibile(preventivo) {
  return preventivo?.source === "edilos";
}

export function etichettaEventoPreventivo(evento) {
  if (evento?.tipo === "email_inviata") return "Email inviata";
  if (evento?.tipo === "stato") return "Stato aggiornato";
  if (evento?.tipo === "creato") return "Preventivo creato";
  return "Aggiornamento";
}
