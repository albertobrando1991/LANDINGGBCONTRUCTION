import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ClipboardList,
  CloudOff,
  Download,
  Loader2,
  Map as MapIcon,
  PenLine,
  Plus,
  RefreshCw,
  Ruler,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import {
  archiveRilievoAmbiente,
  createRilievo,
  loadRilievi,
  loadRilievo,
  patchRilievo,
  saveRilievoTavola,
  saveRilievoAmbiente,
} from "@/lib/rilievoApi";
import {
  cacheRilievo,
  cacheRilievoReferences,
  createOfflineRilievo,
  enqueueRilievoOperation,
  listRilievoOperations,
  mergeRemoteRilievi,
  promoteCachedRilievo,
  readCachedRilievi,
  readCachedRilievo,
  readCachedRilievoReferences,
  readRilievoOfflinePack,
  replaceRilievoOperation,
  resolveRilievoId,
  saveRilievoIdResolution,
  syncRilievoOperations,
  upsertCachedRilievo,
} from "@/lib/rilievoQueue";
import {
  compressCampoPhoto,
  MAX_RILIEVO_PHOTOS,
  uploadRilievoGeneralPhotos,
  uploadRilievoPhotos,
} from "@/lib/campoPhotos";
import { uploadRilievoPlan } from "@/lib/rilievoAssets";
import {
  loadOfflinePhotoPreviews,
  prepareRilievoOffline,
} from "@/lib/rilievoOffline";
import { requestPersistentOfflineStorage } from "@/lib/offlineStorage";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import {
  applyRilievoLeadSelection,
  normalizeRilievoLeads,
  rilievoLeadLabel,
} from "./rilievoLeadSelection";
import { formatDecimale, parseDecimale } from "./rilievoNumeri";
import { ALTEZZA_PRESETS, AMBIENTE_TEMPLATES } from "./rilievoTemplates";
import { mapLimit } from "@/lib/network";
import DictationHint from "./DictationHint";
import PhotoAnnotatorModal from "./PhotoAnnotatorModal";
import RilievoTavola from "./RilievoTavola";

const EMPTY_RILIEVO = {
  sopralluogo_legacy_id: "",
  lead_id: "",
  cliente: "",
  indirizzo: "",
  data_rilievo: "",
  tecnico: "",
  note: "",
};

const TIPI_AMBIENTE = [
  "Soggiorno",
  "Cucina",
  "Camera",
  "Bagno",
  "Disimpegno",
  "Ingresso",
  "Ripostiglio",
  "Balcone",
  "Terrazzo",
  "Altro",
];

function localDate() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function newUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function detailMessage(error) {
  return formatApiErrorDetail(error?.response?.data?.detail || error?.message);
}

function isRetryable(error) {
  const status = error?.response?.status;
  return !error?.response || status === 408 || status === 429 || status >= 500;
}

function isOfflinePackReady(pack, rilievo) {
  if (!pack?.ready) return false;
  if (!pack.rilievo_updated_at || !rilievo?.updated_at) return true;
  return String(pack.rilievo_updated_at) === String(rilievo.updated_at);
}

function hasUnsavedEditorState(value) {
  return ["modificato", "salvataggio", "errore"].includes(value);
}

function PreviewBlob({ photo, onRemove, onAnnotate }) {
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
          alt="Foto ambiente da salvare"
          className="h-full w-full object-cover"
        />
      )}
      <button
        type="button"
        onClick={onRemove}
        aria-label="Rimuovi foto"
        className="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-full bg-black/70 text-white"
      >
        <X className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={onAnnotate}
        aria-label="Annota foto"
        className="absolute bottom-1 left-1 flex min-h-8 items-center gap-1 rounded-full bg-black/75 px-2 text-[9px] uppercase text-white"
      >
        <PenLine className="h-3.5 w-3.5" /> Annota
      </button>
    </div>
  );
}

