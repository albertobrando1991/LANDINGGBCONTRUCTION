import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  Building2,
  Briefcase,
  Store,
  Warehouse,
  ArrowRight,
  ArrowLeft,
  Check,
  Plus,
  Minus,
  Flame,
} from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { STYLE_VIDEO_POSTERS } from "@/lib/assets";

const TIPI = [
  { id: "appartamento", label: "Appartamento", Icon: Home },
  { id: "villa", label: "Villa", Icon: Building2 },
  { id: "ufficio", label: "Ufficio", Icon: Briefcase },
  { id: "negozio", label: "Negozio", Icon: Store },
  { id: "capannone", label: "Capannone", Icon: Warehouse },
];

const INTERVENTI = [
  {
    id: "essenziale",
    titolo: "Rinnovare",
    livello: "essenziale",
    sub: "Layout invariato, finiture nuove",
    body: "Ristrutturazione completa con stessa disposizione. Impianti a norma, pavimenti, rivestimenti, tinteggiatura nuovi.",
    tag: "Forniture escluse",
    border: "border-brand",
    badge: null,
  },
  {
    id: "premium",
    titolo: "Trasformare",
    livello: "premium",
    sub: "Ridisegna gli spazi, finiture di qualità",
    body: "Ristrutturazione con redistribuzione interna. Possibilità di spostare tramezzi e ridisegnare il layout.",
    tag: "Forniture escluse",
    border: "border-fog",
    badge: "Più scelto",
  },
  {
    id: "luxury",
    titolo: "Tutto incluso",
    livello: "luxury",
    sub: "Premium + forniture complete da capitolato",
    body: "Tutto quello che è nel Premium + sanitari, rubinetterie, porte, pavimenti, illuminazione inclusi.",
    tag: "Forniture incluse",
    border: "border-gold",
    badge: null,
  },
];

const STILI = [
  "Moderno minimal",
  "Classico elegante",
  "Industrial loft",
  "Contemporaneo caldo",
];
const TEMPI = [
  { id: "Subito", label: "Subito", hot: true },
  { id: "Entro 3 mesi", label: "Entro 3 mesi" },
  { id: "Entro 6 mesi", label: "Entro 6 mesi" },
  { id: "Sto valutando", label: "Sto valutando" },
];
const MICRO = [
  "Perfetto...",
  "Ottima scelta...",
  "Manca poco...",
  "Quasi pronto...",
  "Ultimi dettagli...",
];

const initial = {
  tipo_immobile: "",
  mq: 80,
  livello: "",
  cucina: true,
  bagni: 1,
  camere: 2,
  soggiorno: true,
  ingresso: false,
  balconi: false,
  stile: "",
  tempistiche: "",
};

