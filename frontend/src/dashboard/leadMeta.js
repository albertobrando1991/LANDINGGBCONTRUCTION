// Metadati condivisi dashboard

export const STATI = {
  nuovo: { label: "Nuovo", color: "text-sky-400", bg: "bg-sky-500/15", dot: "bg-sky-400" },
  qualificato: { label: "Qualificato", color: "text-cyan-400", bg: "bg-cyan-500/15", dot: "bg-cyan-400" },
  sopralluogo_fissato: { label: "Sopralluogo fissato", color: "text-violet-400", bg: "bg-violet-500/15", dot: "bg-violet-400" },
  sopralluogo_fatto: { label: "Sopralluogo fatto", color: "text-indigo-400", bg: "bg-indigo-500/15", dot: "bg-indigo-400" },
  preventivo_preparazione: { label: "Preventivo prep.", color: "text-amber-400", bg: "bg-amber-500/15", dot: "bg-amber-400" },
  preventivo_inviato: { label: "Preventivo inviato", color: "text-yellow-400", bg: "bg-yellow-500/15", dot: "bg-yellow-400" },
  follow_up: { label: "Follow-up", color: "text-orange-400", bg: "bg-orange-500/15", dot: "bg-orange-400" },
  in_trattativa: { label: "In trattativa", color: "text-pink-400", bg: "bg-pink-500/15", dot: "bg-pink-400" },
  chiuso_vinto: { label: "Chiuso vinto", color: "text-emerald-400", bg: "bg-emerald-500/15", dot: "bg-emerald-400" },
  chiuso_perso: { label: "Chiuso perso", color: "text-red-400", bg: "bg-red-500/15", dot: "bg-red-400" },
};

export const PIPELINE_ORDER = [
  "nuovo", "qualificato", "sopralluogo_fissato", "sopralluogo_fatto",
  "preventivo_preparazione", "preventivo_inviato", "follow_up",
  "in_trattativa", "chiuso_vinto", "chiuso_perso",
];

export function priority(score) {
  if (score >= 75) return { label: "Alta", dot: "bg-red-500", text: "text-red-400" };
  if (score >= 50) return { label: "Media", dot: "bg-yellow-500", text: "text-yellow-400" };
  return { label: "Bassa", dot: "bg-emerald-500", text: "text-emerald-400" };
}

export function initials(name) {
  if (!name) return "?";
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

export function ageColor(days) {
  if (days < 5) return "border-l-emerald-500";
  if (days <= 10) return "border-l-yellow-500";
  return "border-l-red-500";
}
