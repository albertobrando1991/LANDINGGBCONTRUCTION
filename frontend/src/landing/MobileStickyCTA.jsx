import { useEffect, useState } from "react";
import { ArrowRight, MessageCircle } from "lucide-react";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";
import { WHATSAPP } from "@/lib/assets";

/**
 * Sticky bottom bar for smartphones: keeps primary conversion actions
 * in the thumb zone after the user leaves the hero.
 */
export default function MobileStickyCTA() {
  const [visible, setVisible] = useState(false);
  const [hiddenByFlow, setHiddenByFlow] = useState(false);

  useEffect(() => {
    let ticking = false;

    const update = () => {
      const y = window.scrollY || 0;
      const vh = window.innerHeight || 800;
      // Show after ~60% of first viewport; hide near footer
      const nearFooter =
        document.documentElement.scrollHeight - (y + vh) < 280;
      setVisible(y > vh * 0.55 && !nearFooter);

      const config = document.getElementById("configuratore");
      const gate = document.querySelector(
        '[data-testid="gate-submit"]',
      )?.closest("section");
      const inConfig =
        config &&
        y + vh * 0.35 > config.offsetTop &&
        y < config.offsetTop + config.offsetHeight * 0.85;
      const inGate =
        gate &&
        y + vh * 0.35 > gate.offsetTop &&
        y < gate.offsetTop + gate.offsetHeight;
      setHiddenByFlow(Boolean(inConfig || inGate));
      ticking = false;
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  const show = visible && !hiddenByFlow;

  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-40 md:hidden transition-transform duration-300 ease-out ${
        show ? "translate-y-0" : "translate-y-full"
      }`}
      style={{
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
      aria-hidden={!show}
    >
      <div className="border-t border-white/10 bg-bg/95 px-3 py-2.5 shadow-[0_-12px_40px_rgba(0,0,0,0.45)] backdrop-blur-md">
        <div className="mx-auto flex max-w-lg items-center gap-2">
          <a
            href={`${WHATSAPP}?text=${encodeURIComponent(
              "Ciao GB Construction, vorrei info sulla ristrutturazione.",
            )}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-stroke bg-surface text-ink touch-manipulation active:scale-95"
            aria-label="Scrivi su WhatsApp"
            tabIndex={show ? 0 : -1}
          >
            <MessageCircle className="h-5 w-5" aria-hidden />
          </a>
          <button
            type="button"
            data-testid="mobile-sticky-stima"
            onClick={() =>
              scheduleSmoothScrollToElement(
                document.getElementById("configuratore"),
              )
            }
            className="inline-flex h-12 min-h-12 flex-1 items-center justify-center gap-2 rounded-full bg-brand px-4 font-display text-sm font-semibold uppercase tracking-wider text-white touch-manipulation active:scale-[0.98]"
            style={{ boxShadow: "0 8px 28px rgba(198,40,40,0.35)" }}
            tabIndex={show ? 0 : -1}
          >
            Stima gratuita
            <ArrowRight className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
