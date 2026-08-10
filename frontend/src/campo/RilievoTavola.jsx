import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Camera,
  FileUp,
  Loader2,
  MousePointer2,
  Pencil,
  Redo2,
  Ruler,
  Save,
  Square,
  StickyNote,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { formatApiErrorDetail } from "@/lib/api";
import {
  compressCampoPhoto,
  createRilievoPhotoUrls,
  MAX_RILIEVO_GENERAL_PHOTOS,
  uploadRilievoGeneralPhotos,
} from "@/lib/campoPhotos";
import {
  createRilievoPlanPreview,
  createRilievoPlanUrl,
  uploadRilievoPlan,
  validateRilievoPlan,
} from "@/lib/rilievoAssets";
import { saveRilievoTavola } from "@/lib/rilievoApi";
import {
  enqueueRilievoOperation,
  listRilievoOperations,
} from "@/lib/rilievoQueue";
import {
  closestElement,
  metersFor,
  normalizedLength,
  roomMetrics,
} from "./rilievoGeometry";

const TOOLS = [
  { id: "seleziona", label: "Seleziona", Icon: MousePointer2 },
  { id: "muro", label: "Muro", Icon: Pencil },
  { id: "ambiente", label: "Ambiente", Icon: Square },
  { id: "quota", label: "Quota", Icon: Ruler },
  { id: "calibra", label: "Calibra", Icon: Redo2 },
  { id: "nota", label: "Nota", Icon: StickyNote },
];

