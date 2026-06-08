import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, ChevronDown } from "lucide-react";
import { ASSETS } from "@/lib/assets";
import { scheduleSmoothScrollToElement } from "@/lib/scroll";

gsap.registerPlugin(ScrollTrigger);
ScrollTrigger.config({ ignoreMobileResize: true });

const TOTAL_FRAMES = 190;
const FINAL_FRAME_HOLD_START = 0.91;
const SCENE_MARKER_POINTS = [0, 0.24, 0.46, 0.68, FINAL_FRAME_HOLD_START, 1];
const OVERLAY_ENTER_DURATION = 0.055;
const OVERLAY_WORD_DURATION = 0.085;
const OVERLAY_EXIT_DURATION = 0.055;
const PUBLIC_MEDIA_BASE = `${process.env.PUBLIC_URL || ""}/cantieri`;
const PLANIMETRIA_OVERLAY_SRC = `${PUBLIC_MEDIA_BASE}/planimetria-napoli-overlay.png`;

const STORY_OVERLAYS = [
  {
    key: "potential",
    start: 0.05,
    exit: 0.235,
    placement:
      "items-start justify-center text-center pt-[13svh] px-5 md:pt-[16vh] md:px-6",
    eyebrow: "GB Construction",
    lines: ["Ristrutturiamo il potenziale", "della tua casa"],
  },
  {
    key: "analysis",
    start: 0.245,
    exit: 0.445,
    placement:
      "items-end justify-start text-left pb-[17svh] px-5 md:pb-[16vh] md:pl-[8vw] md:pr-6",
    eyebrow: "Analisi tecnica",
    lines: ["Prima di costruire,", "analizziamo ogni spazio."],
  },
  {
    key: "layout",
    start: 0.47,
    exit: 0.685,
    placement:
      "items-end justify-center text-center pb-[11svh] px-5 md:items-center md:justify-end md:text-right md:pb-0 md:pr-[8vw] md:pl-6",
    eyebrow: "Nuova distribuzione",
    lines: ["Proporzioni, luce,", "funzione per ogni metro."],
  },
  {
    key: "site",
    start: 0.705,
    exit: 0.895,
    placement:
      "items-end justify-start text-left pb-[17svh] px-5 md:items-center md:pb-0 md:pl-[8vw] md:pr-6",
    eyebrow: "Cantiere organizzato",
    lines: ["Metodo, materiali,", "dettagli sotto controllo."],
  },
];

const PLAN_DETAILS = [
  "Progetto architettonico reale",
  "Distribuzione ambienti",
  "Arredi e impianti",
  "Quote e aperture",
];

const padFrame = (frame) => String(frame).padStart(4, "0");

function splitWords(lines) {
  return lines.map((line) => line.split(" ").filter(Boolean));
}

