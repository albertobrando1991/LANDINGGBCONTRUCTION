export const VARIANTE_CLASSI = [
  "tutte",
  "modificata",
  "nuova",
  "soppressa",
  "invariata",
];

export function filterRigheVariante(righe = [], filtro = "tutte") {
  return filtro === "tutte"
    ? righe
    : righe.filter((riga) => riga.classificazione === filtro);
}

export function formatDelta(value, options = {}) {
  const number = Number(value || 0);
  const formatted = Math.abs(number).toLocaleString("it-IT", {
    minimumFractionDigits: options.decimals ?? 2,
    maximumFractionDigits: options.decimals ?? 2,
  });
  return `${number > 0 ? "+" : number < 0 ? "−" : ""}${formatted}`;
}
