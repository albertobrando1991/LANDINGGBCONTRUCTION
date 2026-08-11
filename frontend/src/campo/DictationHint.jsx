import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { toast } from "sonner";

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

  const toggle = async () => {
    if (listening) {
      recognitionRef.current?.stop?.();
      return;
    }
    if (!Recognition) {
      toast.error("Dettatura non supportata da questo browser", {
        description: "Usa Chrome o Edge, oppure il microfono della tastiera.",
      });
      return;
    }
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        stream.getTracks().forEach((track) => track.stop());
      }
    } catch (error) {
      toast.error("Accesso al microfono non consentito", {
        description:
          "Abilita il microfono nelle autorizzazioni del browser e riprova.",
      });
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "it-IT";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => setListening(true);
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onerror = (event) => {
      setListening(false);
      recognitionRef.current = null;
      const denied = ["not-allowed", "service-not-allowed"].includes(
        event?.error,
      );
      toast.error(
        denied ? "Microfono non autorizzato" : "Dettatura interrotta",
        {
          description: denied
            ? "Consenti l'uso del microfono nelle impostazioni del browser."
            : "Riprova parlando dopo l'attivazione del microfono.",
        },
      );
    };
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results || [])
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      if (transcript) onChange([value, transcript].filter(Boolean).join(" "));
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (error) {
      recognitionRef.current = null;
      setListening(false);
      toast.error("Impossibile avviare la dettatura");
    }
  };

  return (
    <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-fog">
      <span>Puoi dettare le note con il microfono della tastiera.</span>
      {!disabled && (
        <button
          type="button"
          onClick={() => void toggle()}
          aria-pressed={listening}
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
