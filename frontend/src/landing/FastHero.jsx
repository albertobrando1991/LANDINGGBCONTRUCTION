import { ArrowRight } from "lucide-react";
import { ASSETS } from "@/lib/assets";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";

const PUBLIC_MEDIA_BASE = `${process.env.PUBLIC_URL || ""}/cantieri`;

export default function FastHero() {
  const scrollToConfig = () =>
    scheduleSmoothScrollToElement(document.getElementById("configuratore"));

  return (
    <section
      id="hero"
      className="relative min-h-[96svh] overflow-hidden bg-black px-5 pt-28 pb-14 text-center md:min-h-screen md:px-6 md:pt-32"
    >
      <picture>
        <source
          media="(min-width: 768px)"
          srcSet={`${PUBLIC_MEDIA_BASE}/frames_heron_uhd/frame_start.png`}
        />
        <img
          src={`${PUBLIC_MEDIA_BASE}/frames_heron_mobile/frame_0001.jpg`}
          alt=""
          aria-hidden="true"
          loading="eager"
          decoding="async"
          className="absolute inset-0 h-full w-full object-cover"
        />
      </picture>
      <div className="absolute inset-0 bg-black/62 md:bg-black/58" />
      <img
        src={ASSETS.cemento}
        alt=""
        aria-hidden="true"
        loading="lazy"
        decoding="async"
        className="absolute inset-0 h-full w-full object-cover opacity-[0.08] mix-blend-overlay"
      />
      <div className="absolute inset-0 blueprint-grid opacity-[0.035] mix-blend-screen pointer-events-none" />
      <div className="absolute bottom-0 left-0 right-0 h-40 bg-gradient-to-t from-bg to-transparent pointer-events-none" />

      <div className="relative z-10 mx-auto flex min-h-[calc(96svh-11rem)] max-w-5xl flex-col items-center justify-center md:min-h-[calc(100vh-13rem)]">
        <p className="font-display font-semibold uppercase tracking-[0.22em] text-[10px] text-brand md:text-xs md:tracking-[0.3em]">
          GB Construction - Napoli &amp; Campania
        </p>
        <h1 className="mt-5 font-display font-bold uppercase text-[clamp(2.05rem,11vw,3.45rem)] leading-[0.98] tracking-normal text-ink drop-shadow-[0_20px_52px_rgba(0,0,0,0.72)] md:mt-7 md:text-[clamp(4rem,7.6vw,7.8rem)] md:leading-[0.9]">
          Scopri quanto costa ristrutturare casa tua.
        </h1>
        <p
          className="mt-5 max-w-2xl font-body text-sm font-semibold leading-relaxed text-white/90 md:mt-7 md:text-lg"
          style={{ textShadow: "0 8px 28px rgba(0,0,0,0.92)" }}
        >
          Compila pochi dati sul tuo immobile. Ricevi una stima personalizzata
          su 3 livelli e una proposta di sopralluogo gratuito.
        </p>
        <button
          data-testid="hero-cta-stima"
          onClick={scrollToConfig}
          className="mt-8 inline-flex items-center gap-3 rounded-full bg-brand px-7 py-4 font-display text-sm font-semibold uppercase tracking-wider text-white transition-colors hover:bg-brand-dark active:scale-[0.98] md:mt-10 md:px-12 md:py-5 md:text-lg"
          style={{ boxShadow: "0 8px 32px rgba(198,40,40,0.35)" }}
        >
          Avvia stima gratuita
          <ArrowRight className="h-5 w-5" />
        </button>
        <div className="mt-6 font-display text-[10px] font-normal uppercase tracking-[0.18em] text-fog md:mt-8 md:text-xs md:tracking-[0.2em]">
          +200 cantieri - +15 anni in Campania - sopralluogo sempre gratuito
        </div>
      </div>
    </section>
  );
}