function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `elemento-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function clamp(value) {
  return Math.max(0, Math.min(1, value));
}

function snap(value) {
  return Math.round(clamp(value) * 100) / 100;
}

function PhotoPreview({ photo, onRemove }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const next = URL.createObjectURL(photo.blob);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [photo.blob]);
  return (
    <div className="relative aspect-square overflow-hidden rounded-xl border border-stroke bg-bg">
      {url && (
        <img
          src={url}
          alt="Foto immobile da salvare"
          className="h-full w-full object-cover"
        />
      )}
      <button
        type="button"
        onClick={onRemove}
        aria-label="Rimuovi foto da salvare"
        className="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-full bg-black/70 text-white"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

function drawArrow(context, start, end) {
  const angle = Math.atan2(end.y - start.y, end.x - start.x);
  for (const point of [start, end]) {
    const reverse = point === start ? 0 : Math.PI;
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineTo(
      point.x + Math.cos(angle + reverse + 0.55) * 9,
      point.y + Math.sin(angle + reverse + 0.55) * 9,
    );
    context.moveTo(point.x, point.y);
    context.lineTo(
      point.x + Math.cos(angle + reverse - 0.55) * 9,
      point.y + Math.sin(angle + reverse - 0.55) * 9,
    );
    context.stroke();
  }
}

function elementLabel(element, calibration, canvasRatio) {
  const meters = element.metri ?? metersFor(element, calibration, canvasRatio);
  if (element.tipo === "quota" && meters != null) {
    return [element.testo, `${meters} m`].filter(Boolean).join(" · ");
  }
  if (element.tipo === "ambiente") {
    const room = roomMetrics(element, calibration, canvasRatio);
    return [
      element.testo || "Ambiente",
      room ? `${room.width}×${room.height} m · ${room.area} mq` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return element.testo || "";
}

export default function RilievoTavola({
  rilievo,
  user,
  slug,
  isOnline,
  locked,
  onSaved,
  onQueueChanged,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const planInputRef = useRef(null);
  const photoInputRef = useRef(null);
  const rilievoRef = useRef(rilievo);
  rilievoRef.current = rilievo;
  const [tool, setTool] = useState("seleziona");
  const [elements, setElements] = useState([]);
  const [history, setHistory] = useState([]);
  const [calibration, setCalibration] = useState(null);
  const [calibrationDraft, setCalibrationDraft] = useState(null);
  const [calibrationMeters, setCalibrationMeters] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState(null);
  const [canvasSize, setCanvasSize] = useState({ width: 900, height: 600 });
  const [asset, setAsset] = useState({
    planimetria_path: null,
    planimetria_preview_path: null,
    planimetria_filename: null,
    planimetria_mime_type: null,
  });
  const [backgroundUrl, setBackgroundUrl] = useState("");
  const [backgroundImage, setBackgroundImage] = useState(null);
  const [pendingPlan, setPendingPlan] = useState(null);
  const [pendingPhotos, setPendingPhotos] = useState([]);
  const [savedPhotos, setSavedPhotos] = useState([]);
  const [photoPaths, setPhotoPaths] = useState([]);
  const [busy, setBusy] = useState(false);
  const [saveState, setSaveState] = useState("salvato");
  const persistedVersion = `${rilievo?.id || ""}:${rilievo?.updated_at || ""}`;

  useEffect(() => {
    const current = rilievoRef.current;
    const data = current?.planimetria_data || {};
    setElements(Array.isArray(data.elementi) ? data.elementi : []);
    setHistory([]);
    setCalibration(data.calibrazione || null);
    setAsset({
      planimetria_path: current?.planimetria_path || null,
      planimetria_preview_path: current?.planimetria_preview_path || null,
      planimetria_filename: current?.planimetria_filename || null,
      planimetria_mime_type: current?.planimetria_mime_type || null,
    });
    setPhotoPaths(current?.foto_paths || []);
    setPendingPlan(null);
    setPendingPhotos([]);
    setSaveState("salvato");
  }, [persistedVersion]);

  useEffect(() => {
    let active = true;
    listRilievoOperations(slug).then((operations) => {
      if (!active) return;
      const queued = operations.find(
        (item) => item.kind === "tavola" && item.rilievo_id === rilievo?.id,
      );
      if (!queued) return;
      setElements(queued.body?.elementi || []);
      setCalibration(queued.body?.calibrazione || null);
      setPhotoPaths(queued.body?.foto_paths || []);
      setPendingPhotos(queued.photos || []);
      setPendingPlan(
        queued.plan_file
          ? {
              file: queued.plan_file,
              previewBlob: queued.plan_preview || queued.plan_file,
            }
          : null,
      );
      setSaveState("in_attesa");
    });
    return () => {
      active = false;
    };
  }, [rilievo?.id, slug]);

  useEffect(() => {
    let active = true;
    let localUrl = "";
    const load = async () => {
      try {
        if (pendingPlan?.previewBlob) {
          localUrl = URL.createObjectURL(pendingPlan.previewBlob);
          if (active) setBackgroundUrl(localUrl);
          return;
        }
        const path = asset.planimetria_preview_path || asset.planimetria_path;
        const url = await createRilievoPlanUrl(path);
        if (active) setBackgroundUrl(url);
      } catch {
        if (active) setBackgroundUrl("");
      }
    };
    void load();
    return () => {
      active = false;
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
  }, [asset.planimetria_path, asset.planimetria_preview_path, pendingPlan]);

  useEffect(() => {
    if (!backgroundUrl) {
      setBackgroundImage(null);
      return undefined;
    }
    const image = new Image();
    image.onload = () => setBackgroundImage(image);
    image.onerror = () => setBackgroundImage(null);
    image.src = backgroundUrl;
    return () => {
      image.onload = null;
      image.onerror = null;
    };
  }, [backgroundUrl]);

  useEffect(() => {
    let active = true;
    createRilievoPhotoUrls(photoPaths)
      .then((items) => active && setSavedPhotos(items))
      .catch(() => active && setSavedPhotos([]));
    return () => {
      active = false;
    };
  }, [photoPaths]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return undefined;
    const update = () => {
      const width = Math.max(300, Math.floor(node.clientWidth));
      const stored = rilievo?.planimetria_data || {};
      const ratio =
        Number(stored.canvas_height || 800) /
        Number(stored.canvas_width || 1200);
      setCanvasSize({
        width,
        height: Math.max(180, Math.min(720, Math.round(width * ratio))),
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [rilievo?.id, rilievo?.planimetria_data]);

  const selected = elements.find((item) => item.id === selectedId);
  const canvasRatio = canvasSize.height / canvasSize.width;

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const { width, height } = canvasSize;
    canvas.width = width;
    canvas.height = height;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#f8f7f3";
    context.fillRect(0, 0, width, height);

    context.strokeStyle = "#e5e1d8";
    context.lineWidth = 1;
    for (let x = 0; x <= width; x += 24) {
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
    }
    for (let y = 0; y <= height; y += 24) {
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }

    if (backgroundImage) {
      const scale = Math.min(
        width / backgroundImage.naturalWidth,
        height / backgroundImage.naturalHeight,
      );
      const imageWidth = backgroundImage.naturalWidth * scale;
      const imageHeight = backgroundImage.naturalHeight * scale;
      context.globalAlpha = 0.78;
      context.drawImage(
        backgroundImage,
        (width - imageWidth) / 2,
        (height - imageHeight) / 2,
        imageWidth,
        imageHeight,
      );
      context.globalAlpha = 1;
    }

    const paint = (element, isDraft = false) => {
      const start = { x: element.x1 * width, y: element.y1 * height };
      const end = { x: element.x2 * width, y: element.y2 * height };
      const active = selectedId === element.id;
      context.save();
      context.strokeStyle = active ? "#f59e0b" : "#b91c1c";
      context.fillStyle = active
        ? "rgba(245,158,11,.18)"
        : "rgba(185,28,28,.10)";
      context.lineWidth = element.tipo === "muro" ? 5 : active ? 3 : 2;
      if (isDraft) context.setLineDash([8, 6]);
      if (element.tipo === "ambiente") {
        context.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
        context.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
      } else if (element.tipo === "nota") {
        context.beginPath();
        context.arc(start.x, start.y, 6, 0, Math.PI * 2);
        context.fillStyle = "#f59e0b";
        context.fill();
      } else {
        context.beginPath();
        context.moveTo(start.x, start.y);
        context.lineTo(end.x, end.y);
        context.stroke();
        if (element.tipo === "quota" || element.tipo === "calibra") {
          drawArrow(context, start, end);
        }
      }
      const label = elementLabel(element, calibration, canvasRatio);
      if (label) {
        const x = (start.x + end.x) / 2;
        const y = (start.y + end.y) / 2;
        context.font = "600 13px Arial";
        const metrics = context.measureText(label);
        context.fillStyle = "rgba(255,255,255,.92)";
        context.fillRect(
          x - metrics.width / 2 - 5,
          y - 18,
          metrics.width + 10,
          22,
        );
        context.fillStyle = "#171717";
        context.fillText(label, x - metrics.width / 2, y - 3);
      }
      context.restore();
    };

    elements.forEach((element) => paint(element));
    if (draft) paint(draft, true);
  }, [
    backgroundImage,
    calibration,
    canvasRatio,
    canvasSize,
    draft,
    elements,
    selectedId,
  ]);

  useEffect(() => drawCanvas(), [drawCanvas]);

  const pointFromEvent = (event) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: snap((event.clientX - rect.left) / rect.width),
      y: snap((event.clientY - rect.top) / rect.height),
    };
  };

  const pushElements = (next) => {
    setHistory((items) => [...items.slice(-29), elements]);
    setElements(next);
    setSaveState("modificato");
  };

  const pointerDown = (event) => {
    if (locked) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const point = pointFromEvent(event);
    if (tool === "seleziona") {
      setSelectedId(closestElement(elements, point)?.id || "");
      return;
    }
    if (tool === "nota") {
      const item = {
        id: uuid(),
        tipo: "nota",
        x1: point.x,
        y1: point.y,
        x2: point.x,
        y2: point.y,
        testo: "Nota",
      };
      pushElements([...elements, item]);
      setSelectedId(item.id);
      setTool("seleziona");
      return;
    }
    setDraft({
      id: uuid(),
      tipo: tool,
      x1: point.x,
      y1: point.y,
      x2: point.x,
      y2: point.y,
    });
  };

  const pointerMove = (event) => {
    if (!draft || locked) return;
    const point = pointFromEvent(event);
    setDraft((current) => ({ ...current, x2: point.x, y2: point.y }));
  };

  const pointerUp = () => {
    if (!draft || locked) return;
    if (normalizedLength(draft, canvasRatio) < 0.015) {
      setDraft(null);
      return;
    }
    if (draft.tipo === "calibra") {
      setCalibrationDraft(draft);
      setCalibrationMeters("");
      setDraft(null);
      return;
    }
    const item = {
      ...draft,
      testo: draft.tipo === "ambiente" ? "Ambiente" : undefined,
      metri:
        draft.tipo === "quota"
          ? metersFor(draft, calibration, canvasRatio)
          : undefined,
    };
    pushElements([...elements, item]);
    setSelectedId(item.id);
    setDraft(null);
    setTool("seleziona");
  };

  const confirmCalibration = () => {
    const meters = Number(calibrationMeters);
    if (!calibrationDraft || !Number.isFinite(meters) || meters <= 0) {
      toast.error("Inserisci una misura reale valida");
      return;
    }
    const nextCalibration = {
      metri: meters,
      distanza_normalizzata: Number(
        normalizedLength(calibrationDraft, canvasRatio).toFixed(8),
      ),
    };
    setCalibration(nextCalibration);
    pushElements(
      elements.map((item) =>
        item.tipo === "quota"
          ? {
              ...item,
              metri: metersFor(item, nextCalibration, canvasRatio),
            }
          : item,
      ),
    );
    setCalibrationDraft(null);
    setTool("quota");
    setSaveState("modificato");
    toast.success("Scala calibrata: le nuove quote saranno calcolate in metri");
  };

  const selectPlan = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      validateRilievoPlan(file);
      if (file.type === "application/pdf" && !isOnline) {
        throw new Error("Per preparare la preview PDF serve una connessione.");
      }
      setBusy(true);
      const previewBlob = await createRilievoPlanPreview({
        rilievoId: rilievo.id,
        file,
      });
      setPendingPlan({ file, previewBlob });
      setSaveState("modificato");
    } catch (error) {
      toast.error("Planimetria non caricata", { description: error.message });
    } finally {
      setBusy(false);
    }
  };

  const addPhotos = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    const available =
      MAX_RILIEVO_GENERAL_PHOTOS - photoPaths.length - pendingPhotos.length;
    if (available <= 0) {
      toast.error(`Massimo ${MAX_RILIEVO_GENERAL_PHOTOS} foto generali`);
      return;
    }
    try {
      setBusy(true);
      const next = [];
      for (const file of files.slice(0, available)) {
        next.push(await compressCampoPhoto(file));
      }
      setPendingPhotos((items) => [...items, ...next]);
      setSaveState("modificato");
    } catch (error) {
      toast.error("Foto non aggiunta", { description: error.message });
    } finally {
      setBusy(false);
    }
  };

  const payload = useMemo(
    () => ({
      ...asset,
      canvas_width: 1200,
      canvas_height: Math.round(1200 * (canvasSize.height / canvasSize.width)),
      calibrazione: calibration,
      elementi: elements,
      foto_paths: photoPaths,
    }),
    [asset, calibration, canvasSize, elements, photoPaths],
  );

  const save = async () => {
    if (locked || busy) return;
    setBusy(true);
    setSaveState(isOnline ? "salvataggio" : "in_attesa");
    try {
      let body = payload;
      if (isOnline) {
        if (pendingPlan?.file) {
          body = {
            ...body,
            ...(await uploadRilievoPlan({
              user,
              rilievoId: rilievo.id,
              file: pendingPlan.file,
              previewBlob: pendingPlan.previewBlob,
            })),
          };
        }
        if (pendingPhotos.length) {
          const paths = await uploadRilievoGeneralPhotos({
            user,
            rilievoId: rilievo.id,
            photos: pendingPhotos,
          });
          body = {
            ...body,
            foto_paths: Array.from(new Set([...photoPaths, ...paths])),
          };
        }
        const saved = await saveRilievoTavola(rilievo.id, body);
        setPendingPlan(null);
        setPendingPhotos([]);
        setAsset({
          planimetria_path: saved.planimetria_path || null,
          planimetria_preview_path: saved.planimetria_preview_path || null,
          planimetria_filename: saved.planimetria_filename || null,
          planimetria_mime_type: saved.planimetria_mime_type || null,
        });
        setPhotoPaths(saved.foto_paths || []);
        setSaveState("salvato");
        onSaved(saved);
        toast.success("Tavola e foto del rilievo salvate");
      } else {
        await enqueueRilievoOperation(slug, {
          kind: "tavola",
          entity_id: rilievo.id,
          rilievo_id: rilievo.id,
          body,
          plan_file: pendingPlan?.file || null,
          plan_preview: pendingPlan?.previewBlob || null,
          photos: pendingPhotos,
        });
        onQueueChanged((await listRilievoOperations(slug)).length);
        onSaved({
          ...rilievo,
          ...asset,
          planimetria_data: {
            version: 1,
            canvas_width: body.canvas_width,
            canvas_height: body.canvas_height,
            calibrazione: body.calibrazione,
            elementi: body.elementi,
          },
          foto_paths: body.foto_paths,
        });
        setSaveState("in_attesa");
        toast.success("Tavola salvata sul dispositivo");
      }
    } catch (error) {
      setSaveState("errore");
      toast.error("Tavola non salvata", {
        description: formatApiErrorDetail(
          error?.response?.data?.detail || error.message,
        ),
      });
    } finally {
      setBusy(false);
    }
  };

  const updateSelected = (changes) => {
    pushElements(
      elements.map((item) =>
        item.id === selectedId ? { ...item, ...changes } : item,
      ),
    );
  };

  const resetBlank = () => {
    if (
      !window.confirm(
        "Creare una tavola vuota? Le annotazioni attuali saranno rimosse.",
      )
    )
      return;
    setAsset({
      planimetria_path: null,
      planimetria_preview_path: null,
      planimetria_filename: null,
      planimetria_mime_type: null,
    });
    setPendingPlan(null);
    setBackgroundUrl("");
    setBackgroundImage(null);
    pushElements([]);
    setCalibration(null);
    setSelectedId("");
  };

  return (
    <section className="rounded-2xl border border-stroke bg-surface p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="campo-eyebrow">Tavola del rilievo</p>
          <h3 className="font-display text-xl uppercase text-ink">
            Planimetria, quote e foto immobile
          </h3>
          <p className="mt-1 text-xs text-fog">
            Carica PDF o immagine, calibra una misura nota e traccia muri,
            ambienti e quote. Per i PDF viene usata come tavola la prima
            pagina; il file originale resta conservato.
          </p>
        </div>
        <span
          className={`text-[10px] uppercase ${saveState === "errore" ? "text-red-400" : "text-fog"}`}
        >
          {saveState === "salvataggio"
            ? "Salvataggio…"
            : saveState === "in_attesa"
              ? "In attesa di sincronizzazione"
              : saveState === "modificato"
                ? "Modifiche da salvare"
                : saveState === "errore"
                  ? "Errore"
                  : "Salvato"}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <input
          ref={planInputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          className="sr-only"
          onChange={selectPlan}
        />
        <button
          type="button"
          disabled={locked || busy}
          onClick={() => planInputRef.current?.click()}
          className="flex min-h-10 items-center gap-2 rounded-xl bg-brand px-3 text-xs uppercase text-white disabled:opacity-40"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileUp className="h-4 w-4" />
          )}
          Carica planimetria
        </button>
        <button
          type="button"
          disabled={locked}
          onClick={resetBlank}
          className="min-h-10 rounded-xl border border-stroke px-3 text-xs uppercase text-ink disabled:opacity-40"
        >
          Disegna da zero
        </button>
        {(asset.planimetria_filename || pendingPlan?.file?.name) && (
          <span className="flex min-h-10 items-center rounded-xl border border-stroke bg-bg px-3 text-xs text-fog">
            {pendingPlan?.file?.name || asset.planimetria_filename}
          </span>
        )}
      </div>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-2">
        {TOOLS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            disabled={locked}
            onClick={() => setTool(id)}
            aria-pressed={tool === id}
            className={`flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border px-3 text-[11px] uppercase ${tool === id ? "border-brand bg-brand/10 text-brand" : "border-stroke text-fog"}`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      <div
        ref={containerRef}
        className="mt-2 overflow-hidden rounded-xl border border-stroke bg-white"
      >
        <canvas
          ref={canvasRef}
          aria-label="Editor planimetria del rilievo"
          className="block w-full touch-none"
          style={{
            height: `${canvasSize.height}px`,
            cursor: tool === "seleziona" ? "default" : "crosshair",
          }}
          onPointerDown={pointerDown}
          onPointerMove={pointerMove}
          onPointerUp={pointerUp}
          onPointerCancel={() => setDraft(null)}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={locked || !history.length}
          onClick={() => {
            const previous = history[history.length - 1];
            setElements(previous);
            setHistory((items) => items.slice(0, -1));
            setSaveState("modificato");
          }}
          className="flex min-h-10 items-center gap-1 rounded-xl border border-stroke px-3 text-xs text-fog disabled:opacity-30"
        >
          <Undo2 className="h-4 w-4" /> Annulla
        </button>
        <button
          type="button"
          disabled={locked || !selected}
          onClick={() => {
            pushElements(elements.filter((item) => item.id !== selectedId));
            setSelectedId("");
          }}
          className="flex min-h-10 items-center gap-1 rounded-xl border border-red-500/30 px-3 text-xs text-red-400 disabled:opacity-30"
        >
          <Trash2 className="h-4 w-4" /> Elimina elemento
        </button>
        <span className="text-xs text-fog">
          {calibration
            ? `Scala calibrata su ${calibration.metri} m`
            : "Per quote automatiche usa prima Calibra"}
        </span>
      </div>

      {calibrationDraft && (
        <div className="mt-4 rounded-xl border border-brand/40 bg-brand/5 p-3">
          <label className="campo-field">
            <span>Lunghezza reale della linea tracciata (metri)</span>
            <div className="flex gap-2">
              <input
                type="number"
                min="0.001"
                step="0.001"
                inputMode="decimal"
                value={calibrationMeters}
                onChange={(event) => setCalibrationMeters(event.target.value)}
              />
              <button
                type="button"
                onClick={confirmCalibration}
                className="rounded-xl bg-brand px-4 text-xs uppercase text-white"
              >
                Conferma
              </button>
            </div>
          </label>
        </div>
      )}

      {selected && (
        <div className="mt-4 grid gap-3 rounded-xl border border-stroke bg-bg p-3 sm:grid-cols-2">
          <label className="campo-field">
            <span>Etichetta elemento</span>
            <input
              value={selected.testo || ""}
              disabled={locked}
              onChange={(event) =>
                updateSelected({ testo: event.target.value })
              }
            />
          </label>
          {selected.tipo === "quota" && (
            <label className="campo-field">
              <span>Misura (metri)</span>
              <input
                type="number"
                min="0"
                step="0.001"
                inputMode="decimal"
                value={selected.metri ?? ""}
                disabled={locked}
                onChange={(event) =>
                  updateSelected({
                    metri:
                      event.target.value === ""
                        ? null
                        : Number(event.target.value),
                  })
                }
              />
            </label>
          )}
        </div>
      )}

      <div className="mt-6 border-t border-stroke pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-display text-sm uppercase text-ink">
              Foto generali immobile
            </p>
            <p className="text-xs text-fog">
              {photoPaths.length + pendingPhotos.length}/
              {MAX_RILIEVO_GENERAL_PHOTOS} foto · le foto dei singoli ambienti
              restano nelle relative schede.
            </p>
          </div>
          <>
            <input
              ref={photoInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              multiple
              className="sr-only"
              onChange={addPhotos}
            />
            <button
              type="button"
              disabled={
                locked ||
                busy ||
                photoPaths.length + pendingPhotos.length >=
                  MAX_RILIEVO_GENERAL_PHOTOS
              }
              onClick={() => photoInputRef.current?.click()}
              className="flex min-h-10 items-center gap-2 rounded-xl border border-brand/40 px-3 text-xs uppercase text-brand disabled:opacity-40"
            >
              <Camera className="h-4 w-4" /> Aggiungi foto
            </button>
          </>
        </div>
        {(savedPhotos.length > 0 || pendingPhotos.length > 0) && (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {savedPhotos.map((photo) => (
              <div
                key={photo.path}
                className="relative aspect-square overflow-hidden rounded-xl border border-stroke bg-bg"
              >
                <img
                  src={photo.url}
                  alt="Foto generale immobile"
                  className="h-full w-full object-cover"
                />
                {!locked && (
                  <button
                    type="button"
                    onClick={() => {
                      setPhotoPaths((paths) =>
                        paths.filter((path) => path !== photo.path),
                      );
                      setSaveState("modificato");
                    }}
                    aria-label="Rimuovi foto generale"
                    className="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-full bg-black/70 text-white"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
            {pendingPhotos.map((photo) => (
              <PhotoPreview
                key={photo.id}
                photo={photo}
                onRemove={() =>
                  setPendingPhotos((items) =>
                    items.filter((item) => item.id !== photo.id),
                  )
                }
              />
            ))}
          </div>
        )}
      </div>

      {!locked && (
        <button
          type="button"
          disabled={busy}
          onClick={() => void save()}
          className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Salva planimetria, misure e foto
        </button>
      )}
    </section>
  );
}
