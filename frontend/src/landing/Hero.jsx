import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { gsap } from "gsap";
import { ArrowRight } from "lucide-react";
import { ASSETS } from "@/lib/assets";
import HlsVideo from "@/components/HlsVideo";

const ROLES = ["appartamento", "ufficio", "condominio", "negozio", "capannone"];

export default function Hero() {
  const [roleIdx, setRoleIdx] = useState(0);
  const eyebrowRef = useRef(null);
  const headlineRef = useRef(null);
  const descRef = useRef(null);
  const ctaRef = useRef(null);

  useEffect(() => {
    const id = setInterval(() => setRoleIdx((i) => (i + 1) % ROLES.length), 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.timeline({ defaults: { ease: "power3.out" } })
        .fromTo(eyebrowRef.current, { opacity: 0, filter: "blur(10px)", y: 20 }, { opacity: 1, filter: "blur(0px)", y: 0, duration: 0.6 }, 0)
        .fromTo(headlineRef.current, { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 1.2 }, 0.2)
        .fromTo(descRef.current, { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.8 }, 0.6)
        .fromTo(ctaRef.current, { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.6 }, 0.9);
    });
    return () => ctx.revert();
  }, []);

  const scrollToConfig = () =>
    document.getElementById("configuratore")?.scrollIntoView({ behavior: "smooth" });

  return (
    <section id="hero" className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background video HLS + fallback nativo */}
      <HlsVideo
        className="absolute inset-0 w-full h-full object-cover scale-105"
        src={ASSETS.heroVideo}
      />
      {/* Overlay cinematografico */}
      <div className="absolute inset-0 bg-black/55" />
      <img src={ASSETS.cemento} alt="" aria-hidden className="absolute inset-0 w-full h-full object-cover opacity-[0.12] mix-blend-overlay pointer-events-none" />
      <div className="absolute inset-0 blueprint-grid opacity-[0.04] mix-blend-screen animate-blueprint" />
      {/* Vignettatura laterale */}
      <div className="absolute inset-0 pointer-events-none" style={{ background: "radial-gradient(ellipse at center, transparent 42%, rgba(0,0,0,0.7) 100%)" }} />
      <div className="absolute bottom-0 left-0 right-0 h-64 bg-gradient-to-t from-bg to-transparent" />

      <div className="relative z-10 px-6 text-center max-w-5xl mx-auto pt-24 pb-32">
        <div
          ref={eyebrowRef}
          style={{ opacity: 0 }}
          className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-8"
        >
          ANTEPRIMA 2026 · NAPOLI &amp; CAMPANIA
        </div>

        <h1
          ref={headlineRef}
          style={{ opacity: 0 }}
          className="font-display font-bold uppercase text-5xl md:text-7xl lg:text-8xl leading-[0.95] tracking-tight text-ink"
        >
          Scopri quanto costa ristrutturare <span className="text-brand">casa tua</span>. In 60 secondi.
        </h1>

        <div className="mt-6 font-display font-semibold uppercase tracking-[0.1em] text-lg md:text-2xl text-ink/70">
          Per il tuo{" "}
          <motion.span
            key={roleIdx}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-brand font-bold inline-block"
          >
            {ROLES[roleIdx]}
          </motion.span>{" "}
          a Napoli e Campania.
        </div>

        <p
          ref={descRef}
          style={{ opacity: 0 }}
          className="mt-8 font-body text-base md:text-lg text-fog max-w-2xl mx-auto"
        >
          Compila pochi dati sul tuo immobile. Ricevi una stima personalizzata su 3 livelli,
          un'anteprima visiva del progetto e una proposta di sopralluogo gratuito.
        </p>

        <div
          ref={ctaRef}
          style={{ opacity: 0 }}
          className="mt-10"
        >
          <button
            data-testid="hero-cta-stima"
            onClick={scrollToConfig}
            className="group bg-brand text-white rounded-full px-12 py-5 text-lg font-display font-semibold uppercase tracking-wider inline-flex items-center gap-3 transition-transform hover:scale-105"
            style={{ boxShadow: "0 8px 32px rgba(198,40,40,0.35)" }}
          >
            Avvia stima gratuita
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        <div className="mt-8 font-display font-normal uppercase tracking-[0.2em] text-xs text-fog">
          +200 cantieri · +15 anni in Campania · Sopralluogo sempre gratuito
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-3">
        <span className="font-display font-semibold uppercase tracking-[0.2em] text-[10px] text-fog">
          Scorri
        </span>
        <div className="w-px h-12 bg-stroke relative overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-1/3 bg-brand animate-scroll-down" />
        </div>
      </div>
    </section>
  );
}
