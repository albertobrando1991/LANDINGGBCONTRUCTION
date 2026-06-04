const EASE_OUT_CUBIC = (t) => 1 - Math.pow(1 - t, 3);

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

function supportsNativeSmoothScroll() {
  return (
    typeof document !== "undefined" &&
    "scrollBehavior" in document.documentElement.style
  );
}

function animateScrollTo(top, duration = 520) {
  const start = window.scrollY || window.pageYOffset;
  const distance = top - start;
  const startedAt = performance.now();

  const step = (now) => {
    const progress = Math.min((now - startedAt) / duration, 1);
    window.scrollTo(0, Math.round(start + distance * EASE_OUT_CUBIC(progress)));
    if (progress < 1) requestAnimationFrame(step);
  };

  requestAnimationFrame(step);
}

export function smoothScrollToElement(target, options = {}) {
  if (typeof window === "undefined" || !target) return;

  const { offset = getFixedNavOffset(), behavior = "smooth" } = options;
  const targetTop = Math.max(
    0,
    Math.round(target.getBoundingClientRect().top + window.scrollY - offset),
  );
  const resolvedBehavior = prefersReducedMotion() ? "auto" : behavior;

  if (resolvedBehavior === "smooth" && !supportsNativeSmoothScroll()) {
    animateScrollTo(targetTop);
    return;
  }

  window.scrollTo({ top: targetTop, behavior: resolvedBehavior });
}

export function scheduleSmoothScrollToElement(target, options = {}) {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => smoothScrollToElement(target, options));
  });
}
