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
  const firstName = String(leadName || "").trim().split(/\s+/)[0] || "";
  const message = firstName
    ? `Ciao ${firstName}, sono GB Construction. Ti contatto per la richiesta di ristrutturazione.`
    : "Ciao, sono GB Construction. Ti contatto per la richiesta di ristrutturazione.";
  return `https://wa.me/${normalized}?text=${encodeURIComponent(message)}`;
}
