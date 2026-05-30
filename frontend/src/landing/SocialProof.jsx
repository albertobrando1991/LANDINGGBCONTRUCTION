import { useEffect, useState, useCallback } from "react";
import useEmblaCarousel from "embla-carousel-react";
import { Star } from "lucide-react";
import { ASSETS } from "@/lib/assets";

const CARDS = [
  { type: "video", src: ASSETS.beforeAfter1, nome: "Attico Posillipo", citta: "Napoli" },
  { type: "video", src: ASSETS.beforeAfter2, nome: "Loft Vomero", citta: "Napoli" },
  { type: "texture", nome: "Villa Caserta", citta: "Caserta" },
  { type: "texture", nome: "Boutique Chiaia", citta: "Napoli" },
  { type: "texture", nome: "Appartamento Salerno", citta: "Salerno" },
  { type: "texture", nome: "Ufficio Centro Direzionale", citta: "Napoli" },
];

const TESTIMONIALS = [
  { nome: "Francesca R.", testo: "Hanno trasformato il nostro appartamento in qualcosa che non riconoscevamo più. Precisione e puntualità impeccabili.", stelle: 5 },
  { nome: "Luigi D.", testo: "Preventivo chiaro fin dall'inizio, nessuna sorpresa. Cantiere pulito e consegna nei tempi. Consigliatissimi.", stelle: 5 },
  { nome: "Maria E.", testo: "Professionisti veri. Ci hanno seguito su bonus e pratiche, sentendoci sempre tranquilli. Risultato superiore alle aspettative.", stelle: 5 },
];

const BADGES = ["Bonus Ristrutturazioni", "Ecobonus", "Sismabonus", "Partner Dr Soluzioni Finanziarie"];

export default function SocialProof() {
  const [emblaRef, emblaApi] = useEmblaCarousel({ loop: true, align: "start" });

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
                    <video src={c.src} autoPlay muted loop playsInline className="w-full h-full object-cover" />
                  ) : (
                    <img src={ASSETS.cemento} alt={c.nome} className="w-full h-full object-cover opacity-80 group-hover:scale-105 transition-transform duration-700" />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                  {c.type === "video" && (
                    <div className="absolute top-3 left-3 font-display font-semibold uppercase tracking-wider text-[10px] bg-brand text-white px-2 py-1 rounded">
                      Prima / Dopo
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

        {/* Testimonials */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-12">
          {TESTIMONIALS.map((t, i) => (
            <div key={i} className="bg-surface/50 border border-stroke rounded-2xl p-6">
              <div className="flex gap-1 mb-3">
                {Array.from({ length: t.stelle }).map((_, s) => (
                  <Star key={s} className="w-4 h-4 fill-gold text-gold" />
                ))}
              </div>
              <p className="font-body italic text-sm text-ink/80 mb-4">"{t.testo}"</p>
              <div className="font-display font-semibold uppercase text-xs text-ink">{t.nome}</div>
            </div>
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
    </section>
  );
}
