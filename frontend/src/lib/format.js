export function formatEuro(n) {
  if (n == null || isNaN(n)) return "—";
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatNumber(n) {
  if (n == null || isNaN(n)) return "—";
  return new Intl.NumberFormat("it-IT").format(n);
}

export function relativeDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return "adesso";
  if (diff < 3600) return `${Math.floor(diff / 60)} min fa`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h fa`;
  const days = Math.floor(diff / 86400);
  if (days === 1) return "ieri";
  if (days < 30) return `${days} giorni fa`;
  return d.toLocaleDateString("it-IT");
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("it-IT", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatArrivalDateTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("it-IT", {
    timeZone: "Europe/Rome",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
