import { useEffect, useState, useCallback } from "react";
import useEmblaCarousel from "embla-carousel-react";
import { Maximize2 } from "lucide-react";
import HlsVideo from "@/components/HlsVideo";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ASSETS, STYLE_VIDEOS, AMBIENT, TESTIMONIAL_IMAGES } from "@/lib/assets";

const CARDS = [
  { type: "video", src: ASSETS.beforeAfter1, nome: "Attico Posillipo", citta: "Napoli", label: "Prima / Dopo" },
  { type: "video", src: STYLE_VIDEOS["Moderno minimal"], nome: "Render Moderno", citta: "Napoli", label: "Render 3D" },
  { type: "video", src: STYLE_VIDEOS["Classico elegante"], nome: "Render Classico", citta: "Caserta", label: "Render 3D" },
  { type: "video", src: STYLE_VIDEOS["Industrial loft"], nome: "Render Industrial", citta: "Napoli", label: "Render 3D" },
  { type: "img", src: AMBIENT[0], nome: "Cantiere Vomero", citta: "Napoli" },
  { type: "img", src: AMBIENT[2], nome: "Ufficio Direzionale", citta: "Napoli" },
];

const BADGES = ["Bonus Ristrutturazioni", "Ecobonus", "Sismabonus", "Partner Dr Soluzioni Finanziarie"];

export default function SocialProof() {
  const [emblaRef, emblaApi] = useEmblaCarousel({ loop: true, align: "start" });
  const [selected, setSelected] = useState(null);

  const autoplay = useCallback(() => {
    if (emblaApi) emblaApi.scrollNext();
  }, [emblaApi]);

  useEffect(() => {
    const id = setInterval(autoplay, 4000);
    return () => clearInterval(id);
  }, [autoplay]);

  return (
    <section className="py-12 md:py-16 px-6 bg-bg">
      <div className="max-w-7xl mx-auto">
        <p className="font-display font-semibold uppercase tracking-[0.2em] text-sm text-fog mb-8 text-center">
          Già scelta da 200+ clienti in Campania
        </p>

        <div className="overflow-hidden" ref={emblaRef}>
          <div className="flex gap-4">
            {CARDS.map((c, i) => (
              <div key={i} className="flex-[0_0_70%] sm:flex-[0_0_45%] lg:flex-[0_0_30%] min-w-0">
                <div className="relative aspect-[4/5] rounded-2xl overflow-hidden border border-stroke group">
                  {c.type === "video" ? (
                    <HlsVideo src={c.src} className="w-full h-full object-cover" />
                  ) : (
                    <img src={c.src} alt={c.nome} className="w-full h-full object-cover opacity-90 group-hover:scale-105 transition-transform duration-700" />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                  {c.label && (
                    <div className="absolute top-3 left-3 font-display font-semibold uppercase tracking-wider text-[10px] bg-brand text-white px-2 py-1 rounded">
                      {c.label}
                    </div>
                  )}
                  <div className="absolute bottom-4 left-4">
                    <div className="font-display font-semibold uppercase text-sm text-brand">{c.nome}</div>
                    <div className="font-body text-xs text-ink/70">{c.citta}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Testimonials (card grafiche reali) — cliccabili per la lettura */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-12">
          {TESTIMONIAL_IMAGES.map((t, i) => (
            <button
              key={i}
              data-testid={`testimonial-${i}`}
              onClick={() => setSelected(t)}
              className="group relative rounded-2xl overflow-hidden border border-stroke bg-surface/50 hover:border-brand transition-colors text-left"
            >
              <img src={t.src} alt={`Recensione ${t.nome}`} className="w-full h-auto object-cover" loading="lazy" />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/45 transition-colors flex items-center justify-center">
                <span className="opacity-0 group-hover:opacity-100 transition-opacity font-display uppercase text-[11px] tracking-wider text-white bg-brand px-4 py-2 rounded-full inline-flex items-center gap-2">
                  <Maximize2 className="w-3.5 h-3.5" /> Leggi la recensione
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Trust badges */}
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-12">
          {BADGES.map((b, i) => (
            <span key={i} className="font-display font-normal uppercase tracking-wider text-xs text-fog">
              {b}{i < BADGES.length - 1 && <span className="ml-6 text-stroke">·</span>}
            </span>
          ))}
        </div>
      </div>

      {/* Lightbox recensione */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-2xl bg-surface border-stroke p-2" data-testid="testimonial-dialog">
          <DialogTitle className="sr-only">Recensione cliente GB Construction</DialogTitle>
          {selected && (
            <img src={selected.src} alt={`Recensione ${selected.nome}`} className="w-full h-auto rounded-xl" />
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
