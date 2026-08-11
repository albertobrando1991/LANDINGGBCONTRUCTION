import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";

export default function DictationHint({ value, onChange, disabled = false }) {
  const recognitionRef = useRef(null);
  const [listening, setListening] = useState(false);
  const Recognition =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  useEffect(
    () => () => {
      recognitionRef.current?.abort?.();
    },
    [],
  );

  const toggle = () => {
    if (listening) {
      recognitionRef.current?.stop?.();
      return;
    }
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = "it-IT";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => setListening(true);
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onerror = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results || [])
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      if (transcript) onChange([value, transcript].filter(Boolean).join(" "));
    };
    recognitionRef.current = recognition;
    recognition.start();
  };

  return (
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-fog">
      <span>Puoi dettare le note con il microfono della tastiera.</span>
      {Recognition && !disabled && (
        <button
          type="button"
          onClick={toggle}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-brand/40 px-3 uppercase text-brand"
        >
          {listening ? (
            <Square className="h-3.5 w-3.5" />
          ) : (
            <Mic className="h-3.5 w-3.5" />
          )}
          {listening ? "Ferma" : "Detta"}
        </button>
      )}
    </div>
  );
}
