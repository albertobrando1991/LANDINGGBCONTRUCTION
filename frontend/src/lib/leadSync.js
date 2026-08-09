export const LEAD_AUTO_REFRESH_MS = 10000;

const SHARED_LEAD_QUERY_KEYS = [
  ["leads"],
  ["pipeline"],
  ["lead-counts"],
  ["today"],
];

export async function refreshLeadViews(queryClient, options = {}) {
  const { leadId, includeAppointments = false, updatedLead } = options;

  if (leadId && updatedLead) {
    queryClient.setQueryData(["lead", String(leadId)], updatedLead);
  }

  const keys = [...SHARED_LEAD_QUERY_KEYS];
  if (leadId && !updatedLead) keys.push(["lead", String(leadId)]);
  if (includeAppointments) keys.push(["sopralluoghi"]);

  await Promise.all(
    keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  );
}
