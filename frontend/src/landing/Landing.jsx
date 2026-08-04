import { lazy, memo, Suspense, useEffect, useRef, useState } from "react";
import LoadingScreen from "@/landing/LoadingScreen";
import Navbar from "@/landing/Navbar";
import ImmersiveHero from "@/landing/ImmersiveHero";
import BookingModal from "@/landing/BookingModal";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";

const SocialProof = lazy(() => import("@/landing/SocialProof"));
const Packages = lazy(() => import("@/landing/Packages"));
const Configurator = lazy(() => import("@/landing/Configurator"));
const AIArchitect = lazy(() => import("@/landing/AIArchitect"));
const QuickDetails = lazy(() => import("@/landing/QuickDetails"));
const ContactGate = lazy(() => import("@/landing/ContactGate"));
const Output = lazy(() => import("@/landing/Output"));
const SecondChance = lazy(() => import("@/landing/SecondChance"));
const Team = lazy(() => import("@/landing/Team"));
const Footer = lazy(() => import("@/landing/Footer"));

const StaticNavbar = memo(Navbar);
const StaticImmersiveHero = memo(ImmersiveHero);

function SectionFallback({ label = "Caricamento sezione" }) {
  return <div className="min-h-32 bg-bg" role="status" aria-label={label} />;
}

export default function Landing() {
  const [loading, setLoading] = useState(true);
  // Nuovo ordine: prima i dati e il lead, poi (opzionale) l'analisi planimetria.
  const [phase, setPhase] = useState("config"); // config | details | gate | output | architect
  const [config, setConfig] = useState(null);
  const [result, setResult] = useState(null);
  const flowRef = useRef(null);

  useEffect(() => {
    document.title = "GB Construction | Ristrutturazioni";
  }, []);

  const scrollFlow = () => {
    setTimeout(() => {
      scheduleSmoothScrollToElement(flowRef.current, { offset: 86 });
    }, 80);
  };

  const handleConfigDone = (cfg) => {
    setConfig(cfg);
    // Senza planimetria a questo punto: raccogli dettagli semplici per affinare la stima.
    setPhase("details");
    scrollFlow();
  };

  const handleDetailsDone = (extra) => {
    setConfig((current) => ({ ...current, ...extra, has_files: false }));
    setPhase("gate");
    scrollFlow();
  };

  const handleDetailsBack = () => {
    setPhase("config");
    scrollFlow();
  };

  const handleGateSubmit = (data, values) => {
    setResult(data);
    // Lead creato e inoltrato: salva id + contatti per collegare planimetria e prenotazione sopralluogo.
    setConfig((current) => ({
      ...current,
      lead_id: data?.id,
      lead_contact: values
        ? {
            leadId: data?.id,
            nome: values.nome,
            email: values.email,
            telefono: values.telefono,
            indirizzo: values.indirizzo,
          }
        : { leadId: data?.id },
    }));
    setPhase("output");
    scrollFlow();
  };

  const handleStartArchitect = () => {
    setPhase("architect");
    scrollFlow();
  };

  const handleArchitectDone = (aiProject) => {
    setConfig((current) => ({
      ...current,
      has_files: true,
      aiArchitect: aiProject,
      ai_architect_job_id: aiProject.id,
      ai_architect_summary: aiProject.ai_architect_summary,
    }));
    setPhase("output");
    scrollFlow();
  };

  const handleArchitectSkip = () => {
    // L'analisi planimetria e opzionale: torna al preventivo gia generato.
    setPhase("output");
    scrollFlow();
  };

  return (
    <div className="bg-bg text-ink min-h-screen">
      {loading && <LoadingScreen onDone={() => setLoading(false)} />}
      <StaticNavbar />
      <StaticImmersiveHero />
      <Suspense fallback={<SectionFallback label="Caricamento progetti" />}>
        <SocialProof />
        <Packages />
      </Suspense>

      <div ref={flowRef}>
        <Suspense
          fallback={<SectionFallback label="Caricamento configuratore" />}
        >
          {phase === "config" && <Configurator onComplete={handleConfigDone} />}
          {phase === "details" && (
            <QuickDetails
              baseConfig={config}
              onComplete={handleDetailsDone}
              onBack={handleDetailsBack}
            />
          )}
          {phase === "gate" && (
            <ContactGate config={config} onSubmit={handleGateSubmit} />
          )}
          {phase === "output" && (
            <Output
              estimate={result?.estimate}
              aiProject={config?.aiArchitect}
              onStartArchitect={
                config?.aiArchitect ? undefined : handleStartArchitect
              }
              bookingContext={config?.lead_contact}
            />
          )}
          {phase === "architect" && (
            <AIArchitect
              baseConfig={config}
              leadId={config?.lead_id}
              onComplete={handleArchitectDone}
              onSkip={handleArchitectSkip}
            />
          )}
        </Suspense>
      </div>

      <Suspense fallback={<SectionFallback label="Caricamento contenuti" />}>
        <SecondChance />
        <Team />
        <Footer />
      </Suspense>
      <BookingModal />
    </div>
  );
}
