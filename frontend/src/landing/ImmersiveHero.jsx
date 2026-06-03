import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, ChevronDown } from "lucide-react";
import { ASSETS } from "@/lib/assets";

gsap.registerPlugin(ScrollTrigger);

const TOTAL_FRAMES = 190;
const FINAL_FRAME_HOLD_START = 0.88;
const PUBLIC_MEDIA_BASE = `${process.env.PUBLIC_URL || ""}/cantieri`;

const STORY_OVERLAYS = [
  {
    key: "potential",
    start: 0.05,
    exit: 0.17,
    placement: "items-start justify-center text-center pt-[16vh] px-6",
    eyebrow: "GB Construction",
    lines: ["Ristrutturiamo il potenziale", "della tua casa"],
  },
  {
    key: "analysis",
    start: 0.22,
    exit: 0.34,
    placement: "items-end justify-start text-left pb-[16vh] pl-[8vw] pr-6",
    eyebrow: "Analisi tecnica",
    lines: ["Prima di costruire,", "analizziamo ogni spazio."],
  },
  {
    key: "layout",
    start: 0.42,
    exit: 0.54,
    placement: "items-center justify-end text-right pr-[8vw] pl-6",
    eyebrow: "Nuova distribuzione",
    lines: ["Proporzioni, luce,", "funzione per ogni metro."],
  },
  {
    key: "site",
    start: 0.63,
    exit: 0.75,
    placement: "items-center justify-start text-left pl-[8vw] pr-6",
    eyebrow: "Cantiere organizzato",
    lines: ["Metodo, materiali,", "dettagli sotto controllo."],
  },
];

const padFrame = (frame) => String(frame).padStart(4, "0");

function splitWords(lines) {
  return lines.map((line) => line.split(" ").filter(Boolean));
}

function createFrameSources({ basePath, step }) {
  const frames = [];

  for (let frame = 1; frame <= TOTAL_FRAMES; frame += step) {
    if (frame === 1) {
      frames.push({
        number: frame,
        url: `${basePath}/frame_start.png`,
        fallbackUrl: `${basePath}/frame_0001.jpg`,
      });
      continue;
    }

    if (frame === TOTAL_FRAMES) {
      frames.push({
        number: frame,
        url: `${basePath}/frame_final.png`,
        fallbackUrl: `${basePath}/frame_${padFrame(TOTAL_FRAMES)}.jpg`,
      });
      continue;
    }

    frames.push({
      number: frame,
      url: `${basePath}/frame_${padFrame(frame)}.jpg`,
      fallbackUrl: `${basePath}/frame_${padFrame(frame)}.jpg`,
    });
  }

  if (frames[frames.length - 1]?.number !== TOTAL_FRAMES) {
    frames.push({
      number: TOTAL_FRAMES,
      url: `${basePath}/frame_final.png`,
      fallbackUrl: `${basePath}/frame_${padFrame(TOTAL_FRAMES)}.jpg`,
    });
  }

  return frames;
}

