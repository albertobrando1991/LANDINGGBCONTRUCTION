const DECIMAL_ERROR = "Usa un numero, es. 2,70";
const UNIT_SUFFIX_RE = /(mq|m²|cm|mm|m)$/i;

export function parseDecimale(input) {
  if (input == null) return { ok: true, value: null, error: null };
  if (typeof input === "number") {
    return Number.isFinite(input) && input >= 0
      ? { ok: true, value: input, error: null }
      : { ok: false, value: null, error: DECIMAL_ERROR };
  }

  const compact = String(input).trim().replace(/\s+/g, "");
  if (!compact) return { ok: true, value: null, error: null };
  const withoutUnit = compact.replace(UNIT_SUFFIX_RE, "");
  const separators = withoutUnit.match(/[.,]/g) || [];
  if (
    !withoutUnit ||
    separators.length > 1 ||
    !/^\d+(?:[.,]\d+)?$/.test(withoutUnit)
  ) {
    return { ok: false, value: null, error: DECIMAL_ERROR };
  }

  const value = Number(withoutUnit.replace(",", "."));
  return Number.isFinite(value) && value >= 0
    ? { ok: true, value, error: null }
    : { ok: false, value: null, error: DECIMAL_ERROR };
}

export function formatDecimale(value, decimals = 3) {
  if (value == null || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return number.toLocaleString("it-IT", {
    minimumFractionDigits: 0,
    maximumFractionDigits: Math.max(0, decimals),
    useGrouping: false,
  });
}

export { DECIMAL_ERROR };
