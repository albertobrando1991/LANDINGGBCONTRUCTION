import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  CirclePause,
  Flag,
  HardHat,
  Loader2,
  MapPin,
  MessageCircle,
  Plus,
  Save,
  Trash2,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";
import { buildCantiereWhatsappUrl } from "@/lib/whatsapp";
import CantiereDocuments from "@/dashboard/CantiereDocuments";
import CantierePersonale from "@/dashboard/CantierePersonale";
import CantierePresenze from "@/dashboard/CantierePresenze";
import CantierePortalAccess from "@/dashboard/CantierePortalAccess";
import CantiereQuickPhotoModal from "@/dashboard/CantiereQuickPhotoModal";
import DictationHint from "@/campo/DictationHint";

const DEFAULT_FASI = [
  { nome: "Demolizioni", stato: "da_iniziare" },
  { nome: "Impianti", stato: "da_iniziare" },
  { nome: "Massetti", stato: "da_iniziare" },
  { nome: "Pavimenti", stato: "da_iniziare" },
  { nome: "Finiture", stato: "da_iniziare" },
  { nome: "Consegna", stato: "da_iniziare" },
];

const FASE_META = {
  completata: {
    label: "Completata",
    bar: "bg-emerald-500",
    tile: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  },
  in_corso: {
    label: "In corso",
    bar: "bg-brand",
    tile: "border-brand/50 bg-brand/10 text-brand",
  },
  da_iniziare: {
    label: "Da iniziare",
    bar: "bg-stroke",
    tile: "border-stroke bg-bg text-fog",
  },
};

const FASE_CYCLE = ["da_iniziare", "in_corso", "completata"];

