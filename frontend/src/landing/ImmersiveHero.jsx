import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, ChevronDown } from "lucide-react";
import { ASSETS, STYLE_VIDEOS } from "@/lib/assets";
import HlsVideo from "@/components/HlsVideo";

gsap.registerPlugin(ScrollTrigger);

const ROLES = ["appartamento", "ufficio", "condominio", "negozio", "capannone"];

export default function ImmersiveHero() {
  const [roleIdx, setRoleIdx] = useState(0);
  const wrapRef = useRef(null);
  const videoWrapRef = useRef(null);
  const vignetteRef = useRef(null);
  const hintRef = useRef(null);
  const contentRef = useRef(null);

  // parallax targets
  const mouse = useRef({ x: 0, y: 0 });
  const current = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const id = setInterval(() => setRoleIdx((i) => (i + 1) % ROLES.length), 2000);
    return () => clearInterval(id);
  }, []);

  // Scroll-driven cinematic "fly-into-render" timeline
  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: wrapRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 1,
          onUpdate: (self) => {
            const on = self.progress > 0.4;
            if (contentRef.current) {
              contentRef.current.style.pointerEvents = on ? "auto" : "none";
            }
          },
        },
      });

      // dolly-in: zoom progressivo dentro il render
      tl.fromTo(videoWrapRef.current, { scale: 1.12 }, { scale: 1.42, ease: "none" }, 0);
      // vignettatura che si chiude
      tl.fromTo(vignetteRef.current, { opacity: 0.32 }, { opacity: 0.9, ease: "none" }, 0);
      // hint scompare appena si entra
      tl.to(hintRef.current, { opacity: 0, duration: 0.12, ease: "none" }, 0);
      // headline reveal DOPO il volo
      tl.fromTo(
        contentRef.current,
        { opacity: 0, y: 60, filter: "blur(14px)" },
        { opacity: 1, y: 0, filter: "blur(0px)", ease: "power3.out", duration: 0.3 },
        0.42
      );
    }, wrapRef);

    const r = setTimeout(() => ScrollTrigger.refresh(), 600);
    return () => {
      clearTimeout(r);
      ctx.revert();
    };
  }, []);

  // Mouse parallax con lerp (smoothing organico)
  useEffect(() => {
    const onMove = (e) => {
      mouse.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouse.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove);
    let raf;
    const loop = () => {
      current.current.x += (mouse.current.x - current.current.x) * 0.06;
      current.current.y += (mouse.current.y - current.current.y) * 0.06;
      if (videoWrapRef.current) {
        videoWrapRef.current.style.transform =
          `translate3d(${current.current.x * -18}px, ${current.current.y * -12}px, 0)`;
      }
      if (contentRef.current) {
        contentRef.current.style.setProperty("--px", `${current.current.x * 10}px`);
        contentRef.current.style.setProperty("--py", `${current.current.y * 8}px`);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  const scrollToConfig = () =>
    document.getElementById("configuratore")?.scrollIntoView({ behavior: "smooth" });

  return (
    <section id="hero" ref={wrapRef} className="relative h-[260vh]">
      <div className="sticky top-0 h-screen overflow-hidden">
        {/* Render walkthrough — "volo dentro il progetto" */}
        <div ref={videoWrapRef} className="absolute inset-0 will-change-transform" style={{ transform: "scale(1.12)" }}>
          <HlsVideo src={STYLE_VIDEOS["Moderno minimal"]} className="absolute inset-0 w-full h-full object-cover" />
        </div>

        {/* Overlay cinematografico */}
        <div className="absolute inset-0 bg-black/45" />
        <img src={ASSETS.cemento} alt="" aria-hidden className="absolute inset-0 w-full h-full object-cover opacity-[0.10] mix-blend-overlay pointer-events-none" />
        <div className="absolute inset-0 blueprint-grid opacity-[0.05] mix-blend-screen animate-blueprint pointer-events-none" />
        <div ref={vignetteRef} className="absolute inset-0 pointer-events-none" style={{ background: "radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.92) 100%)", opacity: 0.4 }} />
        <div className="absolute bottom-0 left-0 right-0 h-64 bg-gradient-to-t from-bg to-transparent pointer-events-none" />

        {/* Hint iniziale */}
        <div ref={hintRef} className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 pointer-events-none">
          <div className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-4">
            GB Construction · Napoli &amp; Campania
          </div>
          <h2 className="font-display font-bold uppercase text-4xl md:text-6xl lg:text-7xl text-ink/90 leading-[0.95] max-w-3xl">
            Entra nel tuo <span className="text-brand">progetto</span>.
          </h2>
          <div className="mt-10 flex flex-col items-center gap-2">
            <span className="font-display uppercase tracking-[0.3em] text-[10px] text-fog">Scorri per entrare</span>
            <ChevronDown className="w-5 h-5 text-brand animate-bounce" />
          </div>
        </div>

        {/* Hero content — reveal DOPO il volo */}
        <div
          ref={contentRef}
          style={{ opacity: 0, transform: "translate(var(--px,0), var(--py,0))" }}
          className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 pointer-events-none"
        >
          <div className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-6">
            ANTEPRIMA 2026 · NAPOLI &amp; CAMPANIA
          </div>
          <h1 className="font-display font-bold uppercase text-5xl md:text-7xl lg:text-8xl leading-[0.95] tracking-tight text-ink max-w-5xl">
            Scopri quanto costa ristrutturare <span className="text-brand">casa tua</span>. In 60 secondi.
          </h1>
          <div className="mt-6 font-display font-semibold uppercase tracking-[0.1em] text-lg md:text-2xl text-ink/70">
            Per il tuo{" "}
            <motion.span key={roleIdx} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="text-brand font-bold inline-block">
              {ROLES[roleIdx]}
            </motion.span>{" "}
            a Napoli e Campania.
          </div>
          <p className="mt-7 font-body text-base md:text-lg text-fog max-w-2xl">
            Compila pochi dati sul tuo immobile. Ricevi una stima personalizzata su 3 livelli,
            un'anteprima visiva del progetto e una proposta di sopralluogo gratuito.
          </p>
          <div className="mt-9">
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
          <div className="mt-7 font-display font-normal uppercase tracking-[0.2em] text-xs text-fog">
            +200 cantieri · +15 anni in Campania · Sopralluogo sempre gratuito
          </div>
        </div>
      </div>
    </section>
  );
}
