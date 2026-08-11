export function normalizeWhatsappPhone(phone) {
  let digits = String(phone || "").replace(/\D/g, "");
  if (!digits) return "";
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith("39")) return digits;
  return `39${digits}`;
}

export function buildWhatsappUrl(phone, leadName) {
  const normalized = normalizeWhatsappPhone(phone);
  if (!normalized) return "";
  const firstName =
    String(leadName || "")
      .trim()
      .split(/\s+/)[0] || "";
  const message = firstName
    ? `Ciao ${firstName}, sono GB Construction. Ti contatto per la richiesta di ristrutturazione.`
    : "Ciao, sono GB Construction. Ti contatto per la richiesta di ristrutturazione.";
  return `https://wa.me/${normalized}?text=${encodeURIComponent(message)}`;
}

function reportDate(value) {
  if (!value) return "";
  const source = String(value).length === 10 ? `${value}T00:00:00` : value;
  const date = new Date(source);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export function buildCantiereReportMessage(cantiere = {}) {
  const cliente = String(cantiere.cliente || "").trim() || "cliente";
  const fasi = Array.isArray(cantiere.fasi) ? cantiere.fasi : [];
  const completate = fasi
    .filter((fase) => fase?.stato === "completata")
    .map((fase) => fase.nome)
    .filter(Boolean);
  const inCorso = fasi
    .filter((fase) => fase?.stato === "in_corso")
    .map((fase) => fase.nome)
    .filter(Boolean);
  const milestone = String(cantiere.milestone || "").trim();
  const milestoneData = reportDate(cantiere.milestone_data);

  return [
    `Ciao ${cliente},`,
    "ecco l'aggiornamento del tuo cantiere GB Construction.",
    cantiere.indirizzo
      ? `Cantiere: ${String(cantiere.indirizzo).trim()}`
      : null,
    `Avanzamento: ${Math.max(0, Math.min(100, Math.round(Number(cantiere.avanzamento) || 0)))}%`,
    `Fasi completate: ${completate.length ? completate.join(", ") : "nessuna"}`,
    `In corso: ${inCorso.length ? inCorso.join(", ") : "nessuna fase"}`,
    milestone
      ? `Prossima milestone: ${milestone}${milestoneData ? ` · ${milestoneData}` : ""}`
      : null,
    "Per qualsiasi necessità puoi rispondere direttamente a questo messaggio.",
  ]
    .filter(Boolean)
    .join("\n");
}

export function buildCantiereWhatsappUrl(cantiere = {}) {
  const normalized = normalizeWhatsappPhone(
    cantiere.telefono || cantiere.cliente_telefono,
  );
  if (!normalized) return "";
  return `https://wa.me/${normalized}?text=${encodeURIComponent(
    buildCantiereReportMessage(cantiere),
  )}`;
}
