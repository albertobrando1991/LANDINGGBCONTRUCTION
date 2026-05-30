import { useState } from "react";
import { Maximize2, ArrowRight } from "lucide-react";
import Tilt3D from "@/components/Tilt3D";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { PROPOSAL_POSTERS } from "@/lib/assets";

const PACKAGES = [
  { key: "essenziale", name: "Soluzione Essenziale", tag: "Pratica. Concreta. Subito.", accent: "text-brand", ring: "hover:border-brand" },
  { key: "premium", name: "Soluzione Premium", tag: "Trasforma. Ridisegna. Personalizza.", accent: "text-ink", ring: "hover:border-fog", badge: "Più scelto" },
  { key: "luxury", name: "Soluzione Luxury", tag: "Tutto incluso. Chiavi in mano.", accent: "text-gold", ring: "hover:border-gold" },
];

export default function Packages() {
  const [selected, setSelected] = useState(null);

  const scrollToConfig = () =>
    document.getElementById("configuratore")?.scrollIntoView({ behavior: "smooth" });

  return (
    <section id="soluzioni" className="py-24 bg-surface px-6 relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-[0.03] pointer-events-none" />
      <div className="relative max-w-7xl mx-auto">
        <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3 text-center">Le tre soluzioni GB</p>
        <h2 className="font-display font-bold uppercase text-4xl md:text-6xl tracking-tight text-ink text-center mb-4">
          Tre proposte. <span className="text-brand">Una sola qualità.</span>
        </h2>
        <p className="font-body text-fog text-center max-w-2xl mx-auto mb-14">
          Dalla ristrutturazione essenziale al chiavi in mano di lusso. Tocca una soluzione per leggere tutti i dettagli del capitolato.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-7">
          {PACKAGES.map((p) => (
            <div key={p.key} className="flex flex-col">
              <Tilt3D max={9} radius="rounded-3xl">
                <button
                  data-testid={`package-${p.key}`}
                  onClick={() => setSelected(p)}
                  className={`group relative block w-full bg-bg border border-stroke ${p.ring} transition-colors text-left`}
                >
                  {p.badge && (
                    <span className="absolute top-4 right-4 z-10 gold-gradient text-bg font-display font-bold uppercase text-[10px] px-3 py-1 rounded-full">{p.badge}</span>
                  )}
                  <div className="aspect-square overflow-hidden">
                    <img src={PROPOSAL_POSTERS[p.key]} alt={p.name} className="w-full h-full object-cover" loading="lazy" />
                  </div>
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/35 transition-colors flex items-center justify-center">
                    <span className="opacity-0 group-hover:opacity-100 transition-opacity font-display uppercase text-[11px] tracking-wider text-white bg-brand px-4 py-2 rounded-full inline-flex items-center gap-2">
                      <Maximize2 className="w-3.5 h-3.5" /> Leggi i dettagli
                    </span>
                  </div>
                </button>
              </Tilt3D>

              <div className="mt-5 text-center">
                <h3 className={`font-display font-bold uppercase text-lg ${p.accent}`}>{p.name}</h3>
                <p className="font-display uppercase tracking-wider text-xs text-fog mt-1">{p.tag}</p>
                <button
                  onClick={scrollToConfig}
                  data-testid={`package-cta-${p.key}`}
                  className="mt-4 inline-flex items-center gap-2 font-display uppercase text-xs tracking-wider text-ink border border-stroke hover:border-brand hover:text-brand rounded-full px-5 py-2.5 transition-colors"
                >
                  Calcola la tua stima <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Lightbox poster pacchetto */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-xl bg-surface border-stroke p-2 max-h-[92vh] overflow-y-auto" data-testid="package-dialog">
          {selected && (
            <>
              <img src={PROPOSAL_POSTERS[selected.key]} alt={selected.name} className="w-full h-auto rounded-xl" />
              <button
                onClick={scrollToConfig}
                className="mt-3 mb-1 w-full bg-brand text-white rounded-full py-3 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform"
              >
                Avvia la stima gratuita <ArrowRight className="w-4 h-4" />
              </button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
