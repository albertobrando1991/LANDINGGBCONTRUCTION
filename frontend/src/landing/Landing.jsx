import { useState, useRef } from "react";
import LoadingScreen from "@/landing/LoadingScreen";
import Navbar from "@/landing/Navbar";
import ImmersiveHero from "@/landing/ImmersiveHero";
import SocialProof from "@/landing/SocialProof";
import Packages from "@/landing/Packages";
import Configurator from "@/landing/Configurator";
import AIArchitect from "@/landing/AIArchitect";
import ContactGate from "@/landing/ContactGate";
import Output from "@/landing/Output";
import SecondChance from "@/landing/SecondChance";
import Team from "@/landing/Team";
import Footer from "@/landing/Footer";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";

export default function Landing() {
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("config"); // config | architect | gate | output
  const [config, setConfig] = useState(null);
  const [result, setResult] = useState(null);
  const flowRef = useRef(null);

  const scrollFlow = () => {
    setTimeout(() => {
      scheduleSmoothScrollToElement(flowRef.current, { offset: 86 });
    }, 80);
  };

  const handleConfigDone = (cfg) => {
    setConfig(cfg);
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
    setPhase("gate");
    scrollFlow();
  };

  const handleArchitectSkip = () => {
    setPhase("gate");
    scrollFlow();
  };

  const handleGateSubmit = (data) => {
    setResult(data);
    setPhase("output");
    scrollFlow();
  };

  return (
    <div className="bg-bg text-ink min-h-screen">
      {loading && <LoadingScreen onDone={() => setLoading(false)} />}
      <Navbar />
      <ImmersiveHero />
      <SocialProof />
      <Packages />

      <div ref={flowRef}>
        {phase === "config" && <Configurator onComplete={handleConfigDone} />}
        {phase === "architect" && (
          <AIArchitect
            baseConfig={config}
            onComplete={handleArchitectDone}
            onSkip={handleArchitectSkip}
          />
        )}
        {phase === "gate" && (
          <ContactGate config={config} onSubmit={handleGateSubmit} />
        )}
        {phase === "output" && (
          <Output estimate={result?.estimate} aiProject={config?.aiArchitect} />
        )}
      </div>

      <SecondChance />
      <Team />
      <Footer />
    </div>
  );
}
