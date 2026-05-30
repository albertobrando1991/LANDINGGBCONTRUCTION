import { motion } from "framer-motion";
import { Check, X, Calendar, MessageCircle, ShieldCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import Tilt3D from "@/components/Tilt3D";
import { formatEuro } from "@/lib/format";
import { WHATSAPP, PROPOSAL_POSTERS } from "@/lib/assets";

const PACKAGES = [
  {
    key: "essenziale", titolo: "Soluzione Essenziale", tagline: "Pratica. Concreta. Subito.",
    border: "border-brand", color: "text-brand",
    incl: ["Demolizioni e rimozioni", "Impianti a norma DM 37/08", "Pavimenti e rivestimenti", "Tinteggiatura completa"],
    escl: ["Forniture e arredi", "Redistribuzione spazi"], fornitureTag: "Forniture escluse",
  },
  {
    key: "premium", titolo: "Soluzione Premium", tagline: "Trasforma. Ridisegna. Personalizza.",
    border: "border-fog", color: "text-ink", badge: "Più scelto",
    incl: ["Tutto l'Essenziale", "Redistribuzione interna", "Controsoffitti e cartongesso", "Finiture di qualità", "Climatizzazione predisposta"],
    escl: ["Forniture e arredi"], fornitureTag: "Forniture escluse",
  },
  {
    key: "luxury", titolo: "Soluzione Luxury", tagline: "Tutto incluso. Chiavi in mano.",
    border: "border-gold", color: "text-gold", luxury: true,
    incl: ["Tutto il Premium", "Sanitari e rubinetterie premium", "Porte e pavimenti inclusi", "Illuminazione di design", "Domotica base"],
    escl: [], fornitureTag: "Forniture incluse",
  },
];

export default function Output({ estimate }) {
  const pac = estimate?.pacchetti || {};

  return (
    <section className="py-20 px-6 bg-bg">
      <div className="max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8 }} className="text-center mb-12">
          <div className="w-16 h-16 rounded-full bg-success/20 border-2 border-success flex items-center justify-center mx-auto mb-4" style={{ boxShadow: "0 0 30px hsla(142,70%,45%,0.4)" }}>
            <Check className="w-8 h-8 text-success" />
          </div>
          <h2 className="font-display font-bold uppercase text-4xl md:text-5xl text-ink">Ecco la tua stima personalizzata.</h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PACKAGES.map((p, idx) => {
            const data = pac[p.key] || {};
            return (
              <motion.div key={p.key} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: idx * 0.1 }}
                data-testid={`output-card-${p.key}`}
                className={`relative bg-surface border-2 ${p.border} rounded-3xl p-7 ${p.luxury ? "gold-gradient/5" : ""}`}>
                {p.badge && <span className="absolute -top-3 left-1/2 -translate-x-1/2 gold-gradient text-bg font-display font-bold uppercase text-[10px] px-4 py-1 rounded-full">{p.badge}</span>}
                <Tilt3D className="mb-5" max={9} radius="rounded-2xl">
                  <div className="border border-stroke rounded-2xl overflow-hidden">
                    <img src={PROPOSAL_POSTERS[p.key]} alt={p.titolo} className="block w-full h-auto" loading="lazy" />
                  </div>
                </Tilt3D>
                <h3 className={`font-display font-bold uppercase text-xl ${p.color}`}>{p.titolo}</h3>
                <p className="font-display uppercase text-xs text-fog mt-1 mb-5">{p.tagline}</p>

                <div className="mb-1 font-body text-xs text-fog uppercase tracking-wider">Da</div>
                <div className={`font-display font-bold text-4xl ${p.luxury ? "text-gold" : "text-brand"}`}>
                  {formatEuro(data.range_basso)}
                </div>
                <div className="font-body text-sm text-fog">a {formatEuro(data.range_alto)}</div>
                <div className="font-display uppercase text-xs text-fog mt-2">≈ {formatEuro(data.costo_mq)}/mq · {data.tempistiche}</div>

                <div className="h-px bg-stroke my-5" />

                <ul className="space-y-2 mb-3">
                  {p.incl.map((f) => (
                    <li key={f} className="flex items-start gap-2 font-body text-sm text-ink/90">
                      <Check className="w-4 h-4 text-success mt-0.5 shrink-0" /> {f}
                    </li>
                  ))}
                  {p.escl.map((f) => (
                    <li key={f} className="flex items-start gap-2 font-body text-sm text-fog">
                      <X className="w-4 h-4 text-fog mt-0.5 shrink-0" /> {f}
                    </li>
                  ))}
                </ul>

                <span className={`font-display uppercase text-xs ${p.luxury ? "text-gold" : "text-fog"}`}>{p.fornitureTag}</span>
                <button className={`mt-5 w-full rounded-full py-3 font-display font-semibold uppercase text-sm tracking-wider transition-transform hover:scale-[1.02] ${p.luxury ? "gold-gradient text-bg" : "bg-brand text-white"}`}>
                  Approfondisci →
                </button>
              </motion.div>
            );
          })}
        </div>

        <p className="font-body text-xs text-fog max-w-3xl mx-auto text-center mt-8">
          Valori orientativi calcolati sui dati storici di 200+ cantieri GB Construction (range ±15/20%).
          La Soluzione Luxury include il pacchetto forniture standard da capitolato. Variazioni su richiesta valutate in sopralluogo gratuito.
        </p>

        {/* Render preview */}
        <div className="bg-surface border border-stroke rounded-2xl p-6 mt-12">
          <p className="font-display font-semibold uppercase text-sm text-ink mb-4">📷 Stiamo generando un'anteprima visiva del tuo progetto…</p>
          <div className="grid grid-cols-3 gap-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-video rounded-xl bg-surface-2" />)}
          </div>
          <p className="font-body text-xs text-fog mt-4">L'anteprima sarà disponibile via email entro 5 minuti.</p>
        </div>

        {/* Dual CTA */}
        <div className="bg-gradient-to-r from-brand/15 to-transparent border border-brand/30 rounded-3xl p-8 mt-10 text-center">
          <h3 className="font-display font-bold uppercase text-2xl md:text-3xl text-ink mb-6">Il prossimo passo è il sopralluogo gratuito.</h3>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button data-testid="output-prenota" className="bg-brand text-white rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-105 transition-transform">
              <Calendar className="w-5 h-5" /> Prenota sopralluogo gratuito
            </button>
            <a data-testid="output-whatsapp" href={WHATSAPP} target="_blank" rel="noreferrer" className="bg-surface border border-stroke text-ink rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:border-success transition-colors">
              <MessageCircle className="w-5 h-5 text-success" /> Parla con un tecnico su WhatsApp
            </a>
          </div>
          <p className="font-display uppercase text-xs text-fog mt-5 inline-flex items-center gap-2 justify-center">
            <ShieldCheck className="w-4 h-4 text-success" /> Sopralluogo sempre gratuito e senza impegno
          </p>
        </div>
      </div>
    </section>
  );
}