function createFrameSources({ basePath, step, preferPngEndpoints = true }) {
  const frames = [];

  for (let frame = 1; frame <= TOTAL_FRAMES; frame += step) {
    if (frame === 1) {
      const fallbackUrl = `${basePath}/frame_0001.jpg`;
      frames.push({
        number: frame,
        url: preferPngEndpoints ? `${basePath}/frame_start.png` : fallbackUrl,
        fallbackUrl,
      });
      continue;
    }

    if (frame === TOTAL_FRAMES) {
      const fallbackUrl = `${basePath}/frame_${padFrame(TOTAL_FRAMES)}.jpg`;
      frames.push({
        number: frame,
        url: preferPngEndpoints ? `${basePath}/frame_final.png` : fallbackUrl,
        fallbackUrl,
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
    const fallbackUrl = `${basePath}/frame_${padFrame(TOTAL_FRAMES)}.jpg`;
    frames.push({
      number: TOTAL_FRAMES,
      url: preferPngEndpoints ? `${basePath}/frame_final.png` : fallbackUrl,
      fallbackUrl,
    });
  }

  return frames;
}

function isMobileScrollViewport() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(max-width: 768px), (pointer: coarse)").matches
  );
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
  const prefersReducedMotion = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  const frameSettings = useMemo(() => {
    const isMobile = isMobileScrollViewport();

    return isMobile
      ? {
          basePath: `${PUBLIC_MEDIA_BASE}/frames_heron_mobile`,
          step: 2,
          preferPngEndpoints: false,
          dprCap: 1.7,
          initialBuffer: 14,
          prefetchRadius: 5,
          maxDecodedFrames: 16,
          scrub: 0.35,
        }
      : {
          basePath: `${PUBLIC_MEDIA_BASE}/frames_heron_uhd`,
          step: 1,
          preferPngEndpoints: true,
          dprCap: 2,
          initialBuffer: 10,
          prefetchRadius: 4,
          maxDecodedFrames: 14,
          scrub: 1.15,
        };
  }, []);

  const frameSources = useMemo(
    () => createFrameSources(frameSettings),
    [frameSettings],
  );
  const [loadProgress, setLoadProgress] = useState(0);
  const [firstFrameReady, setFirstFrameReady] = useState(false);
  const [initialBufferReady, setInitialBufferReady] = useState(false);

  const wrapRef = useRef(null);
  const pinRef = useRef(null);
  const canvasRef = useRef(null);
  const canvasLayerRef = useRef(null);
  const depthLayerRef = useRef(null);
  const lightSweepRef = useRef(null);
  const planRef = useRef(null);
  const progressRef = useRef(null);
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
  const scheduledFrameRef = useRef(0);
  const scheduledForceRef = useRef(false);
  const drawFrameRafRef = useRef(null);
  const layoutSizeRef = useRef({ width: 0, height: 0 });
  const scrollIdleRef = useRef(null);
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
    [frameSettings.maxDecodedFrames],
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
    [frameSources, trimFrameCache],
  );

  const prefetchAround = useCallback(
    (index) => {
      const order = [index];
      for (
        let offset = 1;
        offset <= frameSettings.prefetchRadius;
        offset += 1
      ) {
        order.push(index + offset, index - offset);
      }

      order.forEach((candidate) => {
        if (candidate >= 0 && candidate < frameSources.length) {
          ensureFrame(candidate);
        }
      });
    },
    [ensureFrame, frameSettings.prefetchRadius, frameSources.length],
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
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(frame, drawX, drawY, drawWidth, drawHeight);
      currentFrameKeyRef.current = frameKey;
    },
    [ensureFrame, frameSources.length, getNearestFrame, prefetchAround],
  );

  const scheduleDrawFrame = useCallback(
    (targetIndex, force = false) => {
      scheduledFrameRef.current = targetIndex;
      scheduledForceRef.current = scheduledForceRef.current || force;

      if (drawFrameRafRef.current) return;

      drawFrameRafRef.current = requestAnimationFrame(() => {
        const nextFrame = scheduledFrameRef.current;
        const shouldForce = scheduledForceRef.current;
        drawFrameRafRef.current = null;
        scheduledForceRef.current = false;
        drawFrame(nextFrame, shouldForce);
      });
    },
    [drawFrame],
  );

  useEffect(() => {
    drawFrameRef.current = scheduleDrawFrame;
  }, [scheduleDrawFrame]);

  useEffect(
    () => () => {
      if (drawFrameRafRef.current) {
        cancelAnimationFrame(drawFrameRafRef.current);
      }
    },
    [],
  );

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = Math.min(window.devicePixelRatio || 1, frameSettings.dprCap);
    const layer = canvasLayerRef.current;
    const pin = pinRef.current;
    const width = Math.round(layer?.clientWidth || window.innerWidth);
    const height = Math.round(
      pin?.clientHeight || layer?.clientHeight || window.innerHeight,
    );
    const ctx = canvas.getContext("2d");

    if (!width || !height) return;

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
        const previous = layoutSizeRef.current;
        resizeCanvas();
        const next = {
          width: Math.round(
            canvasLayerRef.current?.clientWidth || window.innerWidth,
          ),
          height: Math.round(
            pinRef.current?.clientHeight ||
              canvasLayerRef.current?.clientHeight ||
              window.innerHeight,
          ),
        };
        const mobile = isMobileScrollViewport();
        const widthChanged = Math.abs(next.width - previous.width) > 1;
        const heightChanged = Math.abs(next.height - previous.height) > 96;
        layoutSizeRef.current = next;

        if (!mobile || widthChanged || heightChanged) {
          ScrollTrigger.refresh();
        }
      }, 160);
    };

    layoutSizeRef.current = {
      width: Math.round(
        canvasLayerRef.current?.clientWidth || window.innerWidth,
      ),
      height: Math.round(
        pinRef.current?.clientHeight ||
          canvasLayerRef.current?.clientHeight ||
          window.innerHeight,
      ),
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      clearTimeout(resizeTimerRef.current);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, [resizeCanvas]);

  useEffect(() => {
    const onScroll = () => {
      document.documentElement.classList.add("is-touch-scrolling");
      clearTimeout(scrollIdleRef.current);
      scrollIdleRef.current = setTimeout(() => {
        document.documentElement.classList.remove("is-touch-scrolling");
      }, 140);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      clearTimeout(scrollIdleRef.current);
      document.documentElement.classList.remove("is-touch-scrolling");
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const initialIndices = [
      ...Array.from(
        { length: Math.min(frameSettings.initialBuffer, frameSources.length) },
        (_, i) => i,
      ),
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
            setLoadProgress(
              Math.round((completed / initialIndices.length) * 100),
            );
          }
        }),
      ),
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
  }, [
    drawFrame,
    ensureFrame,
    frameSettings.initialBuffer,
    frameSources.length,
  ]);

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
      gsap.set(finalContentRef.current, {
        autoAlpha: 0,
        y: 56,
        filter: "blur(14px)",
      });
      gsap.set(depthLayerRef.current, { autoAlpha: 0.08 });
      gsap.set(lightSweepRef.current, { autoAlpha: 0 });
      gsap.set(planRef.current, {
        autoAlpha: 0,
        y: 24,
        scale: 0.96,
        filter: "blur(10px)",
      });

      const planImage = planRef.current?.querySelector("[data-plan-image]");
      const planScan = planRef.current?.querySelector("[data-plan-scan]");
      const planDetails = planRef.current
        ? gsap.utils.toArray("[data-plan-detail]", planRef.current)
        : [];

      gsap.set(planImage, { "--plan-reveal": "0%" });
      gsap.set(planScan, { xPercent: -115, autoAlpha: 0 });
      gsap.set(planDetails, { autoAlpha: 0, y: 10 });

      const tl = gsap.timeline({
        defaults: { ease: "power3.out" },
        scrollTrigger: {
          trigger: wrapRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: frameSettings.scrub,
          invalidateOnRefresh: true,
          snap: false,
          onUpdate: (self) => {
            const finalVisible = self.progress > FINAL_FRAME_HOLD_START + 0.02;
            if (finalContentRef.current) {
              finalContentRef.current.style.pointerEvents = finalVisible
                ? "auto"
                : "none";
            }
            if (progressRef.current) {
              progressRef.current.style.setProperty(
                "--hero-progress",
                self.progress.toFixed(4),
              );
            }
            scheduleDrawFrame(Math.round(playheadRef.current.frame));
          },
        },
      });

      tl.to(
        playheadRef.current,
        {
          frame: frameSources.length - 1,
          duration: FINAL_FRAME_HOLD_START,
          ease: "none",
          onUpdate: () =>
            scheduleDrawFrame(Math.round(playheadRef.current.frame)),
        },
        0,
      );

      tl.to(
        playheadRef.current,
        {
          frame: frameSources.length - 1,
          duration: 1 - FINAL_FRAME_HOLD_START,
          ease: "none",
          onUpdate: () => scheduleDrawFrame(frameSources.length - 1),
        },
        FINAL_FRAME_HOLD_START,
      );

      tl.to(
        hintRef.current,
        { autoAlpha: 0, y: -18, duration: 0.055, ease: "none" },
        0.055,
      );
      tl.fromTo(
        vignetteRef.current,
        { opacity: 0.38 },
        { opacity: 0.86, duration: 1, ease: "none" },
        0,
      );
      tl.fromTo(
        canvasLayerRef.current,
        { "--hero-scale": 1.015 },
        { "--hero-scale": 1.045, duration: 1, ease: "none" },
        0,
      );
      tl.fromTo(
        depthLayerRef.current,
        { "--depth-x": "-28px", "--depth-y": "18px", autoAlpha: 0.05 },
        {
          "--depth-x": "26px",
          "--depth-y": "-14px",
          autoAlpha: 0.18,
          duration: 1,
          ease: "none",
        },
        0,
      );
      tl.fromTo(
        lightSweepRef.current,
        { xPercent: -140, autoAlpha: 0 },
        { xPercent: 260, autoAlpha: 0.22, duration: 0.42, ease: "none" },
        0.16,
      );
      tl.to(
        lightSweepRef.current,
        { autoAlpha: 0, duration: 0.12, ease: "none" },
        0.62,
      );

      tl.to(
        planRef.current,
        { autoAlpha: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.09 },
        0.34,
      );
      tl.to(
        planImage,
        { "--plan-reveal": "100%", duration: 0.38, ease: "none" },
        0.38,
      );
      tl.to(
        planScan,
        { xPercent: 120, autoAlpha: 0.42, duration: 0.3, ease: "none" },
        0.4,
      );
      tl.to(planScan, { autoAlpha: 0, duration: 0.05, ease: "none" }, 0.7);
      tl.to(
        planDetails,
        { autoAlpha: 1, y: 0, stagger: 0.018, duration: 0.09 },
        0.58,
      );
      tl.to(
        planRef.current,
        {
          autoAlpha: 0,
          y: -18,
          scale: 1.045,
          duration: 0.1,
          ease: "power2.in",
        },
        0.78,
      );

      STORY_OVERLAYS.forEach((overlay) => {
        const overlayEl = wrapRef.current.querySelector(
          `[data-hero-overlay="${overlay.key}"]`,
        );
        const words = overlayEl?.querySelectorAll(".hero-word");
        if (!overlayEl || !words?.length) return;

        tl.to(
          overlayEl,
          { autoAlpha: 1, y: 0, duration: OVERLAY_ENTER_DURATION },
          overlay.start,
        );
        tl.to(
          words,
          {
            autoAlpha: 1,
            y: 0,
            filter: "blur(0px)",
            stagger: 0.006,
            duration: OVERLAY_WORD_DURATION,
          },
          overlay.start + 0.018,
        );
        tl.to(
          overlayEl,
          {
            autoAlpha: 0,
            y: -18,
            duration: OVERLAY_EXIT_DURATION,
            ease: "power2.in",
          },
          overlay.exit,
        );
      });

      const finalWords =
        finalContentRef.current?.querySelectorAll(".hero-word");
      tl.to(
        finalContentRef.current,
        { autoAlpha: 1, y: 0, filter: "blur(0px)", duration: 0.08 },
        FINAL_FRAME_HOLD_START + 0.012,
      );
      if (finalWords?.length) {
        tl.to(
          finalWords,
          {
            autoAlpha: 1,
            y: 0,
            filter: "blur(0px)",
            stagger: 0.006,
            duration: 0.065,
          },
          FINAL_FRAME_HOLD_START + 0.022,
        );
      }
    }, wrapRef);

    const refresh = setTimeout(() => ScrollTrigger.refresh(), 400);
    return () => {
      clearTimeout(refresh);
      ctx.revert();
    };
  }, [drawFrame, frameSettings.scrub, frameSources.length, scheduleDrawFrame]);

  useEffect(() => {
    if (prefersReducedMotion) return undefined;
    // Pointer parallax non serve su touch: mousemove non scatta comunque.
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(pointer: coarse)").matches
    ) {
      return undefined;
    }

    let raf = null;
    // Quando la hero esce dal viewport il loop deve fermarsi: altrimenti
    // continua a scrivere CSS vars su tutta la pagina e blocca i click piu in basso.
    let heroVisible = true;

    const applyVars = (x, y) => {
      if (canvasLayerRef.current) {
        canvasLayerRef.current.style.setProperty("--hero-px", `${x * -14}px`);
        canvasLayerRef.current.style.setProperty("--hero-py", `${y * -10}px`);
      }
      if (depthLayerRef.current) {
        depthLayerRef.current.style.setProperty("--depth-mouse-x", `${x * 18}px`);
        depthLayerRef.current.style.setProperty("--depth-mouse-y", `${y * 12}px`);
      }
      if (finalParallaxRef.current) {
        finalParallaxRef.current.style.setProperty("--hero-text-px", `${x * 10}px`);
        finalParallaxRef.current.style.setProperty("--hero-text-py", `${y * 7}px`);
      }
    };

    const settled = () =>
      Math.abs(mouseRef.current.x - currentMouseRef.current.x) < 0.001 &&
      Math.abs(mouseRef.current.y - currentMouseRef.current.y) < 0.001;

    const loop = () => {
      currentMouseRef.current.x +=
        (mouseRef.current.x - currentMouseRef.current.x) * 0.055;
      currentMouseRef.current.y +=
        (mouseRef.current.y - currentMouseRef.current.y) * 0.055;

      applyVars(currentMouseRef.current.x, currentMouseRef.current.y);

      // Stop quando i valori sono fermi o la hero non e visibile.
      if (!heroVisible || settled()) {
        raf = null;
        return;
      }
      raf = requestAnimationFrame(loop);
    };

    const startLoop = () => {
      if (!raf && heroVisible) raf = requestAnimationFrame(loop);
    };

    const onMove = (event) => {
      if (!heroVisible) return;
      mouseRef.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
      startLoop();
    };

    let observer;
    const pin = pinRef.current;
    if (pin && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(
        ([entry]) => {
          heroVisible = entry.isIntersecting;
          if (heroVisible) startLoop();
        },
        { threshold: 0 },
      );
      observer.observe(pin);
    }

    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (observer) observer.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [prefersReducedMotion]);

  useEffect(() => {
    if (!initialBufferReady || !loadingRef.current) return;
    drawFrame(Math.round(playheadRef.current.frame), true);
    gsap.to(loadingRef.current, {
      autoAlpha: 0,
      duration: 0.45,
      ease: "power2.out",
    });
  }, [drawFrame, initialBufferReady]);

  const scrollToConfig = () =>
    scheduleSmoothScrollToElement(document.getElementById("configuratore"));

  return (
    <section
      id="hero"
      ref={wrapRef}
      className="relative h-[1250svh] bg-bg md:h-[1100vh]"
    >
      <div
        ref={pinRef}
        className="sticky top-0 h-[100svh] overflow-hidden bg-black md:h-screen"
      >
        <div
          ref={canvasLayerRef}
          className="absolute inset-0 will-change-transform"
          style={{
            transform:
              "translate3d(var(--hero-px,0), var(--hero-py,0), 0) scale(var(--hero-scale,1.02))",
          }}
        >
          <canvas
            ref={canvasRef}
            role="img"
            aria-label="Sequenza cinematica di ristrutturazione GB Construction controllata dallo scroll"
            className={`absolute inset-0 h-[100svh] w-screen transition-opacity duration-700 md:h-screen ${
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
        <div
          ref={depthLayerRef}
          className="hero-depth-field absolute inset-0 pointer-events-none"
          aria-hidden
        />
        <div
          ref={lightSweepRef}
          className="hero-light-sweep absolute inset-y-0 -left-1/3 w-1/2 pointer-events-none"
          aria-hidden
        />
        <div className="absolute inset-0 blueprint-grid opacity-[0.045] mix-blend-screen animate-blueprint pointer-events-none" />
        <div
          ref={planRef}
          className="absolute inset-0 z-30 flex items-center justify-center px-4 pointer-events-none sm:px-6 md:px-8"
          aria-hidden
        >
          <div className="floor-plan-board relative w-[min(92vw,440px)] md:w-[min(78vw,980px)]">
            <div className="floor-plan-board-header">
              <span>Progetto architettonico</span>
              <span>Zio Imma Napoli</span>
            </div>
            <div className="floor-plan-image-wrap">
              <img
                src={PLANIMETRIA_OVERLAY_SRC}
                alt=""
                data-plan-image
                className="floor-plan-image"
                loading="eager"
                decoding="async"
              />
              <span data-plan-scan className="floor-plan-scan" />
            </div>
            <div className="floor-plan-board-footer">
              {PLAN_DETAILS.map((detail) => (
                <span key={detail} data-plan-detail>
                  {detail}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div
          ref={vignetteRef}
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse at center, transparent 34%, rgba(0,0,0,0.92) 100%)",
            opacity: 0.4,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-bg via-bg/45 to-transparent pointer-events-none" />
        <div
          ref={progressRef}
          className="hero-progress-rail absolute right-5 top-1/2 z-30 hidden h-52 -translate-y-1/2 md:block pointer-events-none"
          aria-hidden
        >
          <span className="hero-progress-track" />
          <span className="hero-progress-fill" />
          {SCENE_MARKER_POINTS.slice(1, -1).map((point) => (
            <span
              key={point}
              className="hero-progress-tick"
              style={{ top: `${point * 100}%` }}
            />
          ))}
        </div>

        <div
          ref={loadingRef}
          className="absolute inset-0 z-50 bg-bg flex items-center justify-center px-6"
        >
          <div className="w-full max-w-xs text-center">
            <p className="font-display uppercase tracking-[0.32em] text-xs text-brand mb-5">
              GB Construction
            </p>
            <div className="h-[2px] bg-white/[0.12] overflow-hidden rounded-full">
              <div
                className="h-full bg-brand transition-all duration-200"
                style={{
                  width: `${loadProgress}%`,
                  boxShadow: "0 0 18px rgba(198,40,40,0.5)",
                }}
              />
            </div>
            <p className="mt-4 font-display uppercase tracking-[0.24em] text-[10px] text-fog">
              Prepariamo il tuo progetto {loadProgress}%
            </p>
          </div>
        </div>

        <div
          ref={hintRef}
          className="absolute inset-0 z-30 flex flex-col items-center justify-center text-center px-6 pointer-events-none"
        >
          <div className="font-display font-semibold uppercase tracking-[0.18em] md:tracking-[0.3em] text-[10px] md:text-xs text-brand mb-4 max-w-[92vw]">
            GB Construction - Napoli &amp; Campania
          </div>
          <h2 className="font-display font-bold uppercase text-[clamp(2rem,9vw,4.5rem)] md:text-6xl lg:text-7xl text-ink/90 leading-[0.95] max-w-[92vw] md:max-w-3xl">
            <span className="block">Entra nel tuo</span>
            <span className="block text-brand">progetto.</span>
          </h2>
          <div className="mt-10 flex flex-col items-center gap-2">
            <span className="font-display uppercase tracking-[0.3em] text-[10px] text-fog">
              Scorri per trasformare
            </span>
            <ChevronDown className="w-5 h-5 text-brand animate-bounce" />
          </div>
        </div>

        {STORY_OVERLAYS.map((overlay) => (
          <div
            key={overlay.key}
            data-hero-overlay={overlay.key}
            className={`absolute inset-0 z-20 flex ${overlay.placement} pointer-events-none md:z-30`}
          >
            <div className="max-w-[620px]">
              <p className="font-display font-semibold uppercase tracking-[0.28em] text-xs text-brand mb-4">
                {overlay.eyebrow}
              </p>
              <div className="font-display font-bold uppercase text-[clamp(1.75rem,9.6vw,3.25rem)] md:text-[clamp(2.2rem,7vw,6.4rem)] leading-[0.98] md:leading-[0.92] tracking-normal text-ink drop-shadow-[0_20px_60px_rgba(0,0,0,0.55)]">
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
          className="absolute inset-0 z-40 flex items-center justify-center text-center px-5 sm:px-6 pointer-events-none"
        >
          <div
            ref={finalParallaxRef}
            className="max-w-6xl"
            style={{
              transform:
                "translate3d(var(--hero-text-px,0), var(--hero-text-py,0), 0)",
            }}
          >
            <div className="font-display font-semibold uppercase tracking-[0.18em] md:tracking-[0.3em] text-[10px] md:text-xs text-brand mb-6">
              Preventivo smart GB - anteprima reale
            </div>
            <h1 className="font-display font-bold uppercase text-[clamp(2.05rem,9.2vw,3.35rem)] leading-[0.98] tracking-normal text-ink drop-shadow-[0_24px_70px_rgba(0,0,0,0.62)] md:hidden">
              {splitWords(["Questo costa", "ristrutturare", "casa tua."]).map(
                (line, lineIndex, lines) => (
                  <Fragment key={`final-mobile-${lineIndex}`}>
                    <span className="block">
                      {line.map((word, wordIndex) => (
                        <Fragment key={`${word}-${wordIndex}`}>
                          <span
                            className={`hero-word inline-block ${
                              word.toLowerCase().startsWith("ristrutturare")
                                ? "text-brand"
                                : ""
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
                ),
              )}
            </h1>
            <h1 className="hidden font-display font-bold uppercase tracking-normal text-ink drop-shadow-[0_24px_70px_rgba(0,0,0,0.62)] md:block md:text-7xl md:leading-[0.92] lg:text-8xl">
              {splitWords(["Questo costa", "ristrutturare casa tua."]).map(
                (line, lineIndex, lines) => (
                  <Fragment key={`final-${lineIndex}`}>
                    <span className="block">
                      {line.map((word, wordIndex) => (
                        <Fragment key={`${word}-${wordIndex}`}>
                          <span
                            className={`hero-word inline-block ${
                              word.toLowerCase().startsWith("ristrutturare")
                                ? "text-brand"
                                : ""
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
                ),
              )}
            </h1>
            <p
              className="mt-7 font-body text-sm sm:text-base md:text-lg font-semibold text-white/90 max-w-2xl mx-auto"
              style={{ textShadow: "0 8px 28px rgba(0,0,0,0.92)" }}
            >
              <span className="block">
                Compila pochi dati sul tuo immobile.
              </span>
              <span className="block">
                Ricevi una stima personalizzata su 3 livelli, un'anteprima
                visiva del progetto e una proposta di sopralluogo gratuito.
              </span>
            </p>
            <div className="mt-9">
              <button
                data-testid="hero-cta-stima"
                onClick={scrollToConfig}
                className="group bg-brand text-white rounded-full px-7 md:px-12 py-4 md:py-5 text-sm md:text-lg font-display font-semibold uppercase tracking-wider inline-flex items-center gap-3 transition-transform hover:scale-105"
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
