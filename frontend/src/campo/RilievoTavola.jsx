import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Camera,
  Download,
  Eraser,
  FileText,
  FileUp,
  Hand,
  Loader2,
  Maximize2,
  Minimize2,
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
  ZoomIn,
  ZoomOut,
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
  clampPlanView,
  closestElement,
  metersFor,
  normalizedLength,
  panPlanBy,
  planToViewport,
  roomMetrics,
  viewportToPlan,
  zoomPlanAt,
} from "./rilievoGeometry";
import {
  downloadRilievoPdf,
  downloadRilievoPng,
  rilievoExportBaseName,
  rilievoExportDimensions,
} from "./rilievoExport";

const TOOLS = [
  { id: "seleziona", label: "Seleziona", Icon: MousePointer2 },
  { id: "sposta", label: "Sposta", Icon: Hand },
  { id: "gomma", label: "Gomma", Icon: Eraser },
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

function drawArrow(context, start, end, styleScale = 1) {
  const angle = Math.atan2(end.y - start.y, end.x - start.x);
  for (const point of [start, end]) {
    const reverse = point === start ? 0 : Math.PI;
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineTo(
      point.x + Math.cos(angle + reverse + 0.55) * 9 * styleScale,
      point.y + Math.sin(angle + reverse + 0.55) * 9 * styleScale,
    );
    context.moveTo(point.x, point.y);
    context.lineTo(
      point.x + Math.cos(angle + reverse - 0.55) * 9 * styleScale,
      point.y + Math.sin(angle + reverse - 0.55) * 9 * styleScale,
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

function renderTavolaCanvas({
  canvas,
  width,
  height,
  pixelRatio = 1,
  styleScale = 1,
  backgroundImage,
  calibration,
  elements,
  draft = null,
  selectedId = "",
  view = { zoom: 1, x: 0, y: 0 },
}) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Editor grafico non disponibile.");
  const renderWidth = Math.round(width * pixelRatio);
  const renderHeight = Math.round(height * pixelRatio);
  if (canvas.width !== renderWidth || canvas.height !== renderHeight) {
    canvas.width = renderWidth;
    canvas.height = renderHeight;
  }
  const currentView = clampPlanView(view);
  const canvasRatio = height / width;
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#f8f7f3";
  context.fillRect(0, 0, width, height);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  context.save();
  context.translate(
    width * (0.5 + currentView.x),
    height * (0.5 + currentView.y),
  );
  context.scale(currentView.zoom, currentView.zoom);
  context.translate(-width / 2, -height / 2);
  context.strokeStyle = "#e5e1d8";
  context.lineWidth = styleScale / currentView.zoom;
  const gridStep = 24 * styleScale;
  for (let x = 0; x <= width; x += gridStep) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }
  for (let y = 0; y <= height; y += gridStep) {
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
  context.restore();

  const paint = (element, isDraft = false) => {
    const normalizedStart = planToViewport(
      { x: element.x1, y: element.y1 },
      currentView,
    );
    const normalizedEnd = planToViewport(
      { x: element.x2, y: element.y2 },
      currentView,
    );
    const start = {
      x: normalizedStart.x * width,
      y: normalizedStart.y * height,
    };
    const end = {
      x: normalizedEnd.x * width,
      y: normalizedEnd.y * height,
    };
    const active = selectedId === element.id;
    context.save();
    context.strokeStyle = active ? "#f59e0b" : "#b91c1c";
    context.fillStyle = active ? "rgba(245,158,11,.18)" : "rgba(185,28,28,.10)";
    context.lineWidth =
      (element.tipo === "muro" ? 5 : active ? 3 : 2) * styleScale;
    if (isDraft) context.setLineDash([8 * styleScale, 6 * styleScale]);
    if (element.tipo === "ambiente") {
      context.fillRect(start.x, start.y, end.x - start.x, end.y - start.y);
      context.strokeRect(start.x, start.y, end.x - start.x, end.y - start.y);
    } else if (element.tipo === "nota") {
      context.beginPath();
      context.arc(start.x, start.y, 6 * styleScale, 0, Math.PI * 2);
      context.fillStyle = "#f59e0b";
      context.fill();
    } else {
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.stroke();
      if (element.tipo === "quota" || element.tipo === "calibra") {
        drawArrow(context, start, end, styleScale);
      }
    }
    const label = elementLabel(element, calibration, canvasRatio);
    if (label) {
      const x = (start.x + end.x) / 2;
      const y = (start.y + end.y) / 2;
      context.font = `600 ${13 * styleScale}px Arial`;
      const metrics = context.measureText(label);
      context.fillStyle = "rgba(255,255,255,.92)";
      context.fillRect(
        x - metrics.width / 2 - 5 * styleScale,
        y - 18 * styleScale,
        metrics.width + 10 * styleScale,
        22 * styleScale,
      );
      context.fillStyle = "#171717";
      context.fillText(label, x - metrics.width / 2, y - 3 * styleScale);
    }
    context.restore();
  };

  elements.forEach((element) => paint(element));
  if (draft) paint(draft, true);
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
  const pointersRef = useRef(new Map());
  const pinchRef = useRef(null);
  const gestureActiveRef = useRef(false);
  const panDragRef = useRef(null);
  const viewRef = useRef({ zoom: 1, x: 0, y: 0 });
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
  const [exporting, setExporting] = useState("");
  const [saveState, setSaveState] = useState("salvato");
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const [expanded, setExpanded] = useState(false);
  viewRef.current = view;
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
    setView({ zoom: 1, x: 0, y: 0 });
    setSaveState("salvato");
  }, [persistedVersion]);

  useEffect(() => {
    if (!expanded) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [expanded]);

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
        const url = await createRilievoPlanUrl(path, rilievo.id);
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
  }, [
    asset.planimetria_path,
    asset.planimetria_preview_path,
    pendingPlan,
    rilievo.id,
  ]);

  useEffect(() => {
    if (!backgroundUrl) {
      setBackgroundImage(null);
      return undefined;
    }
    const image = new Image();
    image.crossOrigin = "anonymous";
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
    createRilievoPhotoUrls(photoPaths, rilievo.id)
      .then((items) => active && setSavedPhotos(items))
      .catch(() => active && setSavedPhotos([]));
    return () => {
      active = false;
    };
  }, [photoPaths, rilievo.id]);

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
    const { width, height } = canvasSize;
    renderTavolaCanvas({
      canvas,
      width,
      height,
      pixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      backgroundImage,
      calibration,
      elements,
      draft,
      selectedId,
      view,
    });
  }, [
    backgroundImage,
    calibration,
    canvasSize,
    draft,
    elements,
    selectedId,
    view,
  ]);

  useEffect(() => drawCanvas(), [drawCanvas]);

  const viewportPointFromEvent = (event) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) / rect.width,
      y: (event.clientY - rect.top) / rect.height,
    };
  };

  const pointFromEvent = (event) => {
    const point = viewportToPlan(
      viewportPointFromEvent(event),
      viewRef.current,
    );
    return { x: snap(point.x), y: snap(point.y) };
  };

  const pointerPair = () =>
    Array.from(pointersRef.current.values()).slice(0, 2);

  const pairGeometry = (points) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const first = points[0];
    const second = points[1];
    return {
      distance: Math.max(
        1,
        Math.hypot(
          second.clientX - first.clientX,
          second.clientY - first.clientY,
        ),
      ),
      midpoint: {
        x: ((first.clientX + second.clientX) / 2 - rect.left) / rect.width,
        y: ((first.clientY + second.clientY) / 2 - rect.top) / rect.height,
      },
    };
  };

  const beginPinch = () => {
    const geometry = pairGeometry(pointerPair());
    const initialView = viewRef.current;
    pinchRef.current = {
      distance: geometry.distance,
      zoom: initialView.zoom,
      anchor: viewportToPlan(geometry.midpoint, initialView),
    };
    gestureActiveRef.current = true;
    panDragRef.current = null;
    setPanning(true);
    setDraft(null);
  };

  const pushElements = (next) => {
    setHistory((items) => [...items.slice(-29), elements]);
    setElements(next);
    setSaveState("modificato");
  };

  const pointerDown = (event) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    pointersRef.current.set(event.pointerId, {
      clientX: event.clientX,
      clientY: event.clientY,
    });
    if (pointersRef.current.size >= 2) {
      beginPinch();
      return;
    }
    if (gestureActiveRef.current) return;
    if (tool === "sposta") {
      panDragRef.current = {
        pointerId: event.pointerId,
        clientX: event.clientX,
        clientY: event.clientY,
      };
      setPanning(true);
      return;
    }
    if (locked) return;
    const point = pointFromEvent(event);
    if (tool === "seleziona") {
      setSelectedId(
        closestElement(
          elements,
          point,
          0.045 / viewRef.current.zoom,
          canvasRatio,
        )?.id || "",
      );
      return;
    }
    if (tool === "gomma") {
      const target = closestElement(
        elements,
        point,
        0.055 / viewRef.current.zoom,
        canvasRatio,
      );
      if (!target) return;
      pushElements(elements.filter((item) => item.id !== target.id));
      if (selectedId === target.id) setSelectedId("");
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
    if (pointersRef.current.has(event.pointerId)) {
      pointersRef.current.set(event.pointerId, {
        clientX: event.clientX,
        clientY: event.clientY,
      });
    }
    if (pointersRef.current.size >= 2 && pinchRef.current) {
      const geometry = pairGeometry(pointerPair());
      const pinch = pinchRef.current;
      const nextZoom = clampPlanView({
        zoom: pinch.zoom * (geometry.distance / pinch.distance),
      }).zoom;
      setView(
        clampPlanView({
          zoom: nextZoom,
          x: geometry.midpoint.x - ((pinch.anchor.x - 0.5) * nextZoom + 0.5),
          y: geometry.midpoint.y - ((pinch.anchor.y - 0.5) * nextZoom + 0.5),
        }),
      );
      return;
    }
    if (gestureActiveRef.current) return;
    const pan = panDragRef.current;
    if (pan?.pointerId === event.pointerId) {
      const rect = canvasRef.current.getBoundingClientRect();
      const delta = {
        x: (event.clientX - pan.clientX) / rect.width,
        y: (event.clientY - pan.clientY) / rect.height,
      };
      panDragRef.current = {
        ...pan,
        clientX: event.clientX,
        clientY: event.clientY,
      };
      setView((current) => panPlanBy(current, delta));
      return;
    }
    if (!draft || locked) return;
    const point = pointFromEvent(event);
    setDraft((current) => ({ ...current, x2: point.x, y2: point.y }));
  };

  const pointerUp = (event) => {
    pointersRef.current.delete(event.pointerId);
    if (gestureActiveRef.current) {
      if (pointersRef.current.size === 0) {
        gestureActiveRef.current = false;
        pinchRef.current = null;
        setPanning(false);
      }
      return;
    }
    if (panDragRef.current?.pointerId === event.pointerId) {
      panDragRef.current = null;
      setPanning(false);
      return;
    }
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

  const pointerCancel = (event) => {
    pointersRef.current.delete(event.pointerId);
    if (pointersRef.current.size === 0) {
      gestureActiveRef.current = false;
      pinchRef.current = null;
      panDragRef.current = null;
      setPanning(false);
    }
    setDraft(null);
  };

  const changeZoom = (amount, focal = { x: 0.5, y: 0.5 }) => {
    setView((current) => zoomPlanAt(current, current.zoom + amount, focal));
  };

  const resetView = () => setView({ zoom: 1, x: 0, y: 0 });

  const wheelZoom = (event) => {
    if (!event.ctrlKey) return;
    event.preventDefault();
    changeZoom(event.deltaY < 0 ? 0.25 : -0.25, viewportPointFromEvent(event));
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
      resetView();
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

  const hasBackgroundAsset = Boolean(
    pendingPlan?.previewBlob ||
    asset.planimetria_preview_path ||
    asset.planimetria_path,
  );
  const exportReady =
    ["salvato", "in_attesa"].includes(saveState) &&
    !busy &&
    !exporting &&
    (!hasBackgroundAsset || Boolean(backgroundImage)) &&
    (Boolean(backgroundImage) || elements.length > 0);

  const buildExportCanvas = () => {
    const { width, height } = rilievoExportDimensions(
      payload.canvas_width,
      payload.canvas_height,
    );
    const canvas = document.createElement("canvas");
    renderTavolaCanvas({
      canvas,
      width,
      height,
      backgroundImage,
      calibration,
      elements,
      selectedId: "",
      view: { zoom: 1, x: 0, y: 0 },
      styleScale: Math.max(1, width / 1000),
    });
    return canvas;
  };

  const downloadElaborato = async (format) => {
    if (!exportReady) {
      toast.error("Salva prima le modifiche alla planimetria");
      return;
    }
    setExporting(format);
    try {
      const canvas = buildExportCanvas();
      const baseName = rilievoExportBaseName(
        asset.planimetria_filename,
        rilievo.id,
      );
      if (format === "pdf") {
        await downloadRilievoPdf(canvas, baseName);
      } else {
        await downloadRilievoPng(canvas, baseName);
      }
      toast.success(
        format === "pdf"
          ? "PDF annotato scaricato"
          : "Immagine annotata scaricata",
      );
    } catch (error) {
      toast.error("Elaborato non scaricato", {
        description: error?.message || "Riprova tra poco.",
      });
    } finally {
      setExporting("");
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
    resetView();
    pushElements([]);
    setCalibration(null);
    setSelectedId("");
  };

  return (
    <section
      className={
        expanded
          ? "fixed inset-0 z-[80] overflow-y-auto bg-surface p-3 sm:p-5"
          : "rounded-2xl border border-stroke bg-surface p-4 md:p-5"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="campo-eyebrow">Tavola del rilievo</p>
          <h3 className="font-display text-xl uppercase text-ink">
            Planimetria, quote e foto immobile
          </h3>
          <p className="mt-1 text-xs text-fog">
            Carica PDF o immagine, calibra una misura nota e traccia muri,
            ambienti e quote. Per i PDF viene usata come tavola la prima pagina;
            il file originale resta conservato.
          </p>
        </div>
        <div className="flex items-center gap-2">
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
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="flex h-11 w-11 items-center justify-center rounded-xl border border-stroke text-ink"
            aria-label={
              expanded
                ? "Riduci editor planimetria"
                : "Espandi editor planimetria"
            }
          >
            {expanded ? (
              <Minimize2 className="h-5 w-5" />
            ) : (
              <Maximize2 className="h-5 w-5" />
            )}
          </button>
        </div>
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
            disabled={locked && id !== "sposta"}
            onClick={() => setTool(id)}
            aria-pressed={tool === id}
            className={`flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border px-3 text-[11px] uppercase ${tool === id ? "border-brand bg-brand/10 text-brand" : "border-stroke text-fog"}`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      {tool === "gomma" && (
        <p className="mb-2 text-xs text-brand" role="status">
          Gomma attiva: tocca una forma per cancellarla. Puoi recuperarla con
          Annulla.
        </p>
      )}

      {tool === "sposta" && (
        <p className="mb-2 text-xs text-brand" role="status">
          Trascina la tavola con un dito. Su tablet e smartphone puoi usare due
          dita per zoom e spostamento.
        </p>
      )}

      <div className="mb-2 flex flex-wrap items-center gap-2 rounded-xl border border-stroke bg-bg p-2">
        <button
          type="button"
          onClick={() => changeZoom(-0.25)}
          disabled={view.zoom <= 1}
          className="flex h-11 w-11 items-center justify-center rounded-lg border border-stroke text-ink disabled:opacity-30"
          aria-label="Riduci zoom planimetria"
        >
          <ZoomOut className="h-5 w-5" />
        </button>
        <output
          className="min-w-14 text-center font-display text-xs text-ink"
          aria-live="polite"
        >
          {Math.round(view.zoom * 100)}%
        </output>
        <button
          type="button"
          onClick={() => changeZoom(0.25)}
          disabled={view.zoom >= 5}
          className="flex h-11 w-11 items-center justify-center rounded-lg border border-stroke text-ink disabled:opacity-30"
          aria-label="Aumenta zoom planimetria"
        >
          <ZoomIn className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={resetView}
          disabled={view.zoom === 1 && view.x === 0 && view.y === 0}
          className="min-h-11 rounded-lg border border-stroke px-3 text-[11px] uppercase text-fog disabled:opacity-30"
        >
          Adatta
        </button>
        <span className="min-w-48 flex-1 text-right text-[11px] text-fog max-sm:text-left">
          Zoom 100–500% · usa “Sposta” per trascinare
        </span>
      </div>

      <div
        ref={containerRef}
        className="relative mt-2 overflow-hidden rounded-xl border border-stroke bg-white shadow-inner"
      >
        <canvas
          ref={canvasRef}
          aria-label="Editor planimetria del rilievo"
          className="block w-full touch-none"
          style={{
            height: `${canvasSize.height}px`,
            cursor:
              tool === "seleziona"
                ? "default"
                : tool === "sposta"
                  ? panning
                    ? "grabbing"
                    : "grab"
                  : tool === "gomma"
                    ? "cell"
                    : "crosshair",
          }}
          onPointerDown={pointerDown}
          onPointerMove={pointerMove}
          onPointerUp={pointerUp}
          onPointerCancel={pointerCancel}
          onWheel={wheelZoom}
        />
        {view.zoom > 1 && (
          <span className="pointer-events-none absolute bottom-2 right-2 rounded-full bg-black/65 px-2.5 py-1 text-[10px] uppercase text-white">
            {Math.round(view.zoom * 100)}%
          </span>
        )}
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

      <div
        className={`${locked ? "mt-5" : "mt-3"} rounded-xl border border-stroke bg-bg p-3`}
      >
        <div className="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            disabled={!exportReady}
            onClick={() => void downloadElaborato("png")}
            className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-brand/40 px-4 font-display text-xs uppercase text-brand disabled:opacity-40"
          >
            {exporting === "png" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Scarica immagine
          </button>
          <button
            type="button"
            disabled={!exportReady}
            onClick={() => void downloadElaborato("pdf")}
            className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-brand/40 px-4 font-display text-xs uppercase text-brand disabled:opacity-40"
          >
            {exporting === "pdf" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
            Scarica PDF
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-fog">
          Disponibile dopo il salvataggio: include planimetria, misure, forme e
          note in un unico elaborato ad alta risoluzione.
        </p>
      </div>
    </section>
  );
}
