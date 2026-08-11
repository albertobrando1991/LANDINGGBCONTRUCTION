const defaultRaf = (callback) =>
  typeof requestAnimationFrame === "function"
    ? requestAnimationFrame(callback)
    : setTimeout(callback, 16);

const defaultCaf = (frame) =>
  typeof cancelAnimationFrame === "function"
    ? cancelAnimationFrame(frame)
    : clearTimeout(frame);

export function createRafScheduler(draw, raf = defaultRaf, caf = defaultCaf) {
  let frame = null;

  return {
    schedule() {
      if (frame != null) return;
      frame = raf(() => {
        frame = null;
        draw();
      });
    },
    cancel() {
      if (frame == null) return;
      caf(frame);
      frame = null;
    },
  };
}
