import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Circle,
  Loader2,
  Save,
  Type,
  Undo2,
  X,
} from "lucide-react";

function drawArrow(context, annotation) {
  const { x1, y1, x2, y2 } = annotation;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = Math.max(18, context.canvas.width * 0.025);
  context.beginPath();
  context.moveTo(x1, y1);
  context.lineTo(x2, y2);
  context.lineTo(
    x2 - head * Math.cos(angle - Math.PI / 6),
    y2 - head * Math.sin(angle - Math.PI / 6),
  );
  context.moveTo(x2, y2);
  context.lineTo(
    x2 - head * Math.cos(angle + Math.PI / 6),
    y2 - head * Math.sin(angle + Math.PI / 6),
  );
  context.stroke();
}

function drawAnnotation(context, annotation) {
  context.save();
  context.strokeStyle = "#ef4444";
  context.fillStyle = "#ef4444";
  context.lineWidth = Math.max(5, context.canvas.width * 0.006);
  context.lineCap = "round";
  context.lineJoin = "round";
  if (annotation.type === "arrow") drawArrow(context, annotation);
  if (annotation.type === "circle") {
    const centerX = (annotation.x1 + annotation.x2) / 2;
    const centerY = (annotation.y1 + annotation.y2) / 2;
    context.beginPath();
    context.ellipse(
      centerX,
      centerY,
      Math.abs(annotation.x2 - annotation.x1) / 2,
      Math.abs(annotation.y2 - annotation.y1) / 2,
      0,
      0,
      Math.PI * 2,
    );
    context.stroke();
  }
  if (annotation.type === "text") {
    const fontSize = Math.max(24, context.canvas.width * 0.04);
    context.font = `700 ${fontSize}px Arial`;
    const width = context.measureText(annotation.text).width;
    context.fillStyle = "rgba(255,255,255,.88)";
    context.fillRect(
      annotation.x - 6,
      annotation.y - fontSize,
      width + 12,
      fontSize + 10,
    );
    context.fillStyle = "#dc2626";
    context.fillText(annotation.text, annotation.x, annotation.y);
  }
  context.restore();
}

export default function PhotoAnnotatorModal({ photo, onClose, onSave }) {
  const canvasRef = useRef(null);
  const startRef = useRef(null);
  const [image, setImage] = useState(null);
  const [tool, setTool] = useState("arrow");
  const [text, setText] = useState("Crepa");
  const [annotations, setAnnotations] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!photo?.blob) return undefined;
    const url = URL.createObjectURL(photo.blob);
    const nextImage = new Image();
    nextImage.onload = () => setImage(nextImage);
    nextImage.onerror = () => setError("La foto non può essere aperta.");
    nextImage.src = url;
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;
    canvas.width = image.naturalWidth || image.width;
    canvas.height = image.naturalHeight || image.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    annotations.forEach((annotation) => drawAnnotation(context, annotation));
  }, [annotations, image]);

  if (!photo) return null;

  const canvasPoint = (event) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const pointerDown = (event) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const point = canvasPoint(event);
    if (tool === "text") {
      if (text.trim()) {
        setAnnotations((items) => [
          ...items,
          { type: "text", x: point.x, y: point.y, text: text.trim() },
        ]);
      }
      return;
    }
    startRef.current = point;
  };

  const pointerUp = (event) => {
    if (!startRef.current || tool === "text") return;
    const end = canvasPoint(event);
    const start = startRef.current;
    startRef.current = null;
    if (Math.hypot(end.x - start.x, end.y - start.y) < 8) return;
    setAnnotations((items) => [
      ...items,
      { type: tool, x1: start.x, y1: start.y, x2: end.x, y2: end.y },
    ]);
  };

  const save = async () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setSaving(true);
    setError("");
    try {
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
          (result) =>
            result
              ? resolve(result)
              : reject(new Error("Annotazione non salvata.")),
          "image/jpeg",
          0.9,
        );
      });
      const file = new File([blob], photo.name || `foto-${photo.id}.jpg`, {
        type: "image/jpeg",
        lastModified: Date.now(),
      });
      onSave({
        ...photo,
        blob: file,
        size: file.size,
        type: "image/jpeg",
        annotated: true,
      });
    } catch (saveError) {
      setError(saveError?.message || "Annotazione non salvata.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Annota foto"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-3"
    >
      <section className="flex max-h-[96vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-stroke bg-surface p-3 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-display text-lg uppercase text-ink">
              Evidenzia sulla foto
            </h3>
            <p className="text-xs text-fog">
              Frecce, cerchi e testo verranno incorporati definitivamente nel
              JPEG prima del salvataggio offline.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Chiudi annotatore"
          >
            <X className="h-5 w-5 text-fog" />
          </button>
        </div>

        <div className="my-3 flex flex-wrap items-center gap-2">
          {[
            ["arrow", "Freccia", ArrowUpRight],
            ["circle", "Cerchio", Circle],
            ["text", "Testo", Type],
          ].map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTool(id)}
              className={`inline-flex min-h-11 items-center gap-2 rounded-xl border px-3 text-xs uppercase ${tool === id ? "border-brand bg-brand/10 text-brand" : "border-stroke text-fog"}`}
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
          {tool === "text" && (
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="min-h-11 min-w-44 rounded-xl border border-stroke bg-bg px-3 text-sm text-ink"
              placeholder="Testo annotazione"
            />
          )}
          <button
            type="button"
            disabled={!annotations.length}
            onClick={() => setAnnotations((items) => items.slice(0, -1))}
            className="ml-auto inline-flex min-h-11 items-center gap-2 rounded-xl border border-stroke px-3 text-xs uppercase text-fog disabled:opacity-30"
          >
            <Undo2 className="h-4 w-4" /> Annulla segno
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded-xl bg-black/40 text-center">
          <canvas
            ref={canvasRef}
            className="mx-auto block max-h-[64vh] max-w-full touch-none"
            onPointerDown={pointerDown}
            onPointerUp={pointerUp}
            onPointerCancel={() => {
              startRef.current = null;
            }}
          />
        </div>

        <div className="mt-3 flex justify-end gap-2">
          {error && (
            <p className="mr-auto self-center text-xs text-red-400">{error}</p>
          )}
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded-xl border border-stroke px-4 text-xs uppercase text-fog"
          >
            Annulla
          </button>
          <button
            type="button"
            disabled={saving || !image}
            onClick={() => void save()}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 text-xs uppercase text-white disabled:opacity-40"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Salva foto annotata
          </button>
        </div>
      </section>
    </div>
  );
}