const STATO_META = {
  attivo: {
    label: "Attivo",
    icon: HardHat,
    pill: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  in_pausa: {
    label: "In pausa",
    icon: CirclePause,
    pill: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  },
  completato: {
    label: "Completato",
    icon: CheckCircle2,
    pill: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  },
};

const FILTERS = [
  { value: "attivo", label: "Attivi" },
  { value: "in_pausa", label: "In pausa" },
  { value: "completato", label: "Completati" },
  { value: "tutti", label: "Tutti" },
];

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function initialForm(capocantiere = "") {
  return {
    lead_id: "",
    cliente: "",
    indirizzo: "",
    importo: "",
    avanzamento: 0,
    milestone: "Apertura cantiere",
    milestone_data: todayDate(),
    capocantiere,
    criticita: "",
    stato: "attivo",
    note: "",
  };
}

function clampProgress(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function numberValue(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function dateInputValue(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function formatDateLabel(value) {
  if (!value) return "-";
  const source = String(value).length === 10 ? `${value}T00:00:00` : value;
  const d = new Date(source);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function leadImporto(lead) {
  const basso = numberValue(lead?.range_basso);
  const alto = numberValue(lead?.range_alto);
  return basso || alto ? Math.round((basso + alto) / 2) : "";
}

function cantiereDraft(c) {
  return {
    lead_id: c.lead_id || "",
    cliente: c.cliente || "",
    indirizzo: c.indirizzo || "",
    importo: c.importo ?? "",
    avanzamento: clampProgress(c.avanzamento ?? 0),
    milestone: c.milestone || "",
    milestone_data: dateInputValue(c.milestone_data),
    capocantiere: c.capocantiere || "",
    criticita: c.criticita || "",
    stato: c.stato || "attivo",
    note: c.note || "",
    fasi: (c.fasi?.length ? c.fasi : DEFAULT_FASI).map((f) => ({
      nome: f.nome,
      stato: f.stato || "da_iniziare",
    })),
  };
}

function payloadFromDraft(draft) {
  return {
    lead_id: draft.lead_id || null,
    cliente: draft.cliente.trim(),
    indirizzo: draft.indirizzo.trim(),
    importo: numberValue(draft.importo),
    avanzamento: clampProgress(draft.avanzamento),
    milestone: draft.milestone.trim(),
    milestone_data: draft.milestone_data || null,
    capocantiere: draft.capocantiere.trim(),
    criticita: draft.criticita.trim() || null,
    stato: draft.stato || "attivo",
    note: draft.note?.trim() || "",
    fasi: (draft.fasi?.length ? draft.fasi : DEFAULT_FASI).map((f) => ({
      nome: f.nome,
      stato: f.stato,
    })),
  };
}

export function filterCantieri(
  cantieri,
  { criticalOnly = false, foreman = "", mineOnly = false, userName = "" } = {},
) {
  const normalizedUser = String(userName).trim().toLocaleLowerCase();
  return (cantieri || []).filter((cantiere) => {
    const capocantiere = String(cantiere.capocantiere || "").trim();
    if (criticalOnly && !String(cantiere.criticita || "").trim()) return false;
    if (foreman && capocantiere !== foreman) return false;
    if (mineOnly && capocantiere.toLocaleLowerCase() !== normalizedUser) {
      return false;
    }
    return true;
  });
}

export function CantiereCard({
  cantiere,
  staffNames,
  onSave,
  onAtomicSave,
  onComplete,
  onDelete,
  saving,
  deleting,
  canDelete,
  personale = [],
  assegnazioni = [],
}) {
  const [draft, setDraft] = useState(() => cantiereDraft(cantiere));
  const [saveStatus, setSaveStatus] = useState("salvato");
  const [atomicSaving, setAtomicSaving] = useState(false);
  const [phaseMenu, setPhaseMenu] = useState(null);
  const [phaseAnnouncement, setPhaseAnnouncement] = useState("");
  const [quickPhotoOpen, setQuickPhotoOpen] = useState(false);
  const [documentsRefreshKey, setDocumentsRefreshKey] = useState(0);
  const cantiereRef = useRef(cantiere);
  const draftRef = useRef(draft);
  const dirtyRef = useRef(false);
  const editVersionRef = useRef(0);
  const atomicSavingRef = useRef(false);
  const phasePressRef = useRef(null);
  const suppressPhaseClickRef = useRef(null);
  cantiereRef.current = cantiere;
  draftRef.current = draft;
  const StatoIcon = STATO_META[draft.stato]?.icon || HardHat;
  const busy = saving || deleting || atomicSaving;
  const persistedVersion = `${cantiere.id}:${cantiere.updated_at || ""}`;
  const whatsappUrl = buildCantiereWhatsappUrl(cantiere);

  useEffect(() => {
    if (dirtyRef.current) return;
    const next = cantiereDraft(cantiereRef.current);
    draftRef.current = next;
    setDraft(next);
    setSaveStatus("salvato");
  }, [persistedVersion]);

  useEffect(
    () => () => {
      if (phasePressRef.current?.timer) {
        window.clearTimeout(phasePressRef.current.timer);
      }
    },
    [],
  );

  const updateDraft = (updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      draftRef.current = next;
      return next;
    });
  };

  const setField = (field, value) => {
    dirtyRef.current = true;
    editVersionRef.current += 1;
    setSaveStatus("modificato");
    updateDraft((current) => ({ ...current, [field]: value }));
  };

  const statusAfterAtomicSave = () => {
    setSaveStatus(dirtyRef.current ? "modificato" : "salvato");
  };

  const save = async () => {
    const payload = payloadFromDraft(draftRef.current);
    if (!payload.cliente) {
      toast.error("Cliente obbligatorio");
      return;
    }
    const editVersion = editVersionRef.current;
    setSaveStatus("salvataggio");
    try {
      const result = await onSave(cantiere.id, payload);
      if (editVersionRef.current === editVersion) {
        const saved = result?.data ||
          result || {
            ...cantiereRef.current,
            ...payload,
          };
        const next = cantiereDraft(saved);
        dirtyRef.current = false;
        draftRef.current = next;
        setDraft(next);
        setSaveStatus("salvato");
      } else {
        setSaveStatus("modificato");
      }
    } catch {
      setSaveStatus("modificato");
    }
  };

  const persistPhase = async (index, nextStatus, offerUndo = true) => {
    if (atomicSavingRef.current) return;
    const current = draftRef.current;
    const previousStatus = current.fasi[index]?.stato;
    if (!previousStatus || previousStatus === nextStatus) {
      setPhaseMenu(null);
      return;
    }
    const nextFasi = current.fasi.map((fase, faseIndex) =>
      faseIndex === index ? { ...fase, stato: nextStatus } : fase,
    );
    const phaseName = current.fasi[index].nome;
    updateDraft({ ...current, fasi: nextFasi });
    setPhaseMenu(null);
    setPhaseAnnouncement(
      `${phaseName}, ${FASE_META[nextStatus]?.label || nextStatus}`,
    );
    atomicSavingRef.current = true;
    setAtomicSaving(true);
    setSaveStatus("salvataggio");
    try {
      await onAtomicSave(cantiere.id, { fasi: nextFasi });
      statusAfterAtomicSave();
      toast.success(`${phaseName}: ${FASE_META[nextStatus].label}`, {
        duration: 5000,
        ...(offerUndo
          ? {
              action: {
                label: "Annulla",
                onClick: () => void persistPhase(index, previousStatus, false),
              },
            }
          : {}),
      });
    } catch (error) {
      const latest = draftRef.current;
      updateDraft({
        ...latest,
        fasi: latest.fasi.map((fase, faseIndex) =>
          faseIndex === index && fase.stato === nextStatus
            ? { ...fase, stato: previousStatus }
            : fase,
        ),
      });
      statusAfterAtomicSave();
      toast.error("Stato fase non aggiornato", {
        description: formatApiErrorDetail(
          error?.response?.data?.detail || error?.message,
        ),
      });
    } finally {
      atomicSavingRef.current = false;
      setAtomicSaving(false);
    }
  };

  const cyclePhase = (index) => {
    if (suppressPhaseClickRef.current === index) {
      suppressPhaseClickRef.current = null;
      return;
    }
    const currentStatus = draftRef.current.fasi[index]?.stato;
    const currentIndex = Math.max(0, FASE_CYCLE.indexOf(currentStatus));
    void persistPhase(
      index,
      FASE_CYCLE[(currentIndex + 1) % FASE_CYCLE.length],
    );
  };

  const startPhasePress = (index) => {
    if (busy) return;
    if (phasePressRef.current?.timer) {
      window.clearTimeout(phasePressRef.current.timer);
    }
    phasePressRef.current = {
      index,
      timer: window.setTimeout(() => {
        suppressPhaseClickRef.current = index;
        setPhaseMenu(index);
      }, 550),
    };
  };

  const endPhasePress = () => {
    if (phasePressRef.current?.timer) {
      window.clearTimeout(phasePressRef.current.timer);
    }
    phasePressRef.current = null;
  };

  const persistProgress = async (value) => {
    if (atomicSavingRef.current) return;
    const previous = clampProgress(draftRef.current.avanzamento);
    const next = clampProgress(value);
    if (previous === next) return;
    updateDraft({ ...draftRef.current, avanzamento: next });
    atomicSavingRef.current = true;
    setAtomicSaving(true);
    setSaveStatus("salvataggio");
    try {
      await onAtomicSave(cantiere.id, { avanzamento: next });
      statusAfterAtomicSave();
      toast.success(`Avanzamento aggiornato al ${next}%`);
    } catch (error) {
      const latest = draftRef.current;
      if (clampProgress(latest.avanzamento) === next) {
        updateDraft({ ...latest, avanzamento: previous });
      }
      statusAfterAtomicSave();
      toast.error("Avanzamento non aggiornato", {
        description: formatApiErrorDetail(
          error?.response?.data?.detail || error?.message,
        ),
      });
    } finally {
      atomicSavingRef.current = false;
      setAtomicSaving(false);
    }
  };

  return (
    <article
      data-testid={`cantiere-${cantiere.id}`}
      className="bg-surface border border-stroke rounded-2xl p-5 space-y-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <span className="w-10 h-10 rounded-xl bg-brand/15 text-brand inline-flex items-center justify-center shrink-0">
            <HardHat className="w-5 h-5" />
          </span>
          <div className="min-w-0">
            <input
              value={draft.cliente}
              onChange={(e) => setField("cliente", e.target.value)}
              className="w-full bg-transparent font-display font-bold uppercase text-ink text-sm focus:outline-none focus:text-brand"
              aria-label="Cliente cantiere"
            />
            <div className="font-body text-xs text-fog flex items-center gap-1 mt-1 min-w-0">
              <MapPin className="w-3 h-3 shrink-0" />
              <input
                value={draft.indirizzo}
                onChange={(e) => setField("indirizzo", e.target.value)}
                placeholder="Indirizzo"
                className="w-full bg-transparent text-fog placeholder:text-fog/60 focus:outline-none focus:text-ink"
                aria-label="Indirizzo cantiere"
              />
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setQuickPhotoOpen(true)}
            disabled={busy}
            title="Scatta o carica una foto"
            aria-label="Foto rapida cantiere"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-stroke bg-bg text-fog hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Camera className="h-4 w-4" />
          </button>
          {whatsappUrl ? (
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Invia aggiornamento WhatsApp a ${cantiere.cliente}`}
              title="Invia aggiornamento cantiere su WhatsApp"
              className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
            >
              <MessageCircle className="h-4 w-4" />
            </a>
          ) : (
            <span
              title="Telefono cliente non disponibile"
              className="inline-flex"
            >
              <button
                type="button"
                disabled
                aria-label="WhatsApp non disponibile: telefono cliente mancante"
                className="inline-flex min-h-11 min-w-11 cursor-not-allowed items-center justify-center rounded-xl border border-stroke bg-bg text-fog opacity-40"
              >
                <MessageCircle className="h-4 w-4" />
              </button>
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-display uppercase text-[10px] ${STATO_META[draft.stato]?.pill}`}
          >
            <StatoIcon className="w-3 h-3" />
            {STATO_META[draft.stato]?.label || draft.stato}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">
            Importo
          </span>
          <input
            type="number"
            min="0"
            value={draft.importo}
            onChange={(e) => setField("importo", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          />
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">
            Stato
          </span>
          <select
            value={draft.stato}
            onChange={(e) => setField("stato", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          >
            {Object.entries(STATO_META).map(([key, meta]) => (
              <option key={key} value={key}>
                {meta.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">
            Capocantiere
          </span>
          <select
            value={draft.capocantiere}
            onChange={(e) => setField("capocantiere", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          >
            <option value="">Da assegnare</option>
            {staffNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
            {draft.capocantiere && !staffNames.includes(draft.capocantiere) && (
              <option value={draft.capocantiere}>{draft.capocantiere}</option>
            )}
          </select>
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">
            Data milestone
          </span>
          <input
            type="date"
            value={draft.milestone_data}
            onChange={(e) => setField("milestone_data", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          />
        </label>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <span className="font-display uppercase text-xs text-fog">
            Avanzamento
          </span>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {[-5, 5].map((step) => (
              <button
                key={step}
                type="button"
                disabled={busy}
                onClick={() =>
                  void persistProgress(clampProgress(draft.avanzamento) + step)
                }
                className="min-h-11 rounded-xl border border-stroke bg-bg px-3 font-display text-[10px] text-fog hover:border-brand hover:text-brand disabled:opacity-40"
              >
                {step > 0 ? "+5%" : "-5%"}
              </button>
            ))}
            <button
              type="button"
              disabled={busy || clampProgress(draft.avanzamento) === 100}
              onClick={() => void persistProgress(100)}
              className="min-h-11 rounded-xl border border-brand/40 bg-brand/10 px-3 font-display text-[10px] text-brand disabled:opacity-40"
            >
              100%
            </button>
            <input
              type="number"
              min="0"
              max="100"
              value={draft.avanzamento}
              onChange={(e) =>
                setField("avanzamento", clampProgress(e.target.value))
              }
              className="w-16 bg-bg border border-stroke rounded-lg px-2 py-1 text-right text-ink text-sm focus:outline-none focus:border-brand"
            />
            <span className="font-display text-sm text-ink">%</span>
          </div>
        </div>
        <input
          type="range"
          min="0"
          max="100"
          value={draft.avanzamento}
          onChange={(e) =>
            setField("avanzamento", clampProgress(e.target.value))
          }
          className="w-full touch-none accent-brand"
          aria-label="Avanzamento cantiere"
        />
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full accent-gradient"
            style={{ width: `${clampProgress(draft.avanzamento)}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {draft.fasi.map((fase, index) => (
          <div key={`${fase.nome}-${index}`} className="relative">
            <button
              type="button"
              disabled={busy}
              onPointerDown={() => startPhasePress(index)}
              onPointerUp={endPhasePress}
              onPointerCancel={endPhasePress}
              onPointerLeave={endPhasePress}
              onContextMenu={(event) => {
                event.preventDefault();
                setPhaseMenu(index);
              }}
              onClick={() => cyclePhase(index)}
              aria-haspopup="menu"
              aria-expanded={phaseMenu === index}
              aria-label={`${fase.nome}, ${FASE_META[fase.stato]?.label || fase.stato}, tocca per cambiare stato, tieni premuto per scegliere`}
              className={`flex min-h-14 w-full flex-col justify-center gap-1 rounded-xl border px-3 py-2 text-left transition-colors disabled:opacity-50 ${FASE_META[fase.stato]?.tile || FASE_META.da_iniziare.tile}`}
            >
              <span className="block truncate font-body text-[11px]">
                {fase.nome}
              </span>
              <span className="font-display text-[10px] uppercase">
                {FASE_META[fase.stato]?.label || fase.stato}
              </span>
              <span
                className={`h-1.5 w-full rounded-full ${FASE_META[fase.stato]?.bar || "bg-stroke"}`}
              />
            </button>
            {phaseMenu === index && (
              <div
                role="menu"
                aria-label={`Scegli stato ${fase.nome}`}
                className="absolute inset-x-0 top-full z-40 mt-1 space-y-1 rounded-xl border border-stroke bg-surface p-1.5 shadow-xl"
              >
                {Object.entries(FASE_META).map(([key, meta]) => (
                  <button
                    key={key}
                    type="button"
                    role="menuitem"
                    disabled={busy}
                    onClick={() => void persistPhase(index, key)}
                    className={`min-h-11 w-full rounded-lg px-2 text-left font-display text-[10px] uppercase ${fase.stato === key ? "bg-brand/15 text-brand" : "text-fog hover:bg-bg hover:text-ink"}`}
                  >
                    {meta.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <span className="sr-only" aria-live="polite">
        {phaseAnnouncement}
      </span>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Milestone
            </span>
            <input
              value={draft.milestone}
              aria-label="Milestone cantiere"
              onChange={(e) => setField("milestone", e.target.value)}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <DictationHint
            value={draft.milestone}
            onChange={(value) => setField("milestone", value)}
          />
        </div>
        <div>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Criticita
            </span>
            <input
              value={draft.criticita}
              aria-label="Criticita cantiere"
              onChange={(e) => setField("criticita", e.target.value)}
              placeholder="Nessuna criticita"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm placeholder:text-fog focus:outline-none focus:border-brand"
            />
          </label>
          <DictationHint
            value={draft.criticita}
            onChange={(value) => setField("criticita", value)}
          />
        </div>
      </div>

      <CantiereDocuments
        cantiereId={cantiere.id}
        refreshKey={documentsRefreshKey}
      />
      <CantierePortalAccess cantiereId={cantiere.id} />
      <CantierePersonale
        cantiere={cantiere}
        personale={personale}
        assegnazioni={assegnazioni}
      />
      <CantierePresenze
        cantiere={cantiere}
        personale={personale}
        assegnazioni={assegnazioni}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="font-body text-xs text-fog flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="inline-flex items-center gap-1">
            <Flag className="w-3.5 h-3.5 text-brand" />
            {draft.milestone || "Milestone"}:{" "}
            {formatDateLabel(draft.milestone_data)}
          </span>
          <span className="inline-flex items-center gap-1">
            <User className="w-3.5 h-3.5 text-brand" />
            {draft.capocantiere || "Da assegnare"}
          </span>
          {draft.criticita && (
            <span className="inline-flex items-center gap-1 text-warning">
              <AlertTriangle className="w-3.5 h-3.5" />
              Criticita aperta
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {draft.stato !== "completato" && (
            <button
              type="button"
              onClick={() => onComplete(cantiere.id)}
              disabled={busy}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 font-display uppercase text-[10px] text-fog hover:text-ink hover:border-brand disabled:opacity-60"
            >
              Completa
            </button>
          )}
          {canDelete && (
            <button
              type="button"
              data-testid={`delete-cantiere-${cantiere.id}`}
              onClick={() => {
                if (
                  window.confirm(
                    `Eliminare definitivamente il cantiere di ${draft.cliente}?`,
                  )
                ) {
                  onDelete(cantiere.id);
                }
              }}
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 font-display text-[10px] uppercase text-danger transition-colors hover:bg-danger/20 disabled:opacity-60"
            >
              {deleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Elimina
            </button>
          )}
          <button
            type="button"
            onClick={() => void save()}
            disabled={busy}
            className="bg-brand text-white rounded-xl px-4 py-2 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Salva
          </button>
          <span
            data-testid={`save-status-${cantiere.id}`}
            aria-live="polite"
            className={`rounded-full border px-2.5 py-1 font-display text-[9px] uppercase ${saveStatus === "salvato" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" : saveStatus === "salvataggio" ? "border-brand/30 bg-brand/10 text-brand" : "border-warning/30 bg-warning/10 text-warning"}`}
          >
            {saveStatus === "salvato"
              ? "Salvato"
              : saveStatus === "salvataggio"
                ? "Salvataggio…"
                : "Modifiche non salvate"}
          </span>
        </div>
      </div>
      {quickPhotoOpen && (
        <CantiereQuickPhotoModal
          cantiereId={cantiere.id}
          fasi={draft.fasi}
          onClose={() => setQuickPhotoOpen(false)}
          onUploaded={() => setDocumentsRefreshKey((current) => current + 1)}
        />
      )}
    </article>
  );
}

export default function Cantieri() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [filter, setFilter] = useState("attivo");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [foremanFilter, setForemanFilter] = useState("");
  const [mineOnly, setMineOnly] = useState(false);
  const [form, setForm] = useState(() => initialForm());

  const {
    data: list = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["cantieri", filter],
    queryFn: async () =>
      (await client.get("/cantieri", { params: { stato: filter } })).data,
    refetchInterval: 30000,
  });

  const { data: allCantieri = [] } = useQuery({
    queryKey: ["cantieri", "linked"],
    queryFn: async () =>
      (await client.get("/cantieri", { params: { stato: "tutti" } })).data,
  });

  const { data: staff = [] } = useQuery({
    queryKey: ["staff"],
    queryFn: async () => (await client.get("/staff")).data,
  });

  const { data: wonLeads = [] } = useQuery({
    queryKey: ["leads", "chiuso_vinto"],
    queryFn: async () =>
      (await client.get("/leads", { params: { status: "chiuso_vinto" } })).data,
  });

  const { data: personale = [] } = useQuery({
    queryKey: ["personale"],
    queryFn: async () => (await client.get("/personale")).data,
  });

  const { data: assegnazioni = [] } = useQuery({
    queryKey: ["personale-assegnazioni"],
    queryFn: async () => (await client.get("/personale/assegnazioni")).data,
  });

  const staffNames = useMemo(
    () => staff.map((u) => u.name).filter(Boolean),
    [staff],
  );
  const linkedLeadIds = useMemo(
    () => new Set(allCantieri.map((c) => c.lead_id).filter(Boolean)),
    [allCantieri],
  );
  const availableLeads = useMemo(
    () => wonLeads.filter((lead) => !linkedLeadIds.has(lead.id)),
    [wonLeads, linkedLeadIds],
  );

  useEffect(() => {
    if (!form.capocantiere && staffNames.length > 0) {
      setForm((current) => ({ ...current, capocantiere: staffNames[0] }));
    }
  }, [form.capocantiere, staffNames]);

  const createCantiere = useMutation({
    mutationFn: (body) => client.post("/cantieri", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cantieri"] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      setFilter("attivo");
      setForm(initialForm(staffNames[0] || ""));
      toast.success("Cantiere creato");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const updateCantiere = useMutation({
    mutationFn: async ({ id, body }) =>
      (await client.patch(`/cantieri/${id}`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cantieri"] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Cantiere aggiornato");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const deleteCantiere = useMutation({
    mutationFn: (id) => client.delete(`/cantieri/${id}`),
    onSuccess: (_, deletedId) => {
      qc.setQueriesData({ queryKey: ["cantieri"] }, (current) =>
        Array.isArray(current)
          ? current.filter((cantiere) => cantiere.id !== deletedId)
          : current,
      );
      qc.invalidateQueries({ queryKey: ["cantieri"] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Cantiere eliminato");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const saveAtomicCantiere = async (id, body) => {
    const { data } = await client.patch(`/cantieri/${id}`, body);
    qc.setQueriesData({ queryKey: ["cantieri"] }, (current) =>
      Array.isArray(current)
        ? current.map((cantiere) => (cantiere.id === id ? data : cantiere))
        : current,
    );
    qc.invalidateQueries({ queryKey: ["cantieri"] });
    return data;
  };

  const currentUserName = String(user?.name || "").trim();
  const visibleCantieri = useMemo(
    () =>
      filterCantieri(list, {
        criticalOnly,
        foreman: foremanFilter,
        mineOnly,
        userName: currentUserName,
      }),
    [criticalOnly, currentUserName, foremanFilter, list, mineOnly],
  );

  const stats = useMemo(() => {
    const total = visibleCantieri.length;
    const value = visibleCantieri.reduce(
      (sum, c) => sum + numberValue(c.importo),
      0,
    );
    const avg = total
      ? Math.round(
          visibleCantieri.reduce(
            (sum, c) => sum + numberValue(c.avanzamento),
            0,
          ) / total,
        )
      : 0;
    const critical = visibleCantieri.filter((c) => c.criticita).length;
    return { total, value, avg, critical };
  }, [visibleCantieri]);

  const selectLead = (leadId) => {
    const lead = availableLeads.find((l) => l.id === leadId);
    setForm((current) => ({
      ...current,
      lead_id: leadId,
      cliente: lead?.nome || current.cliente,
      indirizzo: lead?.indirizzo || lead?.citta || current.indirizzo,
      importo: lead ? leadImporto(lead) : current.importo,
      capocantiere: lead?.owner || current.capocantiere,
    }));
  };

  const submit = (e) => {
    e.preventDefault();
    const payload = payloadFromDraft({ ...form, fasi: DEFAULT_FASI });
    if (!payload.cliente) {
      toast.error("Cliente obbligatorio");
      return;
    }
    createCantiere.mutate(payload);
  };

  const savingId = updateCantiere.variables?.id;
  const deletingId = deleteCantiere.variables;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-display font-bold uppercase text-3xl text-ink">
            Cantieri attivi
          </h1>
          <div className="flex flex-wrap gap-2 mt-3">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={`rounded-full border px-4 py-2 font-display uppercase text-[10px] transition-colors ${
                  filter === item.value
                    ? "bg-brand text-white border-brand"
                    : "bg-surface border-stroke text-fog hover:text-ink hover:border-brand"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              aria-pressed={criticalOnly}
              onClick={() => setCriticalOnly((current) => !current)}
              className={`min-h-11 rounded-xl border px-3 font-display text-[10px] uppercase ${criticalOnly ? "border-warning bg-warning/10 text-warning" : "border-stroke bg-surface text-fog hover:border-brand hover:text-ink"}`}
            >
              Con criticità aperte
            </button>
            <select
              value={foremanFilter}
              onChange={(event) => setForemanFilter(event.target.value)}
              aria-label="Filtra per capocantiere"
              className="min-h-11 rounded-xl border border-stroke bg-surface px-3 font-display text-[10px] uppercase text-fog focus:border-brand focus:outline-none"
            >
              <option value="">Tutti i capocantiere</option>
              {staffNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <button
              type="button"
              aria-pressed={mineOnly}
              disabled={!currentUserName}
              onClick={() => setMineOnly((current) => !current)}
              className={`min-h-11 rounded-xl border px-3 font-display text-[10px] uppercase disabled:opacity-40 ${mineOnly ? "border-brand bg-brand/10 text-brand" : "border-stroke bg-surface text-fog hover:border-brand hover:text-ink"}`}
            >
              I miei cantieri
            </button>
          </div>
          {mineOnly && (
            <p className="mt-1 text-[10px] text-fog">
              Filtro basato sul nome assegnato al capocantiere.
            </p>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Metric label="Cantieri" value={stats.total} />
          <Metric label="Media" value={`${stats.avg}%`} />
          <Metric
            label="Criticita"
            value={stats.critical}
            warning={stats.critical > 0}
          />
          <Metric label="Valore" value={formatEuro(stats.value)} />
        </div>
      </div>

      <section className="bg-surface border border-stroke rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Plus className="w-5 h-5 text-brand" />
          <h2 className="font-display font-semibold uppercase text-sm text-ink">
            Nuovo cantiere
          </h2>
        </div>
        <form
          onSubmit={submit}
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3 items-end"
        >
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">
              Lead vinto
            </span>
            <select
              value={form.lead_id}
              onChange={(e) => selectLead(e.target.value)}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            >
              <option value="">Manuale</option>
              {availableLeads.map((lead) => (
                <option key={lead.id} value={lead.id}>
                  {lead.nome} - {lead.citta}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">
              Cliente
            </span>
            <input
              value={form.cliente}
              onChange={(e) =>
                setForm((current) => ({ ...current, cliente: e.target.value }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">
              Indirizzo
            </span>
            <input
              value={form.indirizzo}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  indirizzo: e.target.value,
                }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Importo
            </span>
            <input
              type="number"
              min="0"
              value={form.importo}
              onChange={(e) =>
                setForm((current) => ({ ...current, importo: e.target.value }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Capocantiere
            </span>
            <select
              value={form.capocantiere}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  capocantiere: e.target.value,
                }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            >
              <option value="">Da assegnare</option>
              {staffNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Milestone
            </span>
            <input
              value={form.milestone}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  milestone: e.target.value,
                }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Data
            </span>
            <input
              type="date"
              value={form.milestone_data}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  milestone_data: e.target.value,
                }))
              }
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">
              Criticita
            </span>
            <input
              value={form.criticita}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  criticita: e.target.value,
                }))
              }
              placeholder="Opzionale"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm placeholder:text-fog focus:outline-none focus:border-brand"
            />
          </label>
          <button
            type="submit"
            disabled={createCantiere.isPending}
            className="bg-brand text-white rounded-xl px-4 py-2.5 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {createCantiere.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            Crea
          </button>
        </form>
      </section>

      {isLoading ? (
        <div className="text-fog font-display uppercase animate-pulse">
          Caricamento...
        </div>
      ) : isError ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-5 text-red-400 font-body">
          Impossibile caricare i cantieri.
        </div>
      ) : visibleCantieri.length === 0 ? (
        <div className="bg-surface border border-stroke rounded-2xl p-8 text-center font-body text-fog">
          Nessun cantiere corrisponde ai filtri attivi.
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {visibleCantieri.map((c) => (
            <CantiereCard
              key={c.id}
              cantiere={c}
              staffNames={staffNames}
              saving={updateCantiere.isPending && savingId === c.id}
              deleting={deleteCantiere.isPending && deletingId === c.id}
              canDelete={user?.role === "admin"}
              personale={personale}
              assegnazioni={assegnazioni}
              onSave={(id, body) => updateCantiere.mutateAsync({ id, body })}
              onAtomicSave={saveAtomicCantiere}
              onDelete={(id) => deleteCantiere.mutate(id)}
              onComplete={(id) =>
                updateCantiere.mutate({
                  id,
                  body: { stato: "completato", avanzamento: 100 },
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, warning = false }) {
  return (
    <div className="bg-surface border border-stroke rounded-xl px-4 py-3 min-w-28">
      <div className="font-display uppercase text-[10px] text-fog">{label}</div>
      <div
        className={`font-display font-bold text-lg truncate ${warning ? "text-warning" : "text-ink"}`}
      >
        {value}
      </div>
    </div>
  );
}
