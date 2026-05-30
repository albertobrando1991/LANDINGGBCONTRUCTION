import { useState } from "react";
import { toast } from "sonner";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { ASSETS } from "@/lib/assets";
import client, { formatApiErrorDetail } from "@/lib/api";

const PROJECTS = [
  { nome: "Attico Posillipo", citta: "Napoli", tall: true },
  { nome: "Loft Vomero", citta: "Napoli", tall: false },
  { nome: "Villa Caserta", citta: "Caserta", tall: false },
  { nome: "Ufficio Direzionale", citta: "Napoli", tall: true },
  { nome: "Boutique Chiaia", citta: "Napoli", tall: false },
  { nome: "Casa Pozzuoli", citta: "Pozzuoli", tall: false },
];

const FAQ = [
  { q: "Quanto dura una ristrutturazione?", a: "Dipende dalla superficie e dal livello di intervento: una ristrutturazione completa va dai 60 ai 150 giorni. In sopralluogo definiamo un cronoprogramma preciso fase per fase." },
  { q: "Quali bonus fiscali posso usare?", a: "A seconda dell'intervento puoi accedere a Bonus Ristrutturazioni, Ecobonus e Sismabonus. Grazie al nostro partner Dr Soluzioni Finanziarie ti aiutiamo anche con la pratica e l'eventuale finanziamento." },
  { q: "Cosa include il sopralluogo gratuito?", a: "Un tecnico GB rileva misure e stato dell'immobile, verifica gli impianti esistenti e raccoglie le tue esigenze. Da lì produciamo un preventivo dettagliato e definitivo, senza alcun impegno." },
  { q: "Posso modificare il preventivo dopo il sopralluogo?", a: "Certo. La stima online è orientativa: dopo il sopralluogo affiniamo voci, quantità e finiture insieme a te, fino a un capitolato condiviso." },
  { q: "In quali zone operate?", a: "Operiamo a Napoli e in tutta la Campania: provincia di Napoli, Caserta, Salerno, Avellino e Benevento." },
];

export default function SecondChance() {
  const [form, setForm] = useState({ nome: "", telefono: "", messaggio: "" });
  const [sending, setSending] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.nome || !form.telefono) {
      toast.error("Inserisci nome e numero di telefono");
      return;
    }
    setSending(true);
    try {
      await client.post("/callback", form);
      toast.success("Richiesta inviata! Ti contattiamo entro 2 ore.");
      setForm({ nome: "", telefono: "", messaggio: "" });
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <section id="progetti" className="py-20 bg-surface px-6">
      <div className="max-w-7xl mx-auto">
        <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3">I nostri lavori</p>
        <h2 className="font-display font-bold uppercase text-4xl md:text-6xl tracking-tight text-ink mb-10">
          Progetti realizzati a Napoli e in Campania.
        </h2>

        {/* Masonry-like grid */}
        <div className="columns-2 md:columns-3 gap-4 [&>*]:mb-4">
          {PROJECTS.map((p, i) => (
            <div
              key={i}
              className={`relative break-inside-avoid rounded-2xl overflow-hidden border border-stroke group cursor-pointer ${p.tall ? "h-80" : "h-56"}`}
            >
              <img src={ASSETS.cemento} alt={p.nome} className="w-full h-full object-cover opacity-75 group-hover:opacity-100 group-hover:scale-105 transition-all duration-700" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 to-transparent" />
              <div className="absolute bottom-4 left-4">
                <div className="font-display font-semibold uppercase text-sm text-brand">{p.nome}</div>
                <div className="font-body text-xs text-ink/70">{p.citta}</div>
              </div>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 mt-20">
          <div>
            <h3 className="font-display font-bold uppercase text-2xl md:text-3xl text-ink mb-6">Domande frequenti</h3>
            <Accordion type="single" collapsible className="space-y-3">
              {FAQ.map((f, i) => (
                <AccordionItem key={i} value={`item-${i}`} className="bg-bg border border-stroke rounded-xl px-5">
                  <AccordionTrigger data-testid={`faq-${i}`} className="font-display font-semibold uppercase text-sm text-ink hover:no-underline text-left">
                    {f.q}
                  </AccordionTrigger>
                  <AccordionContent className="font-body text-sm text-fog">{f.a}</AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>

          {/* Recupero form */}
          <div className="bg-bg border border-stroke rounded-2xl p-8 h-fit">
            <h3 className="font-display font-bold uppercase text-2xl text-ink mb-2">Preferisci essere richiamato?</h3>
            <p className="font-body text-sm text-fog mb-6">Lasciaci nome e numero, ti contattiamo entro 2 ore.</p>
            <form onSubmit={submit} className="space-y-4">
              <input
                data-testid="callback-nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                placeholder="Nome *"
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
              />
              <input
                data-testid="callback-telefono"
                value={form.telefono}
                onChange={(e) => setForm({ ...form, telefono: e.target.value })}
                placeholder="Telefono *"
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
              />
              <textarea
                data-testid="callback-messaggio"
                value={form.messaggio}
                onChange={(e) => setForm({ ...form, messaggio: e.target.value })}
                placeholder="Messaggio (opzionale)"
                rows={3}
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand resize-none"
              />
              <button
                data-testid="callback-submit"
                disabled={sending}
                className="w-full bg-brand text-white rounded-full py-4 font-display font-semibold uppercase tracking-wider hover:scale-[1.02] transition-transform disabled:opacity-60"
              >
                {sending ? "Invio…" : "Richiamatemi"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </section>
  );
}
