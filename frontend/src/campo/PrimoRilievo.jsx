import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ClipboardList,
  CloudOff,
  Loader2,
  Map as MapIcon,
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
  cacheRilievi,
  cacheRilievo,
  enqueueRilievoOperation,
  listRilievoOperations,
  readCachedRilievi,
  readCachedRilievo,
  syncRilievoOperations,
} from "@/lib/rilievoQueue";
import {
  compressCampoPhoto,
  createRilievoPhotoUrls,
  MAX_RILIEVO_PHOTOS,
  uploadRilievoGeneralPhotos,
  uploadRilievoPhotos,
} from "@/lib/campoPhotos";
import { uploadRilievoPlan } from "@/lib/rilievoAssets";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";
import {
  applyRilievoLeadSelection,
  normalizeRilievoLeads,
  rilievoLeadLabel,
} from "./rilievoLeadSelection";
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

function optionalNumber(value) {
  if (value === "" || value == null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function detailMessage(error) {
  return formatApiErrorDetail(error?.response?.data?.detail || error?.message);
}

function isRetryable(error) {
  const status = error?.response?.status;
  return !error?.response || status === 408 || status === 429 || status >= 500;
}

function PreviewBlob({ photo, onRemove }) {
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
}) {
  const [draft, setDraft] = useState(null);
  const [pendingPhotos, setPendingPhotos] = useState([]);
  const [savedPhotos, setSavedPhotos] = useState([]);
  const [saveState, setSaveState] = useState("salvato");
  const [photoProgress, setPhotoProgress] = useState("");
  const inputRef = useRef(null);
  const savingRef = useRef(false);
  const lastSavedRef = useRef("");
  const photosEnabled = Boolean(user && user !== false);

  useEffect(() => {
    const next = {
      nome: ambiente.nome || "Nuovo ambiente",
      tipologia: ambiente.tipologia || "",
      piano: ambiente.piano || "",
      ordine: Number(ambiente.ordine || 0),
      lunghezza: ambiente.lunghezza ?? "",
      larghezza: ambiente.larghezza ?? "",
      altezza: ambiente.altezza ?? "",
      superficie: ambiente.superficie ?? "",
      misure_extra: Array.isArray(ambiente.misure_extra)
        ? ambiente.misure_extra
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
    createRilievoPhotoUrls(draft?.foto_paths || [], rilievo.id)
      .then((items) => active && setSavedPhotos(items))
      .catch(() => active && setSavedPhotos([]));
    return () => {
      active = false;
    };
  }, [draft?.foto_paths, rilievo.id]);

  const payload = useMemo(() => {
    if (!draft) return null;
    const length = optionalNumber(draft.lunghezza);
    const width = optionalNumber(draft.larghezza);
    const manualSurface = optionalNumber(draft.superficie);
    return {
      nome: String(draft.nome || "").trim(),
      tipologia: String(draft.tipologia || "").trim() || null,
      piano: String(draft.piano || "").trim() || null,
      ordine: Number(draft.ordine || 0),
      lunghezza: length,
      larghezza: width,
      altezza: optionalNumber(draft.altezza),
      superficie:
        manualSurface ??
        (length != null && width != null
          ? Number((length * width).toFixed(3))
          : null),
      misure_extra: (draft.misure_extra || [])
        .filter((item) => item.etichetta?.trim() && item.valore !== "")
        .map((item) => ({
          id: item.id,
          etichetta: item.etichetta.trim(),
          valore: Number(item.valore),
          unita: item.unita || "m",
        })),
      note: String(draft.note || "").trim() || null,
      foto_paths: draft.foto_paths || [],
    };
  }, [draft]);

  const persist = useCallback(
    async (showToast = false) => {
      if (!payload?.nome || savingRef.current || locked) return;
      savingRef.current = true;
      setSaveState(isOnline ? "salvataggio" : "in_attesa");
      try {
        let body = payload;
        let queuedPhotos = pendingPhotos;
        if (isOnline) {
          try {
            const uploaded = await uploadRilievoPhotos({
              user,
              rilievoId: rilievo.id,
              ambienteClientUuid: ambiente.client_uuid,
              photos: pendingPhotos,
              onProgress: ({ index, count, uploaded: done, total }) =>
                setPhotoProgress(
                  `Foto ${index + 1}/${count} · ${total ? Math.round((done / total) * 100) : 0}%`,
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
        savingRef.current = false;
      }
    },
    [
      ambiente.client_uuid,
      draft,
      isOnline,
      locked,
      onSaved,
      payload,
      pendingPhotos,
      rilievo.id,
      slug,
      user,
    ],
  );

  useEffect(() => {
    if (!draft || locked || !payload?.nome) return undefined;
    const snapshot = JSON.stringify({
      draft,
      pending: pendingPhotos.map((photo) => photo.id),
    });
    if (snapshot === lastSavedRef.current) return undefined;
    setSaveState("modificato");
    const timer = window.setTimeout(() => void persist(false), 1100);
    return () => window.clearTimeout(timer);
  }, [draft, locked, payload?.nome, pendingPhotos, persist]);

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
      const compressed = [];
      for (const file of files.slice(0, available)) {
        compressed.push(await compressCampoPhoto(file));
      }
      setPendingPhotos((current) => [...current, ...compressed]);
    } catch (error) {
      toast.error("Foto non aggiunta", { description: error.message });
    }
  };

  const archive = async () => {
    if (!window.confirm(`Rimuovere l'ambiente “${draft.nome}” dal rilievo?`))
      return;
    try {
      if (isOnline) {
        await archiveRilievoAmbiente(rilievo.id, ambiente.client_uuid);
      } else {
        await enqueueRilievoOperation(slug, {
          kind: "ambiente-elimina",
          entity_id: `${rilievo.id}:${ambiente.client_uuid}`,
          rilievo_id: rilievo.id,
          ambiente_client_uuid: ambiente.client_uuid,
        });
      }
      onArchived(ambiente.client_uuid);
      toast.success(
        isOnline ? "Ambiente rimosso" : "Rimozione salvata sul dispositivo",
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
              type="number"
              inputMode="decimal"
              min="0"
              step="0.001"
              value={draft[field]}
              disabled={locked}
              onChange={(event) => setField(field, event.target.value)}
            />
          </label>
        ))}
      </div>

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
              <input
                aria-label={`Valore misura ${index + 1}`}
                type="number"
                inputMode="decimal"
                min="0"
                step="0.001"
                className="rounded-lg border border-stroke bg-surface px-2 text-sm text-ink"
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
    </section>
  );
}

export default function PrimoRilievo({ isOnline }) {
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
  const surveyLastSaved = useRef("");

  const listQuery = useQuery({
    queryKey: ["campo", "rilievi", slug],
    queryFn: async () => {
      try {
        const data = await loadRilievi();
        await cacheRilievi(slug, data);
        return { data, cached: false };
      } catch (error) {
        const cached = await readCachedRilievi(slug);
        if (cached) return { data: cached, cached: true };
        throw error;
      }
    },
    retry: 1,
  });
  const rilievi = listQuery.data?.data || [];

  const detailQuery = useQuery({
    queryKey: ["campo", "rilievo", selectedId],
    enabled: Boolean(selectedId),
    queryFn: async () => {
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
  });
  const rilievo = detailQuery.data?.data;

  const appointmentsQuery = useQuery({
    queryKey: ["sopralluoghi", "campo-rilievo"],
    queryFn: async () => (await client.get("/sopralluoghi")).data,
    enabled: creating && isOnline,
    retry: 1,
  });
  const leadsQuery = useQuery({
    queryKey: ["leads", "campo-rilievo-picker"],
    queryFn: async () =>
      (
        await client.get("/leads", {
          params: { status: "tutti", origine: "tutte" },
        })
      ).data,
    enabled: creating && isOnline,
    retry: 1,
    staleTime: 30_000,
  });
  const leadOptions = useMemo(
    () => normalizeRilievoLeads(leadsQuery.data),
    [leadsQuery.data],
  );

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
        if (isOnline) {
          await patchRilievo(selectedId, surveyDraft);
        } else {
          await enqueueRilievoOperation(slug, {
            kind: "rilievo",
            entity_id: selectedId,
            rilievo_id: selectedId,
            body: surveyDraft,
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
  }, [isOnline, rilievo?.stato, selectedId, slug, surveyDraft]);

  const updateCachedRoom = useCallback(
    (saved) => {
      qc.setQueryData(["campo", "rilievo", selectedId], (current) => {
        if (!current?.data) return current;
        const exists = (current.data.ambienti || []).some(
          (item) => item.client_uuid === saved.client_uuid,
        );
        return {
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
      });
      void qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
    },
    [qc, selectedId, slug],
  );

  const hideCachedRoom = useCallback(
    (clientUuid) => {
      qc.setQueryData(["campo", "rilievo", selectedId], (current) =>
        current?.data
          ? {
              ...current,
              data: {
                ...current.data,
                ambienti: (current.data.ambienti || []).filter(
                  (item) => item.client_uuid !== clientUuid,
                ),
              },
            }
          : current,
      );
      setSelectedRoom("");
    },
    [qc, selectedId],
  );

  const updateCachedRilievo = useCallback(
    (saved) => {
      qc.setQueryData(["campo", "rilievo", selectedId], (current) =>
        current?.data ? { ...current, data: saved } : current,
      );
      void cacheRilievo(slug, saved);
      void qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
    },
    [qc, selectedId, slug],
  );

  const flush = useCallback(async () => {
    if (!isOnline || syncing) return;
    setSyncing(true);
    try {
      const result = await syncRilievoOperations(slug, async (operation) => {
        if (operation.kind === "rilievo") {
          return patchRilievo(operation.rilievo_id, operation.body);
        }
        if (operation.kind === "ambiente-elimina") {
          return archiveRilievoAmbiente(
            operation.rilievo_id,
            operation.ambiente_client_uuid,
          );
        }
        if (operation.kind === "tavola") {
          let body = operation.body;
          if (operation.plan_file) {
            body = {
              ...body,
              ...(await uploadRilievoPlan({
                user,
                rilievoId: operation.rilievo_id,
                file: operation.plan_file,
                previewBlob: operation.plan_preview,
              })),
            };
          }
          if (operation.photos?.length) {
            const paths = await uploadRilievoGeneralPhotos({
              user,
              rilievoId: operation.rilievo_id,
              photos: operation.photos,
            });
            body = {
              ...body,
              foto_paths: Array.from(
                new Set([...(body.foto_paths || []), ...paths]),
              ),
            };
          }
          return saveRilievoTavola(operation.rilievo_id, body);
        }
        let body = operation.body;
        if (operation.photos?.length) {
          const paths = await uploadRilievoPhotos({
            user,
            rilievoId: operation.rilievo_id,
            ambienteClientUuid: operation.ambiente_client_uuid,
            photos: operation.photos,
          });
          body = {
            ...body,
            foto_paths: Array.from(
              new Set([...(body.foto_paths || []), ...paths]),
            ),
          };
        }
        return saveRilievoAmbiente(
          operation.rilievo_id,
          operation.ambiente_client_uuid,
          body,
        );
      });
      setQueueCount((await listRilievoOperations(slug)).length);
      if (result.synced) {
        await qc.invalidateQueries({ queryKey: ["campo", "rilievi"] });
        await qc.invalidateQueries({ queryKey: ["campo", "rilievo"] });
        toast.success(`${result.synced} modifiche rilievo sincronizzate`);
      }
      if (result.failures.length)
        toast.error("Alcune modifiche richiedono un nuovo tentativo");
    } finally {
      setSyncing(false);
    }
  }, [isOnline, qc, slug, syncing, user]);

  useEffect(() => {
    listRilievoOperations(slug).then((items) => setQueueCount(items.length));
  }, [slug]);
  useEffect(() => {
    if (isOnline && queueCount) void flush();
  }, [flush, isOnline, queueCount]);

  const createMutation = useMutation({
    mutationFn: (body) => createRilievo(body),
    onSuccess: async (created) => {
      toast.success("Scheda rilievo creata");
      setCreating(false);
      setCreateForm({ ...EMPTY_RILIEVO, data_rilievo: localDate() });
      await qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
      setSelectedId(created.id);
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
    const clientUuid = newUuid();
    const newRoom = {
      client_uuid: clientUuid,
      nome: `Ambiente ${(rilievo?.ambienti?.length || 0) + 1}`,
      ordine: rilievo?.ambienti?.length || 0,
      misure_extra: [],
      foto_paths: [],
    };
    try {
      if (isOnline) {
        const saved = await saveRilievoAmbiente(
          rilievo.id,
          clientUuid,
          newRoom,
        );
        updateCachedRoom(saved);
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
      const updated = await patchRilievo(selectedId, { stato });
      await cacheRilievo(slug, updated);
      qc.setQueryData(["campo", "rilievo", selectedId], {
        data: updated,
        cached: false,
      });
      await qc.invalidateQueries({ queryKey: ["campo", "rilievi", slug] });
      toast.success(
        stato === "completato" ? "Rilievo completato" : "Rilievo riaperto",
      );
    } catch (error) {
      toast.error("Stato non aggiornato", {
        description: detailMessage(error),
      });
    }
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
            disabled={!isOnline}
            className="flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 font-display text-xs uppercase text-white disabled:opacity-40"
          >
            <Plus className="h-4 w-4" /> Nuovo rilievo
          </button>
        </div>

        {!isOnline && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-fog">
            <CloudOff className="h-4 w-4 text-amber-400" /> Puoi consultare i
            rilievi salvati; la creazione richiede una prima connessione.
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
              Crea e apri rilievo
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
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedId(item.id)}
                className="rounded-2xl border border-stroke bg-surface p-4 text-left transition-colors hover:border-brand/50"
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
        onClick={() => setSelectedId("")}
        className="mb-4 flex items-center gap-1 text-xs uppercase text-fog hover:text-brand"
      >
        <ChevronLeft className="h-4 w-4" /> Tutti i rilievi
      </button>
      {detailQuery.isLoading || !rilievo || !surveyDraft ? (
        <div className="campo-empty">Caricamento scheda…</div>
      ) : detailQuery.isError ? (
        <div className="campo-alert">
          <AlertTriangle />
          <p>{detailMessage(detailQuery.error)}</p>
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
                  disabled={!isOnline || !rooms.length}
                  onClick={() => void changeStatus("completato")}
                  className="mt-4 min-h-11 w-full rounded-xl bg-brand text-xs uppercase text-white disabled:opacity-40"
                >
                  Completa rilievo
                </button>
              )}
              {!isOnline && (
                <p className="mt-2 text-[11px] text-fog">
                  Le modifiche vengono salvate sul dispositivo. Completa quando
                  torni online.
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-stroke bg-surface p-3">
              <button
                type="button"
                onClick={() => setActivePanel("tavola")}
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
                    onClick={() => {
                      setSelectedRoom(room.client_uuid);
                      setActivePanel("ambiente");
                    }}
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
