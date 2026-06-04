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
    <nav className="fixed top-3 left-1/2 z-50 w-[calc(100vw-24px)] -translate-x-1/2 md:top-5 md:w-auto">
      <div
        className={`backdrop-blur-md border border-white/10 bg-surface/70 flex w-full items-center justify-between rounded-full px-2 py-1.5 transition-shadow md:inline-flex md:w-auto md:justify-start md:py-2 ${
          scrolled ? "shadow-lg shadow-black/40" : ""
        }`}
      >
        {/* Logo */}
        <div className="relative h-9 w-9 shrink-0 rounded-full p-[2px] accent-metallic animate-gradient-shift md:h-10 md:w-10">
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

        <div className="relative ml-1 group md:ml-2">
          <span className="absolute -inset-[2px] rounded-full accent-gradient animate-gradient-shift opacity-90" />
          <button
            data-testid="nav-cta-sopralluogo"
            onClick={() => scrollTo("configuratore", "Preventivo AI")}
            className="relative inline-flex items-center gap-1 rounded-full bg-surface px-3 py-2 font-display text-[10px] font-semibold uppercase tracking-[0.12em] text-ink transition-colors group-hover:bg-surface-2 sm:text-xs md:px-4 md:tracking-[0.15em]"
          >
            <span className="sm:hidden">Sopralluogo</span>
            <span className="hidden sm:inline">Richiedi sopralluogo</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="w-px h-5 bg-stroke mx-2 hidden md:block" />
        <button
          data-testid="nav-staff-login"
          onClick={() => navigate("/login")}
          className="px-2 py-2 font-display text-[10px] uppercase tracking-[0.12em] text-fog transition-colors hover:text-ink sm:text-xs md:px-3 md:tracking-[0.15em]"
        >
          Staff
        </button>
      </div>
    </nav>
  );
}
