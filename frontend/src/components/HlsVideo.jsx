import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

/**
 * Video di background con supporto HLS (hls.js) + fallback nativo.
 * - .m3u8 → usa hls.js, oppure HLS nativo (Safari) se disponibile.
 * - .mp4/.webm → sorgente diretta.
 */
export default function HlsVideo({
  src,
  className = "",
  poster,
  autoPlay = true,
  muted = true,
  loop = true,
  playsInline = true,
  preload = "metadata",
  lazy = true,
  onLoadedData,
  onCanPlay,
  ...rest
}) {
  const ref = useRef(null);
  const [isNearViewport, setIsNearViewport] = useState(!lazy);
  const [hasActivated, setHasActivated] = useState(!lazy);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setIsReady(false);
  }, [src]);

  useEffect(() => {
    const video = ref.current;
    if (!video || !lazy) return undefined;

    if (typeof IntersectionObserver === "undefined") {
      setIsNearViewport(true);
      setHasActivated(true);
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        setIsNearViewport(visible);
        if (visible) setHasActivated(true);
      },
      { rootMargin: "260px 0px", threshold: 0.08 },
    );

    observer.observe(video);
    return () => observer.disconnect();
  }, [lazy]);

  useEffect(() => {
    const video = ref.current;
    if (!video || !src || !hasActivated) return undefined;

    const isHls = src.includes(".m3u8");
    if (!isHls) {
      if (video.dataset.sourceUrl !== src) {
        video.dataset.sourceUrl = src;
        video.src = src;
        video.load();
      }
      return undefined;
    }

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // HLS nativo (Safari / iOS)
      if (video.dataset.sourceUrl !== src) {
        video.dataset.sourceUrl = src;
        video.src = src;
        video.load();
      }
      return undefined;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true, lowLatencyMode: false });
      hls.loadSource(src);
      hls.attachMedia(video);
      return () => hls.destroy();
    }

    // Fallback finale
    if (video.dataset.sourceUrl !== src) {
      video.dataset.sourceUrl = src;
      video.src = src;
      video.load();
    }
    return undefined;
  }, [hasActivated, src]);

  useEffect(() => {
    const video = ref.current;
    if (!video || !hasActivated) return;

    if (autoPlay && isNearViewport) {
      const play = video.play();
      if (play?.catch) play.catch(() => {});
      return;
    }

    video.pause();
  }, [autoPlay, hasActivated, isNearViewport]);

  const handleLoadedData = (event) => {
    setIsReady(true);
    onLoadedData?.(event);
  };

  const handleCanPlay = (event) => {
    setIsReady(true);
    onCanPlay?.(event);
  };

  return (
    <video
      ref={ref}
      data-video-ready={isReady ? "true" : "false"}
      className={className}
      poster={poster}
      autoPlay={autoPlay}
      muted={muted}
      loop={loop}
      playsInline={playsInline}
      preload={preload}
      onLoadedData={handleLoadedData}
      onCanPlay={handleCanPlay}
      {...rest}
    />
  );
}
