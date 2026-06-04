import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const WORDS = ["Progettiamo", "Costruiamo", "Trasformiamo"];

export default function LoadingScreen({ onDone }) {
  const [count, setCount] = useState(0);
  const [wordIdx, setWordIdx] = useState(0);
  const [hide, setHide] = useState(false);
  const raf = useRef(null);

  useEffect(() => {
    const root = document.documentElement;
    const previousScrollBehavior = root.style.scrollBehavior;

    root.classList.add("is-scroll-locked");
    root.style.scrollBehavior = "auto";
    window.scrollTo(0, 0);

    return () => {
      root.classList.remove("is-scroll-locked");
      root.style.scrollBehavior = previousScrollBehavior;
    };
  }, []);

  useEffect(() => {
    const start = performance.now();
    const duration = 2200;
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      setCount(Math.floor(p * 100));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    // Safety fallback: force completion if rAF gets throttled (background tab)
    const fallback = setTimeout(() => setCount(100), 2800);
    return () => {
      cancelAnimationFrame(raf.current);
      clearTimeout(fallback);
    };
  }, []);

  useEffect(() => {
    const id = setInterval(
      () => setWordIdx((i) => (i + 1) % WORDS.length),
      900,
    );
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (count >= 100) {
      const t = setTimeout(() => {
        setHide(true);
        setTimeout(onDone, 600);
      }, 400);
      return () => clearTimeout(t);
    }
  }, [count, onDone]);

  return (
    <AnimatePresence>
      {!hide && (
        <motion.div
          data-testid="loading-screen"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
          className="fixed inset-0 z-[9999] bg-bg overflow-hidden"
        >
          <div className="absolute top-6 left-6 font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand">
            GB CONSTRUCTION S.R.L.
          </div>

          <div className="absolute inset-0 flex items-center justify-center">
            <AnimatePresence mode="wait">
              <motion.h1
                key={wordIdx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.4 }}
                className="font-display font-bold uppercase text-6xl md:text-8xl lg:text-9xl text-ink/85 tracking-tight"
              >
                {WORDS[wordIdx]}
              </motion.h1>
            </AnimatePresence>
          </div>

          <div className="absolute bottom-10 right-6 font-display font-bold tabular-nums text-7xl md:text-9xl text-ink leading-none">
            {String(count).padStart(3, "0")}
          </div>

          <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-stroke/50">
            <div
              className="h-full accent-gradient origin-left transition-transform duration-150"
              style={{
                transform: `scaleX(${count / 100})`,
                boxShadow: "0 0 12px rgba(198,40,40,0.4)",
              }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
