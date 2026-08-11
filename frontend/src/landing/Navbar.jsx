import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";
import { openBooking } from "@/lib/booking";

// Link originali della navbar — non rimuovere né rinominare
const LINKS = [
  { label: "Home", id: "hero" },
  { label: "Servizi", id: "configuratore" },
  { label: "Progetti", id: "progetti" },
  { label: "Preventivo AI", id: "configuratore" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState("Home");
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const menuId = useId();

  useEffect(() => {
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        setScrolled(window.scrollY > 100);
        ticking = false;
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.classList.add("is-scroll-locked");

    const onKey = (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.documentElement.classList.remove("is-scroll-locked");
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const scrollTo = (id, label) => {
    setActive(label);
    setMenuOpen(false);
    requestAnimationFrame(() => {
      scheduleSmoothScrollToElement(document.getElementById(id));
    });
  };

  return (
    <>
      <nav
        className="fixed top-3 left-1/2 z-50 w-[calc(100vw-24px)] -translate-x-1/2 md:top-5 md:w-auto"
        style={{
          top: "max(0.75rem, env(safe-area-inset-top))",
        }}
        aria-label="Navigazione principale"
      >
        <div
          className={`backdrop-blur-md border border-white/10 bg-surface/70 flex w-full items-center justify-between rounded-full px-2 py-1.5 transition-shadow md:inline-flex md:w-auto md:justify-start md:py-2 ${
            scrolled ? "shadow-lg shadow-black/40" : ""
          }`}
        >
          {/* Logo — invariato */}
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
                type="button"
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
              type="button"
              data-testid="nav-cta-sopralluogo"
              onClick={() => {
                setMenuOpen(false);
                openBooking();
              }}
              className="relative inline-flex items-center gap-1 rounded-full bg-surface px-3 py-2 font-display text-[10px] font-semibold uppercase tracking-[0.12em] text-ink transition-colors group-hover:bg-surface-2 sm:text-xs md:px-4 md:tracking-[0.15em] min-h-10 touch-manipulation"
            >
              <span className="sm:hidden">Sopralluogo</span>
              <span className="hidden sm:inline">Prenota sopralluogo</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="w-px h-5 bg-stroke mx-2 hidden md:block" />
          {/* Accesso stabile per personale e clienti invitati */}
          <button
            type="button"
            data-testid="nav-staff-login"
            onClick={() => navigate("/login")}
            className="px-2 py-2 font-display text-[10px] uppercase tracking-[0.12em] text-fog transition-colors hover:text-ink sm:text-xs md:px-3 md:tracking-[0.15em] min-h-10 touch-manipulation"
          >
            <span className="sm:hidden">Clienti</span>
            <span className="hidden sm:inline">Area clienti</span>
          </button>

          {/* Aggiunta mobile: menu con gli stessi link desktop */}
          <button
            type="button"
            data-testid="nav-mobile-menu"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            aria-label={menuOpen ? "Chiudi menu" : "Apri menu"}
            onClick={() => setMenuOpen((open) => !open)}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-ink transition-colors touch-manipulation hover:bg-stroke/40 md:hidden"
          >
            {menuOpen ? (
              <X className="h-5 w-5" aria-hidden />
            ) : (
              <Menu className="h-5 w-5" aria-hidden />
            )}
          </button>
        </div>
      </nav>

      {/* Menu mobile — replica esatta dei LINKS originali + CTA */}
      <div
        id={menuId}
        role="dialog"
        aria-modal="true"
        aria-label="Menu di navigazione"
        className={`fixed inset-0 z-40 md:hidden ${
          menuOpen ? "pointer-events-auto" : "pointer-events-none"
        }`}
      >
        <button
          type="button"
          aria-label="Chiudi menu"
          onClick={() => setMenuOpen(false)}
          className={`absolute inset-0 bg-black/70 backdrop-blur-sm transition-opacity duration-300 ${
            menuOpen ? "opacity-100" : "opacity-0"
          }`}
        />
        <div
          className={`absolute inset-x-0 top-0 border-b border-stroke bg-bg/95 px-5 pb-8 pt-[calc(4.5rem+env(safe-area-inset-top))] shadow-2xl transition-transform duration-300 ease-out ${
            menuOpen ? "translate-y-0" : "-translate-y-full"
          }`}
          style={{
            paddingBottom: "max(2rem, env(safe-area-inset-bottom))",
          }}
        >
          <ul className="mx-auto flex max-w-md flex-col gap-1">
            {LINKS.map((l) => (
              <li key={l.label}>
                <button
                  type="button"
                  data-testid={`nav-mobile-${l.label.toLowerCase().replace(/\s/g, "-")}`}
                  onClick={() => scrollTo(l.id, l.label)}
                  className={`flex min-h-12 w-full items-center justify-between rounded-2xl border px-5 py-3.5 text-left font-display text-sm font-semibold uppercase tracking-[0.14em] transition-colors touch-manipulation ${
                    active === l.label
                      ? "border-brand/40 bg-brand/10 text-brand"
                      : "border-stroke bg-surface text-ink active:bg-surface-2"
                  }`}
                >
                  {l.label}
                  <ArrowUpRight className="h-4 w-4 opacity-60" aria-hidden />
                </button>
              </li>
            ))}
          </ul>

          <div className="mx-auto mt-5 flex max-w-md flex-col gap-3">
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                openBooking();
              }}
              className="flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-brand px-5 py-3.5 font-display text-sm font-semibold uppercase tracking-wider text-white touch-manipulation"
            >
              Prenota sopralluogo
              <ArrowUpRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
