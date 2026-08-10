import { normalizeLeadList } from "./leadData";

describe("normalizeLeadList", () => {
  test("mantiene gli array nativi", () => {
    const timeline = [{ id: "ev-1", testo: "Lead ricevuto" }];
    expect(normalizeLeadList(timeline)).toBe(timeline);
  });

  test("recupera gli array JSON provenienti dal bridge legacy", () => {
    expect(
      normalizeLeadList('[{"id":"ev-1","testo":"Preventivo creato"}]'),
    ).toEqual([{ id: "ev-1", testo: "Preventivo creato" }]);
  });

  test("usa una lista vuota per valori non validi", () => {
    expect(normalizeLeadList("non-json")).toEqual([]);
    expect(normalizeLeadList({ id: "ev-1" })).toEqual([]);
  });
});
