import { useEffect, useRef } from "react";

/**
 * Card con effetto 3D coerente con la hero immersiva:
 * parallasse mouse (rotateX/rotateY) con smoothing lerp + glare luminoso.
 */
export default function Tilt3D({ children, className = "", max = 12, scale = 1.03, glare = true, radius = "rounded-2xl" }) {
  const inner = useRef(null);
  const glareRef = useRef(null);
  const target = useRef({ rx: 0, ry: 0, gx: 50, gy: 50, s: 1, go: 0 });
  const cur = useRef({ rx: 0, ry: 0, gx: 50, gy: 50, s: 1, go: 0 });
  const raf = useRef(null);
  const active = useRef(false);
  const motionDisabled = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointerQuery = window.matchMedia("(pointer: coarse)");
    const updateMotionPreference = () => {
      motionDisabled.current = motionQuery.matches || pointerQuery.matches;
      if (motionDisabled.current) {
        active.current = false;
        reset();
        if (raf.current) {
          cancelAnimationFrame(raf.current);
          raf.current = null;
        }
        if (inner.current) inner.current.style.transform = "none";
        if (glareRef.current) glareRef.current.style.opacity = "0";
      }
    };

    updateMotionPreference();
    motionQuery.addEventListener?.("change", updateMotionPreference);
    pointerQuery.addEventListener?.("change", updateMotionPreference);

    return () => {
      motionQuery.removeEventListener?.("change", updateMotionPreference);
      pointerQuery.removeEventListener?.("change", updateMotionPreference);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, []);

  function animate() {
    if (motionDisabled.current) {
      raf.current = null;
      return;
    }

    const c = cur.current;
    const t = target.current;
    c.rx += (t.rx - c.rx) * 0.12;
    c.ry += (t.ry - c.ry) * 0.12;
    c.gx += (t.gx - c.gx) * 0.12;
    c.gy += (t.gy - c.gy) * 0.12;
    c.s += (t.s - c.s) * 0.12;
    c.go += (t.go - c.go) * 0.12;

    if (inner.current) {
      inner.current.style.transform = `rotateX(${c.rx.toFixed(2)}deg) rotateY(${c.ry.toFixed(2)}deg) scale(${c.s.toFixed(3)})`;
    }
    if (glareRef.current) {
      glareRef.current.style.opacity = c.go.toFixed(2);
      glareRef.current.style.background = `radial-gradient(circle at ${c.gx}% ${c.gy}%, rgba(255,255,255,0.22), transparent 55%)`;
    }

    const delta = Math.max(
      Math.abs(t.rx - c.rx),
      Math.abs(t.ry - c.ry),
      Math.abs(t.gx - c.gx) * 0.02,
      Math.abs(t.gy - c.gy) * 0.02,
      Math.abs(t.s - c.s) * 10,
      Math.abs(t.go - c.go)
    );

    if (!active.current && delta < 0.01) {
      raf.current = null;
      return;
    }

    raf.current = requestAnimationFrame(animate);
  }

  function startLoop() {
    if (!motionDisabled.current && !raf.current) {
      raf.current = requestAnimationFrame(animate);
    }
  }

  function reset() {
    target.current.rx = 0;
    target.current.ry = 0;
    target.current.s = 1;
    target.current.go = 0;
    target.current.gx = 50;
    target.current.gy = 50;
  }

  const onMove = (e) => {
    if (motionDisabled.current) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    active.current = true;
    target.current.ry = (px - 0.5) * max * 2;
    target.current.rx = (0.5 - py) * max * 2;
    target.current.gx = px * 100;
    target.current.gy = py * 100;
    target.current.s = scale;
    target.current.go = 1;
    startLoop();
  };
  const onLeave = () => {
    active.current = false;
    reset();
    startLoop();
  };

  return (
    <div className={className} style={{ perspective: "1000px" }} onMouseMove={onMove} onMouseLeave={onLeave}>
      <div
        ref={inner}
        className={`relative ${radius} overflow-hidden will-change-transform`}
        style={{ transformStyle: "preserve-3d", transition: "transform 0.05s linear" }}
      >
        {children}
        {glare && <div ref={glareRef} className={`absolute inset-0 pointer-events-none ${radius}`} style={{ opacity: 0, mixBlendMode: "overlay" }} />}
      </div>
    </div>
  );
}
