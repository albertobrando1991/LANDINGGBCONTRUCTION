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

  useEffect(() => {
    const loop = () => {
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
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf.current);
  }, []);

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    target.current.ry = (px - 0.5) * max * 2;
    target.current.rx = (0.5 - py) * max * 2;
    target.current.gx = px * 100;
    target.current.gy = py * 100;
    target.current.s = scale;
    target.current.go = 1;
  };
  const onLeave = () => {
    target.current.rx = 0;
    target.current.ry = 0;
    target.current.s = 1;
    target.current.go = 0;
    target.current.gx = 50;
    target.current.gy = 50;
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
