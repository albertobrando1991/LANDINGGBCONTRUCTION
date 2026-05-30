import { useState, useRef } from "react";
import LoadingScreen from "@/landing/LoadingScreen";
import Navbar from "@/landing/Navbar";
import ImmersiveHero from "@/landing/ImmersiveHero";
import SocialProof from "@/landing/SocialProof";
import Configurator from "@/landing/Configurator";
import ContactGate from "@/landing/ContactGate";
import Output from "@/landing/Output";
import SecondChance from "@/landing/SecondChance";
import Team from "@/landing/Team";
import Footer from "@/landing/Footer";

export default function Landing() {
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState("config"); // config | gate | output
  const [config, setConfig] = useState(null);
  const [result, setResult] = useState(null);
  const flowRef = useRef(null);

  const scrollFlow = () =>
    setTimeout(() => flowRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);

  const handleConfigDone = (cfg) => {
    setConfig(cfg);
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

      <div ref={flowRef}>
        {phase === "config" && <Configurator onComplete={handleConfigDone} />}
        {phase === "gate" && <ContactGate config={config} onSubmit={handleGateSubmit} />}
        {phase === "output" && <Output estimate={result?.estimate} />}
      </div>

      <SecondChance />
      <Team />
      <Footer />
    </div>
  );
}
