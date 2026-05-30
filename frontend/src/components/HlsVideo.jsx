import { useEffect, useRef } from "react";
import Hls from "hls.js";

/**
 * Video di background con supporto HLS (hls.js) + fallback nativo.
 * - .m3u8 → usa hls.js, oppure HLS nativo (Safari) se disponibile.
 * - .mp4/.webm → sorgente diretta.
 */
export default function HlsVideo({ src, className = "", poster, ...rest }) {
  const ref = useRef(null);

  useEffect(() => {
    const video = ref.current;
    if (!video || !src) return undefined;

    const isHls = src.includes(".m3u8");
    if (!isHls) {
      video.src = src;
      return undefined;
    }

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // HLS nativo (Safari / iOS)
      video.src = src;
      return undefined;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true, lowLatencyMode: false });
      hls.loadSource(src);
      hls.attachMedia(video);
      return () => hls.destroy();
    }

    // Fallback finale
    video.src = src;
    return undefined;
  }, [src]);

  return (
    <video
      ref={ref}
      className={className}
      poster={poster}
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      {...rest}
    />
  );
}
