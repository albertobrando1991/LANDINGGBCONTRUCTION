import { LEAD_AUTO_REFRESH_MS, refreshLeadViews } from "./leadSync";

test("riallinea inbox, pipeline, contatori e dettaglio del lead", async () => {
  const queryClient = {
    invalidateQueries: jest.fn().mockResolvedValue(undefined),
    setQueryData: jest.fn(),
  };
  const lead = { id: "lead-1", status: "preventivo_preparazione" };

  await refreshLeadViews(queryClient, {
    leadId: lead.id,
    updatedLead: lead,
    includeAppointments: true,
  });

  expect(queryClient.setQueryData).toHaveBeenCalledWith(["lead", "lead-1"], lead);
  expect(queryClient.invalidateQueries.mock.calls.map(([arg]) => arg.queryKey)).toEqual(
    expect.arrayContaining([
      ["leads"],
      ["pipeline"],
      ["lead-counts"],
      ["today"],
      ["sopralluoghi"],
    ]),
  );
  expect(LEAD_AUTO_REFRESH_MS).toBe(10000);
});

test("forza il refetch del dettaglio quando non riceve il lead aggiornato", async () => {
  const queryClient = {
    invalidateQueries: jest.fn().mockResolvedValue(undefined),
    setQueryData: jest.fn(),
  };

  await refreshLeadViews(queryClient, { leadId: "lead-2" });

  expect(queryClient.setQueryData).not.toHaveBeenCalled();
  expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
    queryKey: ["lead", "lead-2"],
  });
});
