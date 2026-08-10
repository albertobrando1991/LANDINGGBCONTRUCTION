function clean(value) {
  return String(value || "").trim();
}

export function normalizeRilievoLeads(leads) {
  if (!Array.isArray(leads)) return [];
  return leads
    .filter((lead) => clean(lead?.id) && clean(lead?.nome))
    .sort((left, right) =>
      clean(left.nome).localeCompare(clean(right.nome), "it", {
        sensitivity: "base",
      }),
    );
}

export function rilievoLeadLabel(lead) {
  const details = [
    clean(lead?.citta),
    clean(lead?.email || lead?.telefono),
  ].filter(Boolean);
  return [clean(lead?.nome), ...details].filter(Boolean).join(" · ");
}

export function applyRilievoLeadSelection(current, leadId, leads) {
  const normalizedId = clean(leadId);
  if (!normalizedId) {
    return {
      ...current,
      lead_id: "",
      sopralluogo_legacy_id: "",
    };
  }

  const lead = (Array.isArray(leads) ? leads : []).find(
    (item) => clean(item?.id) === normalizedId,
  );
  if (!lead) return current;

  return {
    ...current,
    lead_id: normalizedId,
    sopralluogo_legacy_id: "",
    cliente: clean(lead.nome) || current.cliente,
    indirizzo: clean(lead.indirizzo) || clean(lead.citta) || current.indirizzo,
  };
}
