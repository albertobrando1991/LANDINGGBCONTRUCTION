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

export function smoothScrollToElement(target, options = {}) {
  if (typeof window === "undefined" || !target) return;

  const { offset = getFixedNavOffset(), behavior = "smooth" } = options;
  const targetTop = Math.max(
    0,
    Math.round(target.getBoundingClientRect().top + window.scrollY - offset),
  );
  const resolvedBehavior = prefersReducedMotion() ? "auto" : behavior;
  const currentTop = window.scrollY || window.pageYOffset;
  const distance = Math.abs(targetTop - currentTop);
  const longProgrammaticJump =
    distance > Math.max(window.innerHeight * 1.15, 900);
  const useNativeSmooth =
    resolvedBehavior === "smooth" && !isMobileViewport() && !longProgrammaticJump;

  cancelSmoothScroll();
  window.scrollTo({
    top: targetTop,
    behavior: useNativeSmooth ? "smooth" : "auto",
  });
}

export function scheduleSmoothScrollToElement(target, options = {}) {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => smoothScrollToElement(target, options));
  });
}
