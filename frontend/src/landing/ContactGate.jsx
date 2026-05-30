import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { motion } from "framer-motion";
import { Lock, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import client, { formatApiErrorDetail } from "@/lib/api";
import { CITTA_CAMPANIA } from "@/lib/assets";

const PHRASES = [
  "Analizzo le voci di cantierizzazione...",
  "Confronto con 200+ cantieri reali GB...",
  "Calcolo coefficienti predittivi...",
  "Genero le tre proposte...",
];

const schema = z.object({
  nome: z.string().min(2, "Inserisci nome e cognome"),
  email: z.string().email("Email non valida"),
  telefono: z.string().min(6, "Numero non valido").regex(/^[+0-9\s().-]+$/, "Numero non valido"),
  citta: z.string().min(1, "Seleziona la città"),
  privacy: z.literal(true, { errorMap: () => ({ message: "Devi accettare la privacy policy" }) }),
  newsletter: z.boolean().optional(),
});

function buildConfig(cfg) {
  const ambienti = [];
  if (cfg.cucina) ambienti.push("Cucina");
  if (cfg.bagni > 0) ambienti.push("Bagni");
  if (cfg.camere > 0) ambienti.push("Camere");
  if (cfg.soggiorno) ambienti.push("Soggiorno");
  if (cfg.ingresso) ambienti.push("Ingresso");
  if (cfg.balconi) ambienti.push("Balconi/Terrazzi");
  return {
    tipo_immobile: cfg.tipo_immobile, mq: cfg.mq, livello: cfg.livello,
    bagni: cfg.bagni, camere: cfg.camere, cucina: cfg.cucina, ambienti,
    stile: cfg.stile, tempistiche: cfg.tempistiche, has_files: cfg.has_files,
  };
}

export default function ContactGate({ config, onSubmit }) {
  const [phase, setPhase] = useState("calc");
  const [pct, setPct] = useState(0);
  const [phraseIdx, setPhraseIdx] = useState(0);

  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } =
    useForm({ resolver: zodResolver(schema), defaultValues: { newsletter: false } });

  useEffect(() => {
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / 3000, 1);
      setPct(Math.floor(p * 100));
      if (p < 1) requestAnimationFrame(tick);
      else setPhase("blurred");
    };
    requestAnimationFrame(tick);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setPhraseIdx((i) => (i + 1) % PHRASES.length), 800);
    return () => clearInterval(id);
  }, []);

  const submit = async (values) => {
    try {
      const { data } = await client.post("/leads", {
        nome: values.nome, email: values.email, telefono: values.telefono,
        citta: values.citta, privacy: values.privacy, newsletter: !!values.newsletter,
        config: buildConfig(config),
      });
      toast.success("Stima generata!");
      onSubmit(data, values);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    }
  };

  return (
    <section className="min-h-screen py-20 px-6 bg-bg flex items-center">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10 items-center w-full">
        {/* Left: calcolo / blurred */}
        <div className="relative">
          {phase === "calc" ? (
            <div className="bg-surface border border-stroke rounded-3xl p-10 text-center">
              <div className="font-display font-bold text-7xl text-brand mb-4">{pct}%</div>
              <div className="h-1 bg-stroke rounded-full overflow-hidden mb-6">
                <div className="h-full accent-gradient" style={{ width: `${pct}%` }} />
              </div>
              <motion.p key={phraseIdx} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="font-display uppercase tracking-wider text-sm text-fog">
                {PHRASES[phraseIdx]}
              </motion.p>
            </div>
          ) : (
            <div className="relative">
              <div className="grid gap-3 blur-md select-none pointer-events-none">
                {["Essenziale", "Premium", "Luxury"].map((p, i) => (
                  <div key={i} className="bg-surface border border-stroke rounded-2xl p-6">
                    <div className="font-display font-bold uppercase text-lg text-ink">{p}</div>
                    <div className="font-display font-bold text-4xl text-brand mt-2">€ ••.•••</div>
                  </div>
                ))}
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="bg-bg/80 backdrop-blur-sm border border-stroke rounded-2xl px-6 py-4 text-center">
                  <Lock className="w-6 h-6 text-brand mx-auto mb-2" />
                  <p className="font-display font-semibold uppercase text-sm text-ink">Lascia i tuoi contatti<br />per vedere il risultato</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: form */}
        <div>
          <h2 className="font-display font-bold uppercase text-3xl md:text-4xl text-ink leading-tight">La tua stima personalizzata è pronta.</h2>
          <div className="font-body text-sm text-fog mt-4 space-y-1">
            <p>Dove vuoi riceverla? Ti inviamo subito:</p>
            <p className="text-ink">✓ Stima dettagliata su Essenziale, Premium e Luxury</p>
            <p className="text-ink">✓ Anteprima visiva del progetto</p>
            <p className="text-ink">✓ Proposta di sopralluogo gratuito questa settimana</p>
          </div>

          <form onSubmit={handleSubmit(submit)} className="mt-6 space-y-4">
            <div>
              <input data-testid="gate-nome" {...register("nome")} placeholder="Nome e cognome *"
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand" />
              {errors.nome && <p className="text-brand text-xs mt-1">{errors.nome.message}</p>}
            </div>
            <div>
              <input data-testid="gate-email" {...register("email")} placeholder="Email *"
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand" />
              {errors.email && <p className="text-brand text-xs mt-1">{errors.email.message}</p>}
            </div>
            <div>
              <input data-testid="gate-telefono" {...register("telefono")} placeholder="Telefono / WhatsApp *"
                className="w-full bg-surface border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand" />
              {errors.telefono && <p className="text-brand text-xs mt-1">{errors.telefono.message}</p>}
            </div>
            <div>
              <Select onValueChange={(v) => setValue("citta", v, { shouldValidate: true })}>
                <SelectTrigger data-testid="gate-citta" className="w-full bg-surface border-stroke rounded-xl px-4 py-6 text-ink">
                  <SelectValue placeholder="Città dell'immobile *" />
                </SelectTrigger>
                <SelectContent>
                  {CITTA_CAMPANIA.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              {errors.citta && <p className="text-brand text-xs mt-1">{errors.citta.message}</p>}
            </div>

            <label className="flex items-start gap-3 cursor-pointer">
              <Checkbox data-testid="gate-privacy" checked={watch("privacy") || false}
                onCheckedChange={(v) => setValue("privacy", v === true, { shouldValidate: true })} className="mt-0.5" />
              <span className="font-body text-xs text-fog">Accetto la privacy policy *</span>
            </label>
            {errors.privacy && <p className="text-brand text-xs">{errors.privacy.message}</p>}

            <label className="flex items-start gap-3 cursor-pointer">
              <Checkbox data-testid="gate-newsletter" checked={watch("newsletter") || false}
                onCheckedChange={(v) => setValue("newsletter", v === true)} className="mt-0.5" />
              <span className="font-body text-xs text-fog">Voglio ricevere ispirazioni e novità</span>
            </label>

            <button data-testid="gate-submit" type="submit" disabled={isSubmitting}
              className="w-full bg-brand text-white rounded-full py-5 text-lg font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform disabled:opacity-60"
              style={{ boxShadow: "0 8px 32px rgba(198,40,40,0.35)" }}>
              {isSubmitting ? "Invio…" : "Ricevi la mia stima"} <ArrowRight className="w-5 h-5" />
            </button>
            <p className="font-body text-xs text-fog text-center">🔒 Dati protetti. Nessuno spam. Nessuna chiamata invadente.</p>
          </form>
        </div>
      </div>
    </section>
  );
}