async function loadBitmap(src) {
  if ("createImageBitmap" in window && "fetch" in window) {
    const response = await fetch(src);
    if (!response.ok) throw new Error(`Frame ${src} non disponibile`);
    const blob = await response.blob();
    return createImageBitmap(blob);
  }

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export default function ImmersiveHero() {
  const frameSettings = useMemo(() => {
    const isMobile =
      typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches;

    return isMobile
      ? {
          basePath: `${PUBLIC_MEDIA_BASE}/frames_heron_uhd`,
          step: 2,
          dprCap: 1.5,
          initialBuffer: 8,
          prefetchRadius: 3,
          maxDecodedFrames: 12,
        }
      : {
          basePath: `${PUBLIC_MEDIA_BASE}/frames_heron_uhd`,
          step: 1,
          dprCap: 2,
          initialBuffer: 10,
          prefetchRadius: 4,
          maxDecodedFrames: 14,
        };
  }, []);

  const frameSources = useMemo(() => createFrameSources(frameSettings), [frameSettings]);
  const [loadProgress, setLoadProgress] = useState(0);
  const [firstFrameReady, setFirstFrameReady] = useState(false);
  const [initialBufferReady, setInitialBufferReady] = useState(false);

  const wrapRef = useRef(null);
  const pinRef = useRef(null);
  const canvasRef = useRef(null);
  const canvasLayerRef = useRef(null);
  const loadingRef = useRef(null);
  const hintRef = useRef(null);
  const vignetteRef = useRef(null);
  const finalContentRef = useRef(null);
  const finalParallaxRef = useRef(null);
  const frameCacheRef = useRef(new Map());
  const loadingFramesRef = useRef(new Map());
  const playheadRef = useRef({ frame: 0 });
  const currentFrameKeyRef = useRef("");
  const requestedFrameRef = useRef(0);
  const resizeTimerRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const currentMouseRef = useRef({ x: 0, y: 0 });
  const drawFrameRef = useRef(() => {});

  const getNearestFrame = useCallback((index) => {
    const cache = frameCacheRef.current;
    if (cache.has(index)) return { index, image: cache.get(index).image };

    let nearest = null;
    cache.forEach((value, key) => {
      const distance = Math.abs(key - index);
      if (!nearest || distance < nearest.distance) {
        nearest = { index: key, image: value.image, distance };
      }
    });

    return nearest;
  }, []);

  const trimFrameCache = useCallback(
    (centerIndex) => {
      const cache = frameCacheRef.current;
      const maxFrames = frameSettings.maxDecodedFrames;

      if (cache.size <= maxFrames) return;

      const ordered = [...cache.keys()]
        .filter((key) => key !== centerIndex)
        .sort((a, b) => Math.abs(b - centerIndex) - Math.abs(a - centerIndex));

      while (cache.size > maxFrames && ordered.length) {
        const key = ordered.shift();
        const cached = cache.get(key);
        if (cached?.image?.close) cached.image.close();
        cache.delete(key);
      }
    },
    [frameSettings.maxDecodedFrames]
  );

  const ensureFrame = useCallback(
    (targetIndex) => {
      const index = Math.max(0, Math.min(frameSources.length - 1, targetIndex));
      const cache = frameCacheRef.current;

      if (cache.has(index)) {
        return Promise.resolve(cache.get(index).image);
      }

      if (loadingFramesRef.current.has(index)) {
        return loadingFramesRef.current.get(index);
      }

      const source = frameSources[index];
      const promise = loadBitmap(source.url)
        .catch(() => loadBitmap(source.fallbackUrl))
        .then((image) => {
          frameCacheRef.current.set(index, { image });

          if (index === 0) {
            setFirstFrameReady(true);
          }

          if (requestedFrameRef.current === index) {
            requestAnimationFrame(() => drawFrameRef.current(index, true));
          }

          trimFrameCache(requestedFrameRef.current);
          return image;
        })
        .finally(() => {
          loadingFramesRef.current.delete(index);
        });

      loadingFramesRef.current.set(index, promise);
      return promise;
    },
    [frameSources, trimFrameCache]
  );

  const prefetchAround = useCallback(
    (index) => {
      const order = [index];
      for (let offset = 1; offset <= frameSettings.prefetchRadius; offset += 1) {
        order.push(index + offset, index - offset);
      }

      order.forEach((candidate) => {
        if (candidate >= 0 && candidate < frameSources.length) {
          ensureFrame(candidate);
        }
      });
    },
    [ensureFrame, frameSettings.prefetchRadius, frameSources.length]
  );

  const drawFrame = useCallback(
    (targetIndex, force = false) => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      const index = Math.max(0, Math.min(frameSources.length - 1, targetIndex));
      requestedFrameRef.current = index;

      let frame = frameCacheRef.current.get(index)?.image;
      let frameIndex = index;

      if (!frame) {
        ensureFrame(index);
        const nearest = getNearestFrame(index);
        frame = nearest?.image;
        frameIndex = nearest?.index ?? index;
      }

      prefetchAround(index);

      if (!frame) return;

      const frameKey = `${index}:${frameIndex}`;
      if (!force && currentFrameKeyRef.current === frameKey) return;

      const width = canvas.clientWidth || window.innerWidth;
      const height = canvas.clientHeight || window.innerHeight;
      const frameWidth = frame.width || frame.naturalWidth;
      const frameHeight = frame.height || frame.naturalHeight;
      const scale = Math.max(width / frameWidth, height / frameHeight);
      const drawWidth = frameWidth * scale;
      const drawHeight = frameHeight * scale;
      const drawX = (width - drawWidth) / 2;
      const drawY = (height - drawHeight) / 2;

      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(frame, drawX, drawY, drawWidth, drawHeight);
      currentFrameKeyRef.current = frameKey;
    },
    [ensureFrame, frameSources.length, getNearestFrame, prefetchAround]
  );

  useEffect(() => {
    drawFrameRef.current = drawFrame;
  }, [drawFrame]);

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = Math.min(window.devicePixelRatio || 1, frameSettings.dprCap);
    const width = window.innerWidth;
    const height = window.innerHeight;
    const ctx = canvas.getContext("2d");

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    drawFrame(Math.round(playheadRef.current.frame), true);
  }, [drawFrame, frameSettings.dprCap]);

  useEffect(() => {
    resizeCanvas();

    const onResize = () => {
      clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(() => {
        resizeCanvas();
        ScrollTrigger.refresh();
      }, 160);
    };

    window.addEventListener("resize", onResize);
    return () => {
      clearTimeout(resizeTimerRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [resizeCanvas]);

  useEffect(() => {
    let cancelled = false;
    const initialIndices = [
      ...Array.from({ length: Math.min(frameSettings.initialBuffer, frameSources.length) }, (_, i) => i),
      frameSources.length - 1,
    ].filter((value, index, values) => values.indexOf(value) === index);

    setLoadProgress(0);
    setInitialBufferReady(false);

    let completed = 0;
    Promise.all(
      initialIndices.map((index) =>
        ensureFrame(index).finally(() => {
          completed += 1;
          if (!cancelled) {
            setLoadProgress(Math.round((completed / initialIndices.length) * 100));
          }
        })
      )
    ).then(() => {
      if (!cancelled) {
        setFirstFrameReady(true);
        setInitialBufferReady(true);
        drawFrame(Math.round(playheadRef.current.frame), true);
        ScrollTrigger.refresh();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [drawFrame, ensureFrame, frameSettings.initialBuffer, frameSources.length]);

  useEffect(() => {
    const loadingFrames = loadingFramesRef.current;
    const frameCache = frameCacheRef.current;

    return () => {
      loadingFrames.clear();
      frameCache.forEach((cached) => {
        if (cached?.image?.close) cached.image.close();
      });
      frameCache.clear();
    };
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.set("[data-hero-overlay]", { autoAlpha: 0, y: 24 });
      gsap.set(".hero-word", { autoAlpha: 0, y: 18, filter: "blur(8px)" });
      gsap.set(finalContentRef.current, { autoAlpha: 0, y: 56, filter: "blur(14px)" });

      const tl = gsap.timeline({
        defaults: { ease: "power3.out" },
        scrollTrigger: {
          trigger: wrapRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const finalVisible = self.progress > FINAL_FRAME_HOLD_START + 0.035;
            if (finalContentRef.current) {
              finalContentRef.current.style.pointerEvents = finalVisible ? "auto" : "none";
            }
            drawFrame(Math.round(playheadRef.current.frame));
          },
        },
      });

      tl.to(
        playheadRef.current,
        {
          frame: frameSources.length - 1,
          duration: FINAL_FRAME_HOLD_START,
          ease: "none",
          onUpdate: () => drawFrame(Math.round(playheadRef.current.frame)),
        },
        0
      );

      tl.to(
        playheadRef.current,
        {
          frame: frameSources.length - 1,
          duration: 1 - FINAL_FRAME_HOLD_START,
          ease: "none",
          onUpdate: () => drawFrame(frameSources.length - 1),
        },
        FINAL_FRAME_HOLD_START
      );

      tl.to(hintRef.current, { autoAlpha: 0, y: -18, duration: 0.055, ease: "none" }, 0.055);
      tl.fromTo(vignetteRef.current, { opacity: 0.38 }, { opacity: 0.86, duration: 1, ease: "none" }, 0);
      tl.fromTo(
        canvasLayerRef.current,
        { "--hero-scale": 1.015 },
        { "--hero-scale": 1.045, duration: 1, ease: "none" },
        0
      );

      STORY_OVERLAYS.forEach((overlay) => {
        const overlayEl = wrapRef.current.querySelector(`[data-hero-overlay="${overlay.key}"]`);
        const words = overlayEl?.querySelectorAll(".hero-word");
        if (!overlayEl || !words?.length) return;

        tl.to(overlayEl, { autoAlpha: 1, y: 0, duration: 0.035 }, overlay.start);
        tl.to(words, { autoAlpha: 1, y: 0, filter: "blur(0px)", stagger: 0.004, duration: 0.05 }, overlay.start + 0.012);
        tl.to(overlayEl, { autoAlpha: 0, y: -18, duration: 0.035, ease: "power2.in" }, overlay.exit);
      });

      const finalWords = finalContentRef.current?.querySelectorAll(".hero-word");
      tl.to(
        finalContentRef.current,
        { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.07 },
        FINAL_FRAME_HOLD_START + 0.025
      );
      if (finalWords?.length) {
        tl.to(
          finalWords,
          { autoAlpha: 1, y: 0, filter: "blur(0px)", stagger: 0.006, duration: 0.045 },
          FINAL_FRAME_HOLD_START + 0.045
        );
      }
    }, wrapRef);

    const refresh = setTimeout(() => ScrollTrigger.refresh(), 400);
    return () => {
      clearTimeout(refresh);
      ctx.revert();
    };
  }, [drawFrame, frameSources.length]);

  useEffect(() => {
    const onMove = (event) => {
      mouseRef.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
    };

    window.addEventListener("mousemove", onMove);
    let raf;

    const loop = () => {
      currentMouseRef.current.x += (mouseRef.current.x - currentMouseRef.current.x) * 0.055;
      currentMouseRef.current.y += (mouseRef.current.y - currentMouseRef.current.y) * 0.055;

      const x = currentMouseRef.current.x;
      const y = currentMouseRef.current.y;

      if (canvasLayerRef.current) {
        canvasLayerRef.current.style.setProperty("--hero-px", `${x * -14}px`);
        canvasLayerRef.current.style.setProperty("--hero-py", `${y * -10}px`);
      }
      if (finalParallaxRef.current) {
        finalParallaxRef.current.style.setProperty("--hero-text-px", `${x * 10}px`);
        finalParallaxRef.current.style.setProperty("--hero-text-py", `${y * 7}px`);
      }

      raf = requestAnimationFrame(loop);
    };

    raf = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    if (!initialBufferReady || !loadingRef.current) return;
    drawFrame(Math.round(playheadRef.current.frame), true);
    gsap.to(loadingRef.current, { autoAlpha: 0, duration: 0.45, ease: "power2.out" });
  }, [drawFrame, initialBufferReady]);

  const scrollToConfig = () =>
    document.getElementById("configuratore")?.scrollIntoView({ behavior: "smooth" });

  return (
    <section id="hero" ref={wrapRef} className="relative h-[800vh] bg-bg">
      <div ref={pinRef} className="sticky top-0 h-screen overflow-hidden bg-black">
        <div
          ref={canvasLayerRef}
          className="absolute inset-0 will-change-transform"
          style={{ transform: "translate3d(var(--hero-px,0), var(--hero-py,0), 0) scale(var(--hero-scale,1.02))" }}
        >
          <canvas
            ref={canvasRef}
            role="img"
            aria-label="Sequenza cinematica di ristrutturazione GB Construction controllata dallo scroll"
            className={`absolute inset-0 h-screen w-screen transition-opacity duration-700 ${
              firstFrameReady ? "opacity-100" : "opacity-0"
            }`}
          />
        </div>

        <div className="absolute inset-0 bg-black/28 pointer-events-none" />
        <img
          src={ASSETS.cemento}
          alt=""
          aria-hidden
          className="absolute inset-0 w-full h-full object-cover opacity-[0.09] mix-blend-overlay pointer-events-none"
        />
        <div className="absolute inset-0 blueprint-grid opacity-[0.045] mix-blend-screen animate-blueprint pointer-events-none" />
        <div
          ref={vignetteRef}
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse at center, transparent 34%, rgba(0,0,0,0.92) 100%)",
            opacity: 0.4,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-bg via-bg/45 to-transparent pointer-events-none" />

        <div ref={loadingRef} className="absolute inset-0 z-20 bg-bg flex items-center justify-center px-6">
          <div className="w-full max-w-xs text-center">
            <p className="font-display uppercase tracking-[0.32em] text-xs text-brand mb-5">GB Construction</p>
            <div className="h-[2px] bg-white/[0.12] overflow-hidden rounded-full">
              <div
                className="h-full bg-brand transition-all duration-200"
                style={{ width: `${loadProgress}%`, boxShadow: "0 0 18px rgba(198,40,40,0.5)" }}
              />
            </div>
            <p className="mt-4 font-display uppercase tracking-[0.24em] text-[10px] text-fog">
              Prepariamo il tuo progetto {loadProgress}%
            </p>
          </div>
        </div>

        <div ref={hintRef} className="absolute inset-0 z-10 flex flex-col items-center justify-center text-center px-6 pointer-events-none">
          <div className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-4">
            GB Construction - Napoli &amp; Campania
          </div>
          <h2 className="font-display font-bold uppercase text-4xl md:text-6xl lg:text-7xl text-ink/90 leading-[0.95] max-w-3xl">
            Entra nel tuo <span className="text-brand">progetto</span>.
          </h2>
          <div className="mt-10 flex flex-col items-center gap-2">
            <span className="font-display uppercase tracking-[0.3em] text-[10px] text-fog">Scorri per trasformare</span>
            <ChevronDown className="w-5 h-5 text-brand animate-bounce" />
          </div>
        </div>

        {STORY_OVERLAYS.map((overlay) => (
          <div
            key={overlay.key}
            data-hero-overlay={overlay.key}
            className={`absolute inset-0 z-10 flex ${overlay.placement} pointer-events-none`}
          >
            <div className="max-w-[620px]">
              <p className="font-display font-semibold uppercase tracking-[0.28em] text-xs text-brand mb-4">
                {overlay.eyebrow}
              </p>
              <div className="font-display font-bold uppercase text-[clamp(2.2rem,7vw,6.4rem)] leading-[0.92] tracking-tight text-ink drop-shadow-[0_20px_60px_rgba(0,0,0,0.55)]">
                {splitWords(overlay.lines).map((line, lineIndex) => (
                  <div key={`${overlay.key}-${lineIndex}`}>
                    {line.map((word, wordIndex) => (
                      <Fragment key={`${word}-${wordIndex}`}>
                        <span className="hero-word inline-block">{word}</span>
                        {wordIndex < line.length - 1 ? " " : ""}
                      </Fragment>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}

        <div
          ref={finalContentRef}
          data-final-hero
          className="absolute inset-0 z-20 flex items-center justify-center text-center px-6 pointer-events-none"
        >
          <div
            ref={finalParallaxRef}
            className="max-w-6xl"
            style={{ transform: "translate3d(var(--hero-text-px,0), var(--hero-text-py,0), 0)" }}
          >
            <div className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-6">
              Preventivo smart GB - anteprima reale
            </div>
            <h1 className="font-display font-bold uppercase text-5xl md:text-7xl lg:text-8xl leading-[0.92] tracking-tight text-ink drop-shadow-[0_24px_70px_rgba(0,0,0,0.62)]">
              {splitWords(["Questo costa", "ristrutturare casa tua."]).map((line, lineIndex, lines) => (
                <Fragment key={`final-${lineIndex}`}>
                  <span className="block">
                    {line.map((word, wordIndex) => (
                      <Fragment key={`${word}-${wordIndex}`}>
                        <span
                          className={`hero-word inline-block ${
                            word.toLowerCase().startsWith("ristrutturare") ? "text-brand" : ""
                          }`}
                        >
                          {word}
                        </span>
                        {wordIndex < line.length - 1 ? " " : ""}
                      </Fragment>
                    ))}
                  </span>
                  {lineIndex < lines.length - 1 ? " " : ""}
                </Fragment>
              ))}
            </h1>
            <p
              className="mt-7 font-body text-base md:text-lg font-semibold text-white/90 max-w-2xl mx-auto"
              style={{ textShadow: "0 8px 28px rgba(0,0,0,0.92)" }}
            >
              <span className="block">Compila pochi dati sul tuo immobile.</span>
              <span className="block">
                Ricevi una stima personalizzata su 3 livelli, un'anteprima visiva del progetto
                e una proposta di sopralluogo gratuito.
              </span>
            </p>
            <div className="mt-9">
              <button
                data-testid="hero-cta-stima"
                onClick={scrollToConfig}
                className="group bg-brand text-white rounded-full px-9 md:px-12 py-4 md:py-5 text-base md:text-lg font-display font-semibold uppercase tracking-wider inline-flex items-center gap-3 transition-transform hover:scale-105"
                style={{ boxShadow: "0 8px 32px rgba(198,40,40,0.35)" }}
              >
                Avvia stima gratuita
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
            <div className="mt-7 font-display font-normal uppercase tracking-[0.2em] text-xs text-fog">
              +200 cantieri - +15 anni in Campania - Sopralluogo sempre gratuito
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
