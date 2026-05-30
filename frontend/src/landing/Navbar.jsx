import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

const LINKS = [
  { label: "Home", id: "hero" },
  { label: "Servizi", id: "configuratore" },
  { label: "Progetti", id: "progetti" },
  { label: "Preventivo AI", id: "configuratore" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState("Home");
  const navigate = useNavigate();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 100);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id, label) => {
    setActive(label);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <nav className="fixed top-5 left-1/2 -translate-x-1/2 z-50">
      <div
        className={`backdrop-blur-md border border-white/10 bg-surface/70 inline-flex items-center rounded-full px-2 py-2 transition-shadow ${
          scrolled ? "shadow-lg shadow-black/40" : ""
        }`}
      >
        {/* Logo */}
        <div className="relative w-10 h-10 rounded-full p-[2px] accent-metallic animate-gradient-shift">
          <div className="w-full h-full rounded-full bg-bg flex items-center justify-center">
            <span className="font-display font-bold text-sm text-ink">GB</span>
          </div>
        </div>

        <div className="w-px h-5 bg-stroke mx-2 hidden md:block" />

        <div className="hidden md:flex items-center gap-1">
          {LINKS.map((l) => (
            <button
              key={l.label}
              data-testid={`nav-${l.label.toLowerCase().replace(/\s/g, "-")}`}
              onClick={() => scrollTo(l.id, l.label)}
              className={`font-display font-semibold uppercase tracking-[0.15em] text-xs rounded-full px-4 py-2 transition-colors ${
                active === l.label
                  ? "bg-brand/15 text-brand"
                  : "text-ink/80 hover:bg-stroke/50 hover:text-ink"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <div className="relative ml-2 group">
          <span className="absolute -inset-[2px] rounded-full accent-gradient animate-gradient-shift opacity-90" />
          <button
            data-testid="nav-cta-sopralluogo"
            onClick={() => scrollTo("configuratore", "Preventivo AI")}
            className="relative rounded-full bg-surface px-4 py-2 font-display font-semibold uppercase tracking-[0.15em] text-xs text-ink inline-flex items-center gap-1 group-hover:bg-surface-2 transition-colors"
          >
            Richiedi sopralluogo <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-5 bg-stroke mx-2 hidden md:block" />
        <button
          data-testid="nav-staff-login"
          onClick={() => navigate("/login")}
          className="text-fog hover:text-ink text-xs font-display uppercase tracking-[0.15em] px-3 py-2 transition-colors"
        >
          Staff
        </button>
      </div>
    </nav>
  );
}