function AmbienteEditor({
  rilievo,
  ambiente,
  locked,
  isOnline,
  user,
  slug,
  onSaved,
  onArchived,
  onSaveStateChange,
  onQueueChanged,
}) {
  const [draft, setDraft] = useState(null);
  const [pendingPhotos, setPendingPhotos] = useState([]);
  const [savedPhotos, setSavedPhotos] = useState([]);
  const [saveState, setSaveState] = useState("salvato");
  const [photoProgress, setPhotoProgress] = useState("");
  const [annotatingPhoto, setAnnotatingPhoto] = useState(null);
  const inputRef = useRef(null);
  const savingRef = useRef(false);
  const lastSavedRef = useRef("");
  const photosEnabled = Boolean(user && user !== false);

  useEffect(() => {
    onSaveStateChange?.(saveState);
  }, [onSaveStateChange, saveState]);

  useEffect(() => {
    const next = {
      nome: ambiente.nome || "Nuovo ambiente",
      tipologia: ambiente.tipologia || "",
      piano: ambiente.piano || "",
      ordine: Number(ambiente.ordine || 0),
      lunghezza: formatDecimale(ambiente.lunghezza),
      larghezza: formatDecimale(ambiente.larghezza),
      altezza: formatDecimale(ambiente.altezza),
      superficie: formatDecimale(ambiente.superficie),
      misure_extra: Array.isArray(ambiente.misure_extra)
        ? ambiente.misure_extra.map((item) => ({
            ...item,
            valore: formatDecimale(item.valore),
          }))
        : [],
      note: ambiente.note || "",
      foto_paths: ambiente.foto_paths || [],
    };
    setDraft(next);
    setPendingPhotos([]);
    lastSavedRef.current = JSON.stringify({ draft: next, pending: [] });
  }, [ambiente]);

  useEffect(() => {
    let active = true;
    listRilievoOperations(slug).then((operations) => {
      if (!active) return;
      const queued = operations.find(
        (item) =>
          item.kind === "ambiente" &&
          item.rilievo_id === rilievo.id &&
          item.ambiente_client_uuid === ambiente.client_uuid,
      );
      if (!queued) return;
      const queuedPhotos = queued.photos || [];
      setPendingPhotos(queuedPhotos);
      setDraft((current) => {
        if (!current) return current;
        const next = {
          ...current,
          ...queued.body,
          lunghezza: formatDecimale(queued.body?.lunghezza),
          larghezza: formatDecimale(queued.body?.larghezza),
          altezza: formatDecimale(queued.body?.altezza),
          superficie: formatDecimale(queued.body?.superficie),
          misure_extra: (queued.body?.misure_extra || []).map((item) => ({
            ...item,
            valore: formatDecimale(item.valore),
          })),
        };
        lastSavedRef.current = JSON.stringify({
          draft: next,
          pending: queuedPhotos.map((photo) => photo.id),
        });
        return next;
      });
      setSaveState("in_attesa");
    });
    return () => {
      active = false;
    };
  }, [ambiente.client_uuid, rilievo.id, slug]);

  useEffect(() => {
    let active = true;
    let localUrls = [];
    loadOfflinePhotoPreviews({
      tenantSlug: slug,
      paths: draft?.foto_paths || [],
      rilievoId: rilievo.id,
      isOnline: isOnline && !rilievo.offline_pending,
    })
      .then((items) => {
        localUrls = items.filter((item) => item.local).map((item) => item.url);
        if (active) setSavedPhotos(items);
      })
      .catch(() => active && setSavedPhotos([]));
    return () => {
      active = false;
      localUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [draft?.foto_paths, isOnline, rilievo.id, rilievo.offline_pending, slug]);

  const numericState = useMemo(() => {
    if (!draft) return { values: {}, extraValues: {}, errors: {} };
    const values = {};
    const extraValues = {};
    const errors = {};
    for (const field of ["lunghezza", "larghezza", "altezza", "superficie"]) {
      const parsed = parseDecimale(draft[field]);
      values[field] = parsed.value;
      if (!parsed.ok) errors[field] = parsed.error;
    }
    for (const item of draft.misure_extra || []) {
      const parsed = parseDecimale(item.valore);
      extraValues[item.id] = parsed.value;
      if (!parsed.ok) errors[`extra-${item.id}`] = parsed.error;
    }
    return { values, extraValues, errors };
  }, [draft]);

  const numberErrors = numericState.errors;
  const hasNumberErrors = Object.keys(numberErrors).length > 0;

  const payload = useMemo(() => {
    if (!draft) return null;
    const length = numericState.values.lunghezza;
    const width = numericState.values.larghezza;
    const manualSurface = numericState.values.superficie;
    return {
      nome: String(draft.nome || "").trim(),
      tipologia: String(draft.tipologia || "").trim() || null,
      piano: String(draft.piano || "").trim() || null,
      ordine: Number(draft.ordine || 0),
      lunghezza: length,
      larghezza: width,
      altezza: numericState.values.altezza,
      superficie:
        manualSurface ??
        (length != null && width != null
          ? Number((length * width).toFixed(3))
          : null),
      misure_extra: (draft.misure_extra || [])
        .filter(
          (item) =>
            item.etichetta?.trim() && String(item.valore ?? "").trim() !== "",
        )
        .map((item) => ({
          id: item.id,
          etichetta: item.etichetta.trim(),
          valore: numericState.extraValues[item.id],
          unita: item.unita || "m",
        })),
      note: String(draft.note || "").trim() || null,
      foto_paths: draft.foto_paths || [],
    };
  }, [draft, numericState]);

  const persist = useCallback(
    async (showToast = false) => {
      if (!payload?.nome || savingRef.current || locked || annotatingPhoto)
        return;
      if (hasNumberErrors) {
        setSaveState("errore");
        if (showToast) {
          toast.error("Correggi le misure non valide prima di salvare");
        }
        return;
      }
      savingRef.current = true;
      setSaveState(isOnline ? "salvataggio" : "in_attesa");
      try {
        let body = payload;
        let queuedPhotos = pendingPhotos;
        if (isOnline && !rilievo.offline_pending) {
          try {
            const uploaded = await uploadRilievoPhotos({
              user,
              rilievoId: rilievo.id,
              ambienteClientUuid: ambiente.client_uuid,
              photos: pendingPhotos,
              onProgress: ({ uploaded: done, total }) =>
                setPhotoProgress(
                  `Upload foto · ${total ? Math.round((done / total) * 100) : 0}%`,
                ),
            });
            body = {
              ...payload,
              foto_paths: Array.from(
                new Set([...(payload.foto_paths || []), ...uploaded]),
              ),
            };
            queuedPhotos = [];
            const saved = await saveRilievoAmbiente(
              rilievo.id,
              ambiente.client_uuid,
              body,
            );
            const nextDraft = {
              ...draft,
              ...saved,
              foto_paths: saved.foto_paths || body.foto_paths,
            };
            setDraft(nextDraft);
            setPendingPhotos([]);
            setPhotoProgress("");
            lastSavedRef.current = JSON.stringify({
              draft: nextDraft,
              pending: [],
            });
            setSaveState("salvato");
            onSaved(saved);
            if (showToast) toast.success("Ambiente salvato");
            return;
          } catch (error) {
            if (!isRetryable(error)) throw error;
          }
        }
        await enqueueRilievoOperation(slug, {
          kind: "ambiente",
          entity_id: `${rilievo.id}:${ambiente.client_uuid}`,
          rilievo_id: rilievo.id,
          ambiente_client_uuid: ambiente.client_uuid,
          body,
          photos: queuedPhotos,
        });
        onSaved({
          ...ambiente,
          ...body,
          client_uuid: ambiente.client_uuid,
        });
        onQueueChanged?.((await listRilievoOperations(slug)).length);
        lastSavedRef.current = JSON.stringify({
          draft,
          pending: pendingPhotos.map((photo) => photo.id),
        });
        setSaveState("in_attesa");
        if (showToast) toast.success("Ambiente salvato sul dispositivo");
      } catch (error) {
        setSaveState("errore");
        if (showToast)
          toast.error("Ambiente non salvato", {
            description: detailMessage(error),
          });
      } finally {
        setPhotoProgress("");
        savingRef.current = false;
      }
    },
    [
      ambiente,
      annotatingPhoto,
      draft,
      hasNumberErrors,
      isOnline,
      locked,
      onSaved,
      onQueueChanged,
      payload,
      pendingPhotos,
      rilievo.id,
      rilievo.offline_pending,
      slug,
      user,
    ],
  );

  useEffect(() => {
    if (!draft || locked || annotatingPhoto || !payload?.nome) return undefined;
    if (hasNumberErrors) {
      setSaveState("errore");
      return undefined;
    }
    const snapshot = JSON.stringify({
      draft,
      pending: pendingPhotos.map((photo) => photo.id),
    });
    if (snapshot === lastSavedRef.current) return undefined;
    setSaveState("modificato");
    const timer = window.setTimeout(() => void persist(false), 1100);
    return () => window.clearTimeout(timer);
  }, [
    annotatingPhoto,
    draft,
    hasNumberErrors,
    locked,
    payload?.nome,
    pendingPhotos,
    persist,
  ]);

  if (!draft) return null;

  const setField = (field, value) =>
    setDraft((current) => ({ ...current, [field]: value }));

  const addPhotos = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    const available =
      MAX_RILIEVO_PHOTOS -
      (draft.foto_paths?.length || 0) -
      pendingPhotos.length;
    if (available <= 0) {
      toast.error(`Massimo ${MAX_RILIEVO_PHOTOS} foto per ambiente`);
      return;
    }
    try {
      const results = await mapLimit(
        files.slice(0, available),
        3,
        async (file) => {
          try {
            return { photo: await compressCampoPhoto(file), file };
          } catch (error) {
            return { error, file };
          }
        },
      );
      const compressed = results.flatMap((result) =>
        result.photo ? [result.photo] : [],
      );
      const failed = results.filter((result) => result.error);
      setPendingPhotos((current) => [...current, ...compressed]);
      if (failed.length) {
        toast.error(`${failed.length} foto non aggiunte`, {
          description: failed
            .map((result) => `${result.file.name}: ${result.error.message}`)
            .join(" · "),
        });
      }
    } catch (error) {
      toast.error("Foto non aggiunta", { description: error.message });
    }
  };

  const archive = async () => {
    if (!window.confirm(`Rimuovere l'ambiente “${draft.nome}” dal rilievo?`))
      return;
    try {
      if (isOnline && !rilievo.offline_pending) {
        try {
          await archiveRilievoAmbiente(rilievo.id, ambiente.client_uuid);
        } catch (error) {
          if (!isRetryable(error)) throw error;
          await enqueueRilievoOperation(slug, {
            kind: "ambiente-elimina",
            entity_id: `${rilievo.id}:${ambiente.client_uuid}`,
            rilievo_id: rilievo.id,
            ambiente_client_uuid: ambiente.client_uuid,
          });
        }
      } else {
        await enqueueRilievoOperation(slug, {
          kind: "ambiente-elimina",
          entity_id: `${rilievo.id}:${ambiente.client_uuid}`,
          rilievo_id: rilievo.id,
          ambiente_client_uuid: ambiente.client_uuid,
        });
      }
      onArchived(ambiente.client_uuid);
      onQueueChanged?.((await listRilievoOperations(slug)).length);
      toast.success(
        isOnline && !rilievo.offline_pending
          ? "Ambiente rimosso"
          : "Rimozione salvata sul dispositivo",
      );
    } catch (error) {
      toast.error("Ambiente non rimosso", {
        description: detailMessage(error),
      });
    }
  };

  return (
    <section className="rounded-2xl border border-stroke bg-surface p-4 md:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
            Ambiente {Number(draft.ordine || 0) + 1}
          </p>
          <h3 className="mt-1 font-display text-xl uppercase text-ink">
            {draft.nome}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] uppercase ${saveState === "errore" ? "text-red-400" : saveState === "salvato" ? "text-success" : "text-fog"}`}
          >
            {saveState === "salvataggio"
              ? "Salvataggio…"
              : saveState === "in_attesa"
                ? "In attesa"
                : saveState === "modificato"
                  ? "Da salvare"
                  : saveState === "errore"
                    ? "Errore"
                    : "Salvato"}
          </span>
          {!locked && (
            <button
              type="button"
              onClick={archive}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-red-500/30 text-red-400"
              aria-label="Rimuovi ambiente"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {!locked && (
        <div className="mb-4 rounded-xl border border-stroke bg-bg p-3">
          <p className="font-display text-[10px] uppercase text-fog">
            Template ambiente
          </p>
          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {AMBIENTE_TEMPLATES.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() =>
                  setDraft((current) => ({
                    ...current,
                    tipologia: template.tipologia,
                    altezza: template.altezza,
                  }))
                }
                className="min-h-10 shrink-0 rounded-full border border-brand/40 px-3 text-[10px] uppercase text-brand"
              >
                {template.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-3">
        <label className="campo-field md:col-span-2">
          <span>Nome ambiente</span>
          <input
            value={draft.nome}
            disabled={locked}
            onChange={(event) => setField("nome", event.target.value)}
          />
        </label>
        <label className="campo-field">
          <span>Tipologia</span>
          <select
            value={draft.tipologia}
            disabled={locked}
            onChange={(event) => setField("tipologia", event.target.value)}
          >
            <option value="">Seleziona…</option>
            {TIPI_AMBIENTE.map((tipo) => (
              <option key={tipo} value={tipo}>
                {tipo}
              </option>
            ))}
          </select>
        </label>
        <label className="campo-field">
          <span>Piano / zona</span>
          <input
            value={draft.piano}
            disabled={locked}
            placeholder="Es. Piano terra"
            onChange={(event) => setField("piano", event.target.value)}
          />
        </label>
        {[
          ["lunghezza", "Lunghezza (m)"],
          ["larghezza", "Larghezza (m)"],
          ["altezza", "Altezza (m)"],
          ["superficie", "Superficie (mq)"],
        ].map(([field, label]) => (
          <label className="campo-field" key={field}>
            <span>{label}</span>
            <input
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={draft[field]}
              disabled={locked}
              aria-invalid={Boolean(numberErrors[field])}
              onChange={(event) => setField(field, event.target.value)}
            />
            {numberErrors[field] && (
              <small className="text-red-400">{numberErrors[field]}</small>
            )}
          </label>
        ))}
      </div>

      {!locked && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-[10px] uppercase text-fog">Altezza rapida</span>
          {ALTEZZA_PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              onClick={() => setField("altezza", preset)}
              className="min-h-9 rounded-full border border-stroke px-3 text-[10px] text-ink hover:border-brand"
            >
              {preset} m
            </button>
          ))}
        </div>
      )}

      <div className="mt-5 rounded-xl border border-stroke bg-bg p-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="font-display text-xs uppercase text-ink">
              Misure aggiuntive
            </p>
            <p className="text-[11px] text-fog">
              Pareti irregolari, nicchie, porte, finestre o altre quote.
            </p>
          </div>
          {!locked && (
            <button
              type="button"
              onClick={() =>
                setField("misure_extra", [
                  ...draft.misure_extra,
                  { id: newUuid(), etichetta: "", valore: "", unita: "m" },
                ])
              }
              className="flex h-10 items-center gap-1 rounded-xl border border-brand/40 px-3 text-xs uppercase text-brand"
            >
              <Plus className="h-4 w-4" /> Misura
            </button>
          )}
        </div>
        <div className="mt-3 space-y-2">
          {draft.misure_extra.map((misura, index) => (
            <div
              key={misura.id}
              className="grid grid-cols-[minmax(0,1fr)_90px_72px_40px] gap-2"
            >
              <input
                aria-label={`Etichetta misura ${index + 1}`}
                className="rounded-lg border border-stroke bg-surface px-2 text-sm text-ink"
                placeholder="Es. Parete lato finestra"
                value={misura.etichetta}
                disabled={locked}
                onChange={(event) =>
                  setField(
                    "misure_extra",
                    draft.misure_extra.map((item) =>
                      item.id === misura.id
                        ? { ...item, etichetta: event.target.value }
                        : item,
                    ),
                  )
                }
              />
              <div className="min-w-0">
                <input
                  aria-label={`Valore misura ${index + 1}`}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  aria-invalid={Boolean(numberErrors[`extra-${misura.id}`])}
                  className="h-full w-full rounded-lg border border-stroke bg-surface px-2 text-sm text-ink"
                  value={misura.valore}
                  disabled={locked}
                  onChange={(event) =>
                    setField(
                      "misure_extra",
                      draft.misure_extra.map((item) =>
                        item.id === misura.id
                          ? { ...item, valore: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
                {numberErrors[`extra-${misura.id}`] && (
                  <small className="block text-[9px] text-red-400">
                    {numberErrors[`extra-${misura.id}`]}
                  </small>
                )}
              </div>
              <select
                aria-label={`Unita misura ${index + 1}`}
                className="rounded-lg border border-stroke bg-surface px-1 text-sm text-ink"
                value={misura.unita}
                disabled={locked}
                onChange={(event) =>
                  setField(
                    "misure_extra",
                    draft.misure_extra.map((item) =>
                      item.id === misura.id
                        ? { ...item, unita: event.target.value }
                        : item,
                    ),
                  )
                }
              >
                {["m", "mq", "cm", "mm", "cad"].map((unit) => (
                  <option key={unit}>{unit}</option>
                ))}
              </select>
              <button
                type="button"
                disabled={locked}
                onClick={() =>
                  setField(
                    "misure_extra",
                    draft.misure_extra.filter((item) => item.id !== misura.id),
                  )
                }
                className="flex items-center justify-center rounded-lg border border-stroke text-fog disabled:opacity-30"
                aria-label={`Rimuovi misura ${index + 1}`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          {!draft.misure_extra.length && (
            <p className="text-xs text-fog">Nessuna misura aggiuntiva.</p>
          )}
        </div>
      </div>

      <label className="campo-field mt-4">
        <span>Note ambiente</span>
        <textarea
          rows="3"
          value={draft.note}
          disabled={locked}
          placeholder="Stato impianti, materiali, criticità…"
          onChange={(event) => setField("note", event.target.value)}
        />
      </label>
      <DictationHint
        value={draft.note}
        disabled={locked}
        onChange={(value) => setField("note", value)}
      />

      <div className="mt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-display text-xs uppercase text-ink">
              Foto ambiente
            </p>
            <p className="text-[11px] text-fog">
              {(draft.foto_paths?.length || 0) + pendingPhotos.length}/
              {MAX_RILIEVO_PHOTOS} foto · compresse sul dispositivo
            </p>
          </div>
          {!locked && (
            <>
              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                multiple
                className="sr-only"
                disabled={!photosEnabled}
                onChange={addPhotos}
              />
              <button
                type="button"
                disabled={
                  !photosEnabled ||
                  (draft.foto_paths?.length || 0) + pendingPhotos.length >=
                    MAX_RILIEVO_PHOTOS
                }
                onClick={() => inputRef.current?.click()}
                className="flex min-h-11 items-center gap-2 rounded-xl border border-brand/40 px-3 text-xs uppercase text-brand disabled:opacity-40"
              >
                <Camera className="h-4 w-4" /> Scatta o scegli
              </button>
            </>
          )}
        </div>
        {(savedPhotos.length > 0 || pendingPhotos.length > 0) && (
          <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
            {savedPhotos.map((photo) => (
              <img
                key={photo.path}
                src={photo.url}
                alt="Foto salvata dell'ambiente"
                className="aspect-square w-full rounded-xl border border-stroke object-cover"
              />
            ))}
            {pendingPhotos.map((photo) => (
              <PreviewBlob
                key={photo.id}
                photo={photo}
                onRemove={() =>
                  setPendingPhotos((current) =>
                    current.filter((item) => item.id !== photo.id),
                  )
                }
                onAnnotate={() => setAnnotatingPhoto(photo)}
              />
            ))}
          </div>
        )}
        {photoProgress && (
          <p className="mt-2 text-xs text-fog">{photoProgress}</p>
        )}
      </div>

      {!locked && (
        <button
          type="button"
          onClick={() => void persist(true)}
          className="mt-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white"
        >
          <Save className="h-4 w-4" /> Salva adesso
        </button>
      )}
      {annotatingPhoto && (
        <PhotoAnnotatorModal
          photo={annotatingPhoto}
          onClose={() => setAnnotatingPhoto(null)}
          onSave={(annotated) => {
            setPendingPhotos((items) =>
              items.map((item) =>
                item.id === annotated.id ? annotated : item,
              ),
            );
            setAnnotatingPhoto(null);
            setSaveState("modificato");
          }}
        />
      )}
    </section>
  );
}

export default function PrimoRilievo({
  isOnline,
  syncRequest = 0,
  onQueueCountChange,
  onSyncingChange,
}) {
  const { slug } = useTenant();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    ...EMPTY_RILIEVO,
    data_rilievo: localDate(),
  });
  const [surveyDraft, setSurveyDraft] = useState(null);
  const [selectedRoom, setSelectedRoom] = useState("");
  const [activePanel, setActivePanel] = useState("tavola");
  const [queueCount, setQueueCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [offlinePacks, setOfflinePacks] = useState({});
  const [preparingOffline, setPreparingOffline] = useState("");
  const [roomSaveState, setRoomSaveState] = useState("salvato");
  const [tavolaSaveState, setTavolaSaveState] = useState("salvato");
  const surveyLastSaved = useRef("");
  const syncingRef = useRef(false);

  const listQuery = useQuery({
    queryKey: ["campo", "rilievi", slug],
    queryFn: async () => {
      try {
        const data = await mergeRemoteRilievi(slug, await loadRilievi());
        return { data, cached: false };
      } catch (error) {
        const cached = await readCachedRilievi(slug);
        if (cached) return { data: cached, cached: true };
        throw error;
      }
    },
    retry: 1,
    networkMode: "always",
  });
  const rilievi = useMemo(
    () => listQuery.data?.data || [],
    [listQuery.data?.data],
  );

  const detailQuery = useQuery({
    queryKey: ["campo", "rilievo", slug, selectedId],
    enabled: Boolean(selectedId),
    queryFn: async () => {
      const local = await readCachedRilievo(slug, selectedId);
      if (local?.offline_pending) return { data: local, cached: true };
      try {
        const data = await loadRilievo(selectedId);
        await cacheRilievo(slug, data);
        return { data, cached: false };
      } catch (error) {
        const cached = await readCachedRilievo(slug, selectedId);
        if (cached) return { data: cached, cached: true };
        throw error;
      }
    },
    retry: 1,
    networkMode: "always",
  });
  const rilievo = detailQuery.data?.data;

  const appointmentsQuery = useQuery({
    queryKey: ["sopralluoghi", "campo-rilievo", slug],
    queryFn: async () => {
      try {
        const data = (await client.get("/sopralluoghi")).data;
        await cacheRilievoReferences(slug, "sopralluoghi", data);
        return data;
      } catch (error) {
        const cached = await readCachedRilievoReferences(slug, "sopralluoghi");
        if (cached) return cached;
        throw error;
      }
    },
    enabled: creating || isOnline,
    retry: 1,
    networkMode: "always",
  });
  const leadsQuery = useQuery({
    queryKey: ["leads", "campo-rilievo-picker", slug],
    queryFn: async () => {
      try {
        const data = (
          await client.get("/leads", {
            params: { status: "tutti", origine: "tutte" },
          })
        ).data;
        await cacheRilievoReferences(slug, "leads", data);
        return data;
      } catch (error) {
        const cached = await readCachedRilievoReferences(slug, "leads");
        if (cached) return cached;
        throw error;
      }
    },
    enabled: creating || isOnline,
    retry: 1,
    staleTime: 30_000,
    networkMode: "always",
  });
  const leadOptions = useMemo(
    () => normalizeRilievoLeads(leadsQuery.data),
    [leadsQuery.data],
  );

  useEffect(() => {
    let active = true;
    Promise.all(
      rilievi.map(async (item) => [
        item.id,
        await readRilievoOfflinePack(slug, item.id),
      ]),
    ).then((entries) => {
      if (active) setOfflinePacks(Object.fromEntries(entries));
    });
    return () => {
      active = false;
    };
  }, [rilievi, slug]);

  useEffect(() => {
    if (!rilievo?.id) return;
    const next = {
      cliente: rilievo.cliente || "",
      indirizzo: rilievo.indirizzo || "",
      data_rilievo: rilievo.data_rilievo || localDate(),
      tecnico: rilievo.tecnico || "",
      note: rilievo.note || "",
    };
    setSurveyDraft(next);
    surveyLastSaved.current = JSON.stringify(next);
  }, [
    rilievo?.cliente,
    rilievo?.data_rilievo,
    rilievo?.id,
    rilievo?.indirizzo,
    rilievo?.note,
    rilievo?.tecnico,
  ]);

  useEffect(() => {
    const rooms = rilievo?.ambienti || [];
    setSelectedRoom((current) =>
      rooms.some((item) => item.client_uuid === current)
        ? current
        : rooms[0]?.client_uuid || "",
    );
  }, [rilievo?.ambienti]);

  useEffect(() => {
    if (!selectedId || !surveyDraft || rilievo?.stato === "completato")
      return undefined;
    const snapshot = JSON.stringify(surveyDraft);
    if (snapshot === surveyLastSaved.current || !surveyDraft.cliente.trim())
      return undefined;
    const timer = window.setTimeout(async () => {
      try {
        if (isOnline && !rilievo?.offline_pending) {
          const saved = await patchRilievo(selectedId, surveyDraft);
          await upsertCachedRilievo(slug, saved);
          qc.setQueryData(["campo", "rilievo", slug, selectedId], {
            data: saved,
            cached: false,
          });
        } else {
          await enqueueRilievoOperation(slug, {
            kind: "rilievo",
            entity_id: selectedId,
            rilievo_id: selectedId,
            body: surveyDraft,
          });
          const local = {
            ...rilievo,
            ...surveyDraft,
            updated_at: new Date().toISOString(),
          };
          await upsertCachedRilievo(slug, local);
          qc.setQueryData(["campo", "rilievo", slug, selectedId], {
            data: local,
            cached: true,
          });
        }
        surveyLastSaved.current = snapshot;
        setQueueCount((await listRilievoOperations(slug)).length);
      } catch (error) {
        if (isRetryable(error)) {
          await enqueueRilievoOperation(slug, {
            kind: "rilievo",
            entity_id: selectedId,
            rilievo_id: selectedId,
            body: surveyDraft,
          });
          const local = {
            ...rilievo,
            ...surveyDraft,
            updated_at: new Date().toISOString(),
          };
          await upsertCachedRilievo(slug, local);
          qc.setQueryData(["campo", "rilievo", slug, selectedId], {
            data: local,
            cached: true,
          });
          surveyLastSaved.current = snapshot;
          setQueueCount((await listRilievoOperations(slug)).length);
          return;
        }
        toast.error("Scheda rilievo non salvata", {
          description: detailMessage(error),
        });
      }
    }, 900);
    return () => window.clearTimeout(timer);
  }, [
    isOnline,
    qc,
    rilievo,
    rilievo?.offline_pending,
    rilievo?.stato,
    selectedId,
    slug,
    surveyDraft,
  ]);

  const updateCachedRoom = useCallback(
    (saved) => {
      qc.setQueryData(["campo", "rilievo", slug, selectedId], (current) => {
        if (!current?.data) return current;
        const exists = (current.data.ambienti || []).some(
          (item) => item.client_uuid === saved.client_uuid,
        );
        const next = {
          ...current,
          data: {
            ...current.data,
            ambienti: exists
              ? current.data.ambienti.map((item) =>
                  item.client_uuid === saved.client_uuid ? saved : item,
                )
              : [...(current.data.ambienti || []), saved],
          },
        };
        void upsertCachedRilievo(slug, next.data);
        return next;
      });
      void qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
    },
    [qc, selectedId, slug],
  );

  const hideCachedRoom = useCallback(
    (clientUuid) => {
      qc.setQueryData(["campo", "rilievo", slug, selectedId], (current) => {
        if (!current?.data) return current;
        const next = {
          ...current,
          data: {
            ...current.data,
            ambienti: (current.data.ambienti || []).filter(
              (item) => item.client_uuid !== clientUuid,
            ),
          },
        };
        void upsertCachedRilievo(slug, next.data);
        return next;
      });
      setSelectedRoom("");
    },
    [qc, selectedId, slug],
  );

  const updateCachedRilievo = useCallback(
    (saved) => {
      qc.setQueryData(["campo", "rilievo", slug, selectedId], (current) =>
        current?.data ? { ...current, data: saved } : current,
      );
      void upsertCachedRilievo(slug, saved);
      void qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
    },
    [qc, selectedId, slug],
  );

  const flush = useCallback(async () => {
    if (!isOnline || syncingRef.current) return;
    syncingRef.current = true;
    setSyncing(true);
    try {
      const result = await syncRilievoOperations(slug, async (operation) => {
        if (operation.kind === "rilievo-crea") {
          const created = await createRilievo(operation.body);
          await saveRilievoIdResolution(slug, operation.rilievo_id, created.id);
          const promoted = await promoteCachedRilievo(
            slug,
            operation.rilievo_id,
            created,
          );
          qc.setQueryData(["campo", "rilievo", slug, created.id], {
            data: promoted,
            cached: true,
          });
          qc.removeQueries({
            queryKey: ["campo", "rilievo", slug, operation.rilievo_id],
            exact: true,
          });
          setSelectedId((current) =>
            current === operation.rilievo_id ? created.id : current,
          );
          return created;
        }
        const rilievoId = await resolveRilievoId(slug, operation.rilievo_id);
        if (
          operation.kind === "rilievo" ||
          operation.kind === "rilievo-stato"
        ) {
          const saved = await patchRilievo(rilievoId, operation.body);
          await upsertCachedRilievo(slug, saved);
          qc.setQueryData(["campo", "rilievo", slug, rilievoId], {
            data: saved,
            cached: false,
          });
          return saved;
        }
        if (operation.kind === "ambiente-elimina") {
          const result = await archiveRilievoAmbiente(
            rilievoId,
            operation.ambiente_client_uuid,
          );
          const cached = await readCachedRilievo(slug, rilievoId);
          if (cached) {
            await upsertCachedRilievo(slug, {
              ...cached,
              ambienti: (cached.ambienti || []).filter(
                (item) => item.client_uuid !== operation.ambiente_client_uuid,
              ),
            });
          }
          return result;
        }
        if (operation.kind === "tavola") {
          let body = operation.body;
          if (operation.plan_file) {
            body = {
              ...body,
              ...(await uploadRilievoPlan({
                user,
                rilievoId,
                file: operation.plan_file,
                previewBlob: operation.plan_preview,
                assetId: operation.plan_asset_id,
              })),
            };
          }
          if (operation.photos?.length) {
            const paths = await uploadRilievoGeneralPhotos({
              user,
              rilievoId,
              photos: operation.photos,
            });
            body = {
              ...body,
              foto_paths: Array.from(
                new Set([...(body.foto_paths || []), ...paths]),
              ),
            };
          }
          if (operation.plan_file || operation.photos?.length) {
            await replaceRilievoOperation(slug, {
              ...operation,
              body,
              plan_file: null,
              plan_preview: null,
              photos: [],
            });
          }
          const saved = await saveRilievoTavola(rilievoId, body);
          await upsertCachedRilievo(slug, saved);
          return saved;
        }
        let body = operation.body;
        if (operation.photos?.length) {
          const paths = await uploadRilievoPhotos({
            user,
            rilievoId,
            ambienteClientUuid: operation.ambiente_client_uuid,
            photos: operation.photos,
          });
          body = {
            ...body,
            foto_paths: Array.from(
              new Set([...(body.foto_paths || []), ...paths]),
            ),
          };
          await replaceRilievoOperation(slug, {
            ...operation,
            body,
            photos: [],
          });
        }
        const saved = await saveRilievoAmbiente(
          rilievoId,
          operation.ambiente_client_uuid,
          body,
        );
        const cached = await readCachedRilievo(slug, rilievoId);
        if (cached) {
          const exists = (cached.ambienti || []).some(
            (item) => item.client_uuid === saved.client_uuid,
          );
          await upsertCachedRilievo(slug, {
            ...cached,
            ambienti: exists
              ? cached.ambienti.map((item) =>
                  item.client_uuid === saved.client_uuid ? saved : item,
                )
              : [...(cached.ambienti || []), saved],
          });
        }
        return saved;
      });
      setQueueCount((await listRilievoOperations(slug)).length);
      if (result.synced) {
        void qc.invalidateQueries({ queryKey: ["campo", "rilievi"] });
        void qc.invalidateQueries({ queryKey: ["campo", "rilievo"] });
        toast.success(`${result.synced} modifiche rilievo sincronizzate`);
      }
      if (result.failures.length)
        toast.error("Alcune modifiche richiedono un nuovo tentativo");
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [isOnline, qc, slug, user]);

  useEffect(() => {
    listRilievoOperations(slug).then((items) => setQueueCount(items.length));
  }, [slug]);
  useEffect(() => {
    onQueueCountChange?.(queueCount);
  }, [onQueueCountChange, queueCount]);
  useEffect(() => {
    onSyncingChange?.(syncing);
  }, [onSyncingChange, syncing]);
  useEffect(() => {
    if (isOnline && queueCount) void flush();
  }, [flush, isOnline, queueCount]);
  useEffect(() => {
    if (syncRequest > 0 && isOnline && queueCount) void flush();
  }, [flush, isOnline, queueCount, syncRequest]);

  const createMutation = useMutation({
    networkMode: "always",
    mutationFn: async (body) => {
      await requestPersistentOfflineStorage();
      if (isOnline) {
        try {
          const created = await createRilievo(body);
          return {
            created: await upsertCachedRilievo(slug, {
              ...created,
              ambienti: created.ambienti || [],
            }),
            queued: false,
          };
        } catch (error) {
          if (!isRetryable(error)) throw error;
        }
      }
      const local = createOfflineRilievo(body, body.client_uuid);
      await enqueueRilievoOperation(slug, {
        kind: "rilievo-crea",
        entity_id: local.id,
        rilievo_id: local.id,
        local_rilievo_id: local.id,
        body,
      });
      await upsertCachedRilievo(slug, local);
      return { created: local, queued: true };
    },
    onSuccess: async ({ created, queued: wasQueued }) => {
      toast.success(
        wasQueued ? "Rilievo creato sul dispositivo" : "Scheda rilievo creata",
      );
      setCreating(false);
      setCreateForm({ ...EMPTY_RILIEVO, data_rilievo: localDate() });
      setSelectedId(created.id);
      qc.setQueryData(["campo", "rilievo", slug, created.id], {
        data: created,
        cached: wasQueued,
      });
      const list = (await readCachedRilievi(slug)) || [];
      qc.setQueryData(["campo", "rilievi", slug], {
        data: list,
        cached: wasQueued,
      });
      setQueueCount((await listRilievoOperations(slug)).length);
    },
    onError: (error) =>
      toast.error("Rilievo non creato", { description: detailMessage(error) }),
  });

  const selectAppointment = (id) => {
    const item = (appointmentsQuery.data || []).find(
      (appointment) => appointment.id === id,
    );
    setCreateForm((current) =>
      id
        ? {
            ...current,
            sopralluogo_legacy_id: id,
            lead_id: item?.lead_id || "",
            cliente: item?.cliente || current.cliente,
            indirizzo: item?.indirizzo || current.indirizzo,
            data_rilievo: item?.data || current.data_rilievo,
            tecnico: item?.tecnico || current.tecnico,
          }
        : { ...current, sopralluogo_legacy_id: "" },
    );
  };

  const selectLead = (id) =>
    setCreateForm((current) =>
      applyRilievoLeadSelection(current, id, leadOptions),
    );

  const addRoom = async () => {
    if (
      (activePanel === "ambiente" && hasUnsavedEditorState(roomSaveState)) ||
      (activePanel === "tavola" && hasUnsavedEditorState(tavolaSaveState))
    ) {
      toast.error("Salva le modifiche aperte prima di aggiungere un ambiente");
      return;
    }
    const clientUuid = newUuid();
    const newRoom = {
      client_uuid: clientUuid,
      nome: `Ambiente ${(rilievo?.ambienti?.length || 0) + 1}`,
      ordine: rilievo?.ambienti?.length || 0,
      misure_extra: [],
      foto_paths: [],
    };
    try {
      if (isOnline && !rilievo.offline_pending) {
        try {
          const saved = await saveRilievoAmbiente(
            rilievo.id,
            clientUuid,
            newRoom,
          );
          updateCachedRoom(saved);
        } catch (error) {
          if (!isRetryable(error)) throw error;
          await enqueueRilievoOperation(slug, {
            kind: "ambiente",
            entity_id: `${rilievo.id}:${clientUuid}`,
            rilievo_id: rilievo.id,
            ambiente_client_uuid: clientUuid,
            body: newRoom,
            photos: [],
          });
          updateCachedRoom(newRoom);
          setQueueCount((await listRilievoOperations(slug)).length);
        }
      } else {
        await enqueueRilievoOperation(slug, {
          kind: "ambiente",
          entity_id: `${rilievo.id}:${clientUuid}`,
          rilievo_id: rilievo.id,
          ambiente_client_uuid: clientUuid,
          body: newRoom,
          photos: [],
        });
        updateCachedRoom(newRoom);
        setQueueCount((await listRilievoOperations(slug)).length);
      }
      setSelectedRoom(clientUuid);
      setActivePanel("ambiente");
    } catch (error) {
      toast.error("Ambiente non aggiunto", {
        description: detailMessage(error),
      });
    }
  };

  const changeStatus = async (stato) => {
    try {
      if (
        stato === "completato" &&
        [roomSaveState, tavolaSaveState].some(hasUnsavedEditorState)
      ) {
        toast.error("Salva le modifiche aperte prima di completare il rilievo");
        return;
      }
      if (surveyDraft?.cliente?.trim()) {
        await enqueueRilievoOperation(slug, {
          kind: "rilievo",
          entity_id: selectedId,
          rilievo_id: selectedId,
          body: surveyDraft,
        });
      }
      await enqueueRilievoOperation(slug, {
        kind: "rilievo-stato",
        entity_id: selectedId,
        rilievo_id: selectedId,
        body: { stato },
      });
      const updated = {
        ...rilievo,
        ...surveyDraft,
        stato,
        updated_at: new Date().toISOString(),
      };
      await upsertCachedRilievo(slug, updated);
      qc.setQueryData(["campo", "rilievo", slug, selectedId], {
        data: updated,
        cached: true,
      });
      void qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
      setQueueCount((await listRilievoOperations(slug)).length);
      toast.success(
        stato === "completato"
          ? "Completamento salvato sul dispositivo"
          : "Riapertura salvata sul dispositivo",
      );
      if (isOnline) void flush();
    } catch (error) {
      toast.error("Stato non aggiornato", {
        description: detailMessage(error),
      });
    }
  };

  const prepareForOffline = async (rilievoId) => {
    if (!isOnline) {
      toast.error("Collegati a Internet per preparare il sopralluogo");
      return;
    }
    setPreparingOffline(rilievoId);
    try {
      const result = await prepareRilievoOffline({
        tenantSlug: slug,
        rilievoId,
      });
      setOfflinePacks((current) => ({
        ...current,
        [rilievoId]: result.pack,
      }));
      qc.setQueryData(["campo", "rilievo", slug, rilievoId], {
        data: result.rilievo,
        cached: false,
      });
      if (result.failures.length) {
        toast.error("Preparazione offline incompleta", {
          description: `${result.failures.length} allegati non sono stati scaricati. Riprova prima di uscire.`,
        });
      } else {
        toast.success("Sopralluogo pronto per l'uso offline", {
          description: result.storage.persisted
            ? "Dati e allegati sono protetti nella memoria persistente del tablet."
            : "Dati e allegati sono salvati sul tablet.",
        });
      }
    } catch (error) {
      toast.error("Sopralluogo non preparato", {
        description: detailMessage(error),
      });
    } finally {
      setPreparingOffline("");
    }
  };

  const openTavola = () => {
    if (activePanel === "ambiente" && hasUnsavedEditorState(roomSaveState)) {
      toast.error("Salva l'ambiente prima di cambiare sezione");
      return;
    }
    setActivePanel("tavola");
  };

  const openRoom = (clientUuid) => {
    const currentState =
      activePanel === "tavola" ? tavolaSaveState : roomSaveState;
    if (
      hasUnsavedEditorState(currentState) &&
      (activePanel !== "ambiente" || selectedRoom !== clientUuid)
    ) {
      toast.error("Salva le modifiche aperte prima di cambiare ambiente");
      return;
    }
    setSelectedRoom(clientUuid);
    setActivePanel("ambiente");
  };

  if (!selectedId) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-5 lg:py-8">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="campo-eyebrow">Primo sopralluogo</p>
            <h2 className="font-display text-2xl uppercase text-ink">
              Schede rilievo
            </h2>
            <p className="mt-1 text-sm text-fog">
              Ambienti, quote, note e fotografie salvati a distanza.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white"
          >
            <Plus className="h-4 w-4" /> Nuovo rilievo
          </button>
        </div>

        {!isOnline && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-fog">
            <CloudOff className="h-4 w-4 text-amber-400" /> Puoi creare e
            compilare un nuovo rilievo: verra sincronizzato quando torni online.
          </div>
        )}
        {queueCount > 0 && (
          <button
            type="button"
            onClick={flush}
            disabled={!isOnline || syncing}
            className="mb-4 flex w-full items-center justify-center gap-2 rounded-xl border border-brand/40 p-3 text-xs uppercase text-brand disabled:opacity-40"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />{" "}
            {queueCount} modifiche da sincronizzare
          </button>
        )}

        {creating && (
          <section className="mb-5 rounded-2xl border border-brand/40 bg-surface p-4 md:p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-display text-lg uppercase text-ink">
                Nuova scheda rilievo
              </h3>
              <button
                type="button"
                onClick={() => setCreating(false)}
                aria-label="Chiudi"
              >
                <X className="h-5 w-5 text-fog" />
              </button>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="campo-field md:col-span-2">
                <span>
                  Cliente dai lead <em>facoltativo</em>
                </span>
                <select
                  aria-label="Cliente dai lead"
                  value={createForm.lead_id}
                  onChange={(event) => selectLead(event.target.value)}
                >
                  <option value="">Inserimento manuale</option>
                  {leadOptions.map((lead) => (
                    <option key={lead.id} value={lead.id}>
                      {rilievoLeadLabel(lead)}
                    </option>
                  ))}
                </select>
                {leadsQuery.isLoading && (
                  <small className="text-fog">Caricamento lead…</small>
                )}
                {leadsQuery.isError && (
                  <small className="text-red-400">
                    Lead non disponibili. Puoi continuare con l'inserimento
                    manuale.
                  </small>
                )}
                {!leadsQuery.isLoading &&
                  !leadsQuery.isError &&
                  leadOptions.length === 0 && (
                    <small className="text-fog">
                      Nessun lead disponibile: inserisci il cliente manualmente.
                    </small>
                  )}
              </label>
              <label className="campo-field md:col-span-2">
                <span>
                  Sopralluogo prenotato <em>facoltativo</em>
                </span>
                <select
                  value={createForm.sopralluogo_legacy_id}
                  onChange={(event) => selectAppointment(event.target.value)}
                >
                  <option value="">Inserimento manuale</option>
                  {(appointmentsQuery.data || []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.data} · {item.cliente} · {item.indirizzo}
                    </option>
                  ))}
                </select>
              </label>
              <label className="campo-field">
                <span>Cliente</span>
                <input
                  value={createForm.cliente}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      cliente: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="campo-field">
                <span>Indirizzo</span>
                <input
                  value={createForm.indirizzo}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      indirizzo: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="campo-field">
                <span>Data rilievo</span>
                <input
                  type="date"
                  value={createForm.data_rilievo}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      data_rilievo: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="campo-field">
                <span>Tecnico</span>
                <input
                  value={createForm.tecnico}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      tecnico: event.target.value,
                    }))
                  }
                />
              </label>
              <label className="campo-field md:col-span-2">
                <span>Note iniziali</span>
                <textarea
                  rows="3"
                  value={createForm.note}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      note: event.target.value,
                    }))
                  }
                />
              </label>
              <div className="md:col-span-2">
                <DictationHint
                  value={createForm.note}
                  onChange={(value) =>
                    setCreateForm((current) => ({ ...current, note: value }))
                  }
                />
              </div>
            </div>
            <button
              type="button"
              disabled={
                createMutation.isPending || createForm.cliente.trim().length < 2
              }
              onClick={() =>
                createMutation.mutate({
                  ...createForm,
                  client_uuid: newUuid(),
                  lead_id: createForm.lead_id || null,
                  sopralluogo_legacy_id:
                    createForm.sopralluogo_legacy_id || null,
                })
              }
              className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand font-display text-xs uppercase text-white disabled:opacity-40"
            >
              {createMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ClipboardList className="h-4 w-4" />
              )}{" "}
              {isOnline ? "Crea e apri rilievo" : "Crea sul dispositivo"}
            </button>
          </section>
        )}

        {listQuery.isLoading ? (
          <div className="campo-empty">Caricamento rilievi…</div>
        ) : listQuery.isError ? (
          <div className="campo-alert">
            <AlertTriangle />
            <p>{detailMessage(listQuery.error)}</p>
          </div>
        ) : !rilievi.length ? (
          <div className="campo-empty">
            <ClipboardList />
            <strong>Nessun primo rilievo</strong>
            <span>Crea la prima scheda dal sopralluogo.</span>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {rilievi.map((item) => (
              <article
                key={item.id}
                className="rounded-2xl border border-stroke bg-surface p-4 transition-colors hover:border-brand/50"
              >
                <button
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-display text-base uppercase text-ink">
                        {item.cliente}
                      </p>
                      <p className="mt-1 text-xs text-fog">
                        {item.indirizzo || "Indirizzo da completare"}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-1 text-[10px] uppercase ${item.stato === "completato" ? "bg-emerald-500/15 text-success" : "bg-brand/15 text-brand"}`}
                    >
                      {item.stato}
                    </span>
                  </div>
                  <div className="mt-4 flex gap-4 text-xs text-fog">
                    <span>{item.n_ambienti || 0} ambienti</span>
                    <span>{item.n_foto || 0} foto</span>
                    <span>{item.data_rilievo}</span>
                  </div>
                </button>
                <div className="mt-3 flex items-center justify-between gap-2 border-t border-stroke pt-3">
                  <span className="text-[10px] uppercase text-fog">
                    {item.offline_pending
                      ? "Creato sul dispositivo"
                      : isOfflinePackReady(offlinePacks[item.id], item)
                        ? "Pronto offline"
                        : "Solo online"}
                  </span>
                  {!item.offline_pending && (
                    <button
                      type="button"
                      onClick={() => void prepareForOffline(item.id)}
                      disabled={!isOnline || preparingOffline === item.id}
                      className="flex min-h-9 items-center gap-2 rounded-lg border border-brand/40 px-3 text-[10px] uppercase text-brand disabled:opacity-40"
                    >
                      {preparingOffline === item.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                      {isOfflinePackReady(offlinePacks[item.id], item)
                        ? "Aggiorna"
                        : "Prepara"}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
        {listQuery.data?.cached && (
          <p className="mt-4 text-xs text-fog">
            Visualizzazione dalla copia salvata sul dispositivo.
          </p>
        )}
      </main>
    );
  }

  const rooms = rilievo?.ambienti || [];
  const activeRoom = rooms.find((item) => item.client_uuid === selectedRoom);
  const locked = rilievo?.stato === "completato";

  return (
    <main className="mx-auto max-w-6xl px-4 py-5 lg:py-8">
      <button
        type="button"
        onClick={() => {
          if (
            hasUnsavedEditorState(
              activePanel === "tavola" ? tavolaSaveState : roomSaveState,
            )
          ) {
            toast.error("Salva le modifiche prima di chiudere il rilievo");
            return;
          }
          setSelectedId("");
        }}
        className="mb-4 flex items-center gap-1 text-xs uppercase text-fog hover:text-brand"
      >
        <ChevronLeft className="h-4 w-4" /> Tutti i rilievi
      </button>
      {detailQuery.isLoading ? (
        <div className="campo-empty">Caricamento scheda…</div>
      ) : detailQuery.isError && !rilievo ? (
        <div className="campo-alert">
          <AlertTriangle />
          <p>{detailMessage(detailQuery.error)}</p>
        </div>
      ) : !rilievo || !surveyDraft ? (
        <div className="campo-empty">
          Scheda non disponibile sul dispositivo.
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="space-y-4">
            <section className="rounded-2xl border border-stroke bg-surface p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="campo-eyebrow">Scheda rilievo</p>
                  <h2 className="font-display text-xl uppercase text-ink">
                    {surveyDraft.cliente}
                  </h2>
                </div>
                {locked && <CheckCircle2 className="h-5 w-5 text-success" />}
              </div>
              <div className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-stroke bg-bg p-3">
                <span className="text-[10px] uppercase text-fog">
                  {rilievo.offline_pending
                    ? "Rilievo locale in attesa"
                    : isOfflinePackReady(offlinePacks[rilievo.id], rilievo)
                      ? "Pronto offline"
                      : "Allegati non preparati"}
                </span>
                {!rilievo.offline_pending && (
                  <button
                    type="button"
                    onClick={() => void prepareForOffline(rilievo.id)}
                    disabled={!isOnline || preparingOffline === rilievo.id}
                    className="flex min-h-9 items-center gap-1 rounded-lg border border-brand/40 px-2 text-[9px] uppercase text-brand disabled:opacity-40"
                  >
                    {preparingOffline === rilievo.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Download className="h-3.5 w-3.5" />
                    )}
                    Prepara
                  </button>
                )}
              </div>
              <div className="mt-4 space-y-3">
                <label className="campo-field">
                  <span>Cliente</span>
                  <input
                    disabled={locked}
                    value={surveyDraft.cliente}
                    onChange={(event) =>
                      setSurveyDraft((current) => ({
                        ...current,
                        cliente: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="campo-field">
                  <span>Indirizzo</span>
                  <input
                    disabled={locked}
                    value={surveyDraft.indirizzo}
                    onChange={(event) =>
                      setSurveyDraft((current) => ({
                        ...current,
                        indirizzo: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="campo-field">
                  <span>Data</span>
                  <input
                    disabled={locked}
                    type="date"
                    value={surveyDraft.data_rilievo}
                    onChange={(event) =>
                      setSurveyDraft((current) => ({
                        ...current,
                        data_rilievo: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="campo-field">
                  <span>Tecnico</span>
                  <input
                    disabled={locked}
                    value={surveyDraft.tecnico}
                    onChange={(event) =>
                      setSurveyDraft((current) => ({
                        ...current,
                        tecnico: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="campo-field">
                  <span>Note generali</span>
                  <textarea
                    disabled={locked}
                    rows="4"
                    value={surveyDraft.note}
                    onChange={(event) =>
                      setSurveyDraft((current) => ({
                        ...current,
                        note: event.target.value,
                      }))
                    }
                  />
                </label>
                <DictationHint
                  value={surveyDraft.note}
                  disabled={locked}
                  onChange={(value) =>
                    setSurveyDraft((current) => ({
                      ...current,
                      note: value,
                    }))
                  }
                />
              </div>
              {locked ? (
                <button
                  type="button"
                  onClick={() => void changeStatus("bozza")}
                  className="mt-4 min-h-11 w-full rounded-xl border border-brand/40 text-xs uppercase text-brand"
                >
                  Riapri rilievo
                </button>
              ) : (
                <button
                  type="button"
                  disabled={
                    !rooms.length ||
                    [roomSaveState, tavolaSaveState].some(hasUnsavedEditorState)
                  }
                  onClick={() => void changeStatus("completato")}
                  className="mt-4 min-h-11 w-full rounded-xl bg-brand text-xs uppercase text-white disabled:opacity-40"
                >
                  Completa rilievo
                </button>
              )}
              {!isOnline && (
                <p className="mt-2 text-[11px] text-fog">
                  Le modifiche e il completamento vengono salvati sul
                  dispositivo e sincronizzati al ritorno della connessione.
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-stroke bg-surface p-3">
              <button
                type="button"
                onClick={openTavola}
                className={`mb-3 flex w-full items-center gap-3 rounded-xl border p-3 text-left ${activePanel === "tavola" ? "border-brand bg-brand/10" : "border-stroke bg-bg"}`}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-2 text-brand">
                  <MapIcon className="h-4 w-4" />
                </span>
                <span>
                  <b className="block text-sm text-ink">Planimetria e foto</b>
                  <small className="text-fog">
                    Tavola, quote e galleria immobile
                  </small>
                </span>
              </button>
              <div className="flex items-center justify-between px-1 pb-3">
                <div>
                  <p className="font-display text-xs uppercase text-ink">
                    Ambienti
                  </p>
                  <p className="text-[11px] text-fog">
                    {rooms.length} registrati
                  </p>
                </div>
                {!locked && (
                  <button
                    type="button"
                    onClick={addRoom}
                    className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white"
                    aria-label="Aggiungi ambiente"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {rooms.map((room, index) => (
                  <button
                    key={room.client_uuid}
                    type="button"
                    onClick={() => openRoom(room.client_uuid)}
                    className={`flex w-full items-center gap-3 rounded-xl border p-3 text-left ${activePanel === "ambiente" && selectedRoom === room.client_uuid ? "border-brand bg-brand/10" : "border-stroke bg-bg"}`}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-2 font-display text-xs text-brand">
                      {index + 1}
                    </span>
                    <span className="min-w-0">
                      <b className="block truncate text-sm text-ink">
                        {room.nome}
                      </b>
                      <small className="text-fog">
                        {room.superficie
                          ? `${Number(room.superficie).toLocaleString("it-IT")} mq`
                          : "Misure da completare"}{" "}
                        · {(room.foto_paths || []).length} foto
                      </small>
                    </span>
                  </button>
                ))}
              </div>
              {!rooms.length && (
                <div className="campo-empty compact">
                  <Ruler />
                  <span>Aggiungi il primo ambiente.</span>
                </div>
              )}
            </section>
          </aside>

          <div>
            {activePanel === "tavola" ? (
              <RilievoTavola
                rilievo={rilievo}
                user={user}
                slug={slug}
                isOnline={isOnline}
                locked={locked}
                onSaved={updateCachedRilievo}
                onQueueChanged={setQueueCount}
                onSaveStateChange={setTavolaSaveState}
              />
            ) : activeRoom ? (
              <AmbienteEditor
                key={activeRoom.client_uuid}
                rilievo={rilievo}
                ambiente={activeRoom}
                locked={locked}
                isOnline={isOnline}
                user={user}
                slug={slug}
                onSaved={updateCachedRoom}
                onArchived={hideCachedRoom}
                onQueueChanged={setQueueCount}
                onSaveStateChange={setRoomSaveState}
              />
            ) : (
              <div className="campo-empty rounded-2xl border border-stroke bg-surface">
                <Ruler />
                <strong>Seleziona o aggiungi un ambiente</strong>
                <span>Le misure vengono salvate automaticamente.</span>
              </div>
            )}
          </div>
        </div>
      )}
      {queueCount > 0 && (
        <button
          type="button"
          onClick={flush}
          disabled={!isOnline || syncing}
          className="fixed bottom-4 right-4 z-40 flex min-h-12 items-center gap-2 rounded-full bg-brand px-5 text-xs uppercase text-white shadow-2xl disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />{" "}
          {queueCount} da sincronizzare
        </button>
      )}
    </main>
  );
}
