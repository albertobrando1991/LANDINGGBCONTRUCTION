import {
  buildCantiereReportMessage,
  buildCantiereWhatsappUrl,
} from "./whatsapp";

const CANTIERE = {
  cliente: "Mario Rossi",
  telefono: "+39 333 123 4567",
  indirizzo: "Via Roma 10, Napoli",
  avanzamento: 45,
  fasi: [
    { nome: "Demolizioni", stato: "completata" },
    { nome: "Impianti & luce", stato: "in_corso" },
  ],
  milestone: "Consegna materiali",
  milestone_data: "2026-08-20",
};

test("non genera il link WhatsApp senza telefono", () => {
  expect(buildCantiereWhatsappUrl({ ...CANTIERE, telefono: "" })).toBe("");
});

test("costruisce un report coerente anche senza fasi completate", () => {
  const message = buildCantiereReportMessage({
    ...CANTIERE,
    fasi: [{ nome: "Impianti", stato: "da_iniziare" }],
  });
  expect(message).toContain("Fasi completate: nessuna");
  expect(message).toContain("In corso: nessuna fase");
  expect(message).toContain("Avanzamento: 45%");
});

test("codifica caratteri speciali e newline nel link", () => {
  const url = buildCantiereWhatsappUrl(CANTIERE);
  expect(url).toContain("https://wa.me/393331234567?text=");
  expect(url).toContain("%0A");
  expect(decodeURIComponent(url.split("?text=")[1])).toContain(
    "Impianti & luce",
  );
});

test.each(["+39 333 123 4567", "0039 333 123 4567", "333 123 4567"])(
  "normalizza il numero italiano %s nello stesso link",
  (telefono) => {
    expect(buildCantiereWhatsappUrl({ ...CANTIERE, telefono })).toBe(
      buildCantiereWhatsappUrl(CANTIERE),
    );
  },
);
