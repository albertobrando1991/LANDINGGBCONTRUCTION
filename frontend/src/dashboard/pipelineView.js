export const PIPELINE_PAGE_SIZE = 6;

export function normalizePipelineSearch(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLocaleLowerCase("it");
}

export function filterLeadsByName(leads, query) {
  const normalizedQuery = normalizePipelineSearch(query);
  if (!normalizedQuery) return leads || [];

  return (leads || []).filter((lead) =>
    normalizePipelineSearch(lead?.nome).includes(normalizedQuery),
  );
}

export function paginatePipelineLeads(
  leads,
  requestedPage,
  pageSize = PIPELINE_PAGE_SIZE,
) {
  const safeLeads = leads || [];
  const safePageSize = Math.max(1, Number(pageSize) || PIPELINE_PAGE_SIZE);
  const total = safeLeads.length;
  const totalPages = Math.max(1, Math.ceil(total / safePageSize));
  const page = Math.min(totalPages, Math.max(1, Number(requestedPage) || 1));
  const offset = (page - 1) * safePageSize;
  const items = safeLeads.slice(offset, offset + safePageSize);

  return {
    items,
    page,
    total,
    totalPages,
    start: total === 0 ? 0 : offset + 1,
    end: Math.min(offset + safePageSize, total),
  };
}