export default function Configurator({ onComplete }) {
  const [step, setStep] = useState(1);
  const [cfg, setCfg] = useState(initial);
  const [loading, setLoading] = useState(false);
  const [microIdx] = useState(() => Math.floor(Math.random() * MICRO.length));

  const set = (patch) => setCfg((c) => ({ ...c, ...patch }));

  useEffect(() => {
    if (step < 4) return undefined;

    const preloadedImages = STILI.map((style) => {
      const image = new Image();
      image.decoding = "async";
      image.src = STYLE_VIDEO_POSTERS[style];
      return image;
    });

    return () => {
      preloadedImages.forEach((image) => {
        image.src = "";
      });
    };
  }, [step]);

  const canContinue = () => {
    if (step === 1) return !!cfg.tipo_immobile;
    if (step === 3) return !!cfg.livello;
    if (step === 5) return !!cfg.stile;
    if (step === 6) return !!cfg.tempistiche;
    return true;
  };

  const next = () => {
    if (step === 6) {
      onComplete({ ...cfg, has_files: false });
      return;
    }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setStep((s) => Math.min(s + 1, 6));
    }, 600);
  };
  const prev = () => setStep((s) => Math.max(s - 1, 1));

  const Counter = ({ label, value, min, max, onChange }) => (
    <div className="flex items-center justify-between bg-surface border border-stroke rounded-full px-5 py-3">
      <span className="font-display font-semibold uppercase text-sm text-ink">
        {label}
      </span>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          className="w-7 h-7 rounded-full bg-surface-2 text-ink flex items-center justify-center hover:bg-brand transition-colors"
        >
          <Minus className="w-4 h-4" />
        </button>
        <span className="font-display font-bold text-lg text-brand w-6 text-center">
          {value}
        </span>
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          className="w-7 h-7 rounded-full bg-surface-2 text-ink flex items-center justify-center hover:bg-brand transition-colors"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </div>
  );

  const Chip = ({ active, onClick, children, testId }) => (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`font-display font-semibold uppercase text-sm rounded-full px-5 py-3 border transition-all ${
        active
          ? "bg-brand text-white border-brand"
          : "bg-surface text-ink border-stroke hover:border-brand"
      }`}
    >
      {children}
    </button>
  );

  return (
    <section
      id="configuratore"
      className="relative min-h-screen touch-pan-y overflow-x-clip bg-bg px-5 py-20 sm:px-6"
    >
      <div className="absolute inset-0 blueprint-grid opacity-[0.03]" />
      <div className="relative mx-auto w-full max-w-5xl min-w-0">
        {/* Header */}
        <div className="text-center mb-10">
          <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3">
            Stima intelligente GB
          </p>
          <h2 className="font-display font-bold uppercase text-4xl md:text-6xl tracking-tight text-ink">
            Configura. <span className="text-brand">Visualizza.</span> Ricevi.
          </h2>
          <p className="font-body text-fog mt-3">
            60 secondi. 6 domande. Tre proposte personalizzate.
          </p>
        </div>

        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="font-display font-semibold uppercase text-xs text-ink">
              Step {step} di 6
            </span>
            <span className="font-display text-xs text-fog">
              {Math.round((step / 6) * 100)}%
            </span>
          </div>
          <div className="h-1 bg-stroke rounded-full overflow-hidden">
            <motion.div
              className="h-full accent-gradient"
              animate={{ width: `${(step / 6) * 100}%` }}
              transition={{ duration: 0.4 }}
            />
          </div>
        </div>

        <div className="relative min-h-[640px] md:min-h-[460px]">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="font-display font-semibold uppercase tracking-[0.2em] text-xl text-brand"
              >
                {MICRO[microIdx]}
              </motion.p>
            </div>
          ) : (
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className="min-w-0"
              >
                {step === 1 && (
                  <>
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-6 text-center">
                      Che tipo di immobile vuoi ristrutturare?
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                      {TIPI.map(({ id, label, Icon }) => {
                        const sel = cfg.tipo_immobile === id;
                        return (
                          <button
                            key={id}
                            data-testid={`tipo-${id}`}
                            onClick={() => set({ tipo_immobile: id })}
                            className={`relative bg-surface border-2 rounded-2xl p-6 flex flex-col items-center gap-3 transition-colors ${sel ? "border-brand bg-brand/10" : "border-stroke hover:border-brand"}`}
                          >
                            {sel && (
                              <Check className="absolute top-2 right-2 w-5 h-5 text-brand" />
                            )}
                            <Icon
                              className={`w-10 h-10 ${sel ? "text-brand" : "text-fog"}`}
                              strokeWidth={2}
                            />
                            <span className="font-display font-semibold uppercase text-sm text-ink">
                              {label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}

                {step === 2 && (
                  <div className="text-center">
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-8">
                      Quanti metri quadri?
                    </h3>
                    <div className="font-display font-bold text-7xl text-brand mb-8">
                      {cfg.mq} mq
                    </div>
                    <div className="max-w-xl mx-auto px-4">
                      <Slider
                        data-testid="slider-mq"
                        className="touch-pan-y"
                        value={[cfg.mq]}
                        min={30}
                        max={500}
                        step={5}
                        onValueChange={(v) => set({ mq: v[0] })}
                      />
                      <div className="flex justify-between font-display text-xs text-fog mt-3">
                        <span>30 mq</span>
                        <span>500 mq</span>
                      </div>
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <>
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-6 text-center">
                      Cosa vuoi fare?
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                      {INTERVENTI.map((it) => {
                        const sel = cfg.livello === it.livello;
                        return (
                          <button
                            key={it.id}
                            data-testid={`intervento-${it.livello}`}
                            onClick={() => set({ livello: it.livello })}
                            className={`relative text-left bg-surface border-2 rounded-2xl p-6 transition-colors ${sel ? "border-brand bg-brand/5" : it.border}`}
                          >
                            {it.badge && (
                              <span className="absolute -top-3 left-6 gold-gradient text-bg font-display font-bold uppercase text-[10px] px-3 py-1 rounded-full">
                                {it.badge}
                              </span>
                            )}
                            <h4
                              className={`font-display font-bold uppercase text-xl mb-1 ${it.livello === "luxury" ? "text-gold" : "text-ink"}`}
                            >
                              {it.titolo}
                            </h4>
                            <p className="font-display uppercase text-xs text-brand mb-3">
                              {it.sub}
                            </p>
                            <p className="font-body text-sm text-fog mb-4">
                              {it.body}
                            </p>
                            <span
                              className={`font-display uppercase text-xs ${it.livello === "luxury" ? "text-gold" : "text-fog"}`}
                            >
                              {it.tag}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}

                {step === 4 && (
                  <>
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-6 text-center">
                      Quali ambienti?
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                      <Chip
                        testId="amb-cucina"
                        active={cfg.cucina}
                        onClick={() => set({ cucina: !cfg.cucina })}
                      >
                        Cucina
                      </Chip>
                      <Counter
                        label="Bagni"
                        value={cfg.bagni}
                        min={0}
                        max={4}
                        onChange={(v) => set({ bagni: v })}
                      />
                      <Counter
                        label="Camere"
                        value={cfg.camere}
                        min={0}
                        max={5}
                        onChange={(v) => set({ camere: v })}
                      />
                      <Chip
                        testId="amb-soggiorno"
                        active={cfg.soggiorno}
                        onClick={() => set({ soggiorno: !cfg.soggiorno })}
                      >
                        Soggiorno
                      </Chip>
                      <Chip
                        testId="amb-ingresso"
                        active={cfg.ingresso}
                        onClick={() => set({ ingresso: !cfg.ingresso })}
                      >
                        Ingresso
                      </Chip>
                      <Chip
                        testId="amb-balconi"
                        active={cfg.balconi}
                        onClick={() => set({ balconi: !cfg.balconi })}
                      >
                        Balconi / Terrazzi
                      </Chip>
                    </div>
                  </>
                )}

                {step === 5 && (
                  <>
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-6 text-center">
                      Che stile ti rappresenta?
                    </h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      {STILI.map((s) => {
                        const sel = cfg.stile === s;
                        return (
                          <button
                            key={s}
                            data-testid={`stile-${s.split(" ")[0].toLowerCase()}`}
                            onClick={() => set({ stile: s })}
                            className={`style-video-card relative aspect-[4/5] rounded-2xl overflow-hidden border-2 bg-surface transition-colors ${sel ? "ring-4 ring-brand border-brand" : "border-stroke hover:border-brand"}`}
                          >
                            <img
                              src={STYLE_VIDEO_POSTERS[s]}
                              alt=""
                              aria-hidden="true"
                              loading={step === 5 ? "eager" : "lazy"}
                              decoding="async"
                              className="pointer-events-none absolute inset-0 h-full w-full object-cover"
                            />
                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />
                            <span className="absolute bottom-3 left-3 right-3 font-display font-semibold uppercase text-sm text-ink">
                              {s}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}

                {step === 6 && (
                  <>
                    <h3 className="font-display font-bold uppercase text-2xl text-ink mb-8 text-center">
                      Quando vorresti iniziare?
                    </h3>
                    <div className="flex flex-wrap justify-center gap-4">
                      {TEMPI.map((t) => {
                        const sel = cfg.tempistiche === t.id;
                        return (
                          <button
                            key={t.id}
                            data-testid={`tempo-${t.id.split(" ")[0].toLowerCase()}`}
                            onClick={() => set({ tempistiche: t.id })}
                            className={`font-display font-semibold uppercase rounded-full px-8 py-4 border inline-flex items-center gap-2 transition-colors ${sel ? "bg-brand text-white border-brand" : "bg-surface text-ink border-stroke hover:border-brand"}`}
                          >
                            {t.hot && <Flame className="w-4 h-4" />}
                            {t.label}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-10">
          <button
            data-testid="config-back"
            onClick={prev}
            disabled={step === 1}
            className="font-display font-semibold uppercase text-sm text-fog hover:text-ink inline-flex items-center gap-2 disabled:opacity-30 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Indietro
          </button>
          <button
            data-testid="config-next"
            onClick={next}
            disabled={!canContinue()}
            className="bg-brand text-white rounded-full font-display font-semibold uppercase tracking-wider inline-flex items-center gap-2 transition-colors disabled:opacity-40 hover:bg-brand-dark px-8 py-4"
          >
            Continua <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </section>
  );
}
