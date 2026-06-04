const EASE_OUT_CUBIC = (t) => 1 - Math.pow(1 - t, 3);
let activeScrollRaf = 0;
let activeCleanup = null;

export function getFixedNavOffset() {
  if (typeof window === "undefined") return 88;
  return window.matchMedia("(max-width: 767px)").matches ? 72 : 88;
}

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function isMobileViewport() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(max-width: 767px), (pointer: coarse)").matches
  );
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function durationForDistance(distance) {
  const abs = Math.abs(distance);
  const mobile = isMobileViewport();
  return clamp(
    abs * (mobile ? 0.44 : 0.28),
    mobile ? 480 : 380,
    mobile ? 1250 : 920,
  );
}

export function cancelSmoothScroll() {
  if (activeScrollRaf) {
    cancelAnimationFrame(activeScrollRaf);
    activeScrollRaf = 0;
  }
  if (activeCleanup) {
    activeCleanup();
    activeCleanup = null;
  }
}

function animateScrollTo(top, duration) {
  cancelSmoothScroll();

  const start = window.scrollY || window.pageYOffset;
  const distance = top - start;
  if (Math.abs(distance) < 2) {
    window.scrollTo(0, top);
    return;
  }

  const startedAt = performance.now();
  const root = document.documentElement;
  const resolvedDuration = duration || durationForDistance(distance);

  const cancelOnUserInput = () => cancelSmoothScroll();
  root.classList.add("is-programmatic-scroll");
  window.addEventListener("wheel", cancelOnUserInput, {
    passive: true,
    once: true,
  });
  window.addEventListener("touchstart", cancelOnUserInput, {
    passive: true,
    once: true,
  });

  activeCleanup = () => {
    root.classList.remove("is-programmatic-scroll");
    window.removeEventListener("wheel", cancelOnUserInput);
    window.removeEventListener("touchstart", cancelOnUserInput);
  };

  const step = (now) => {
    const progress = Math.min((now - startedAt) / resolvedDuration, 1);
    window.scrollTo(0, Math.round(start + distance * EASE_OUT_CUBIC(progress)));
    if (progress < 1) {
      activeScrollRaf = requestAnimationFrame(step);
      return;
    }

    activeScrollRaf = 0;
    if (activeCleanup) {
      activeCleanup();
      activeCleanup = null;
    }
  };

  activeScrollRaf = requestAnimationFrame(step);
}

export function smoothScrollToElement(target, options = {}) {
  if (typeof window === "undefined" || !target) return;

  const {
    offset = getFixedNavOffset(),
    behavior = "smooth",
    duration,
  } = options;
  const targetTop = Math.max(
    0,
    Math.round(target.getBoundingClientRect().top + window.scrollY - offset),
  );
  const resolvedBehavior = prefersReducedMotion() ? "auto" : behavior;

  if (resolvedBehavior === "smooth") {
    animateScrollTo(targetTop, duration);
    return;
  }

  cancelSmoothScroll();
  window.scrollTo({ top: targetTop, behavior: "auto" });
}

export function scheduleSmoothScrollToElement(target, options = {}) {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => smoothScrollToElement(target, options));
  });
}
