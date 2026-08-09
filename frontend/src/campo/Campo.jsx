import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Camera,
  CheckCircle2,
  Cloud,
  CloudOff,
  Download,
  HardHat,
  Minus,
  Plus,
  RefreshCw,
  Ruler,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  buildCampoMeasurementPayload,
  loadCampoCantieri,
  loadCampoMisure,
  sendCampoMeasurement,
} from "@/lib/campoApi";
import {
  cacheCampoBootstrap,
  cacheCampoMisure,
  enqueueCampoMeasurement,
  isRetryableCampoError,
  listQueuedCampoMeasurements,
  readCampoBootstrap,
  readCampoMisure,
  replaceQueuedCampoMeasurement,
  syncQueuedCampoMeasurements,
} from "@/lib/campoQueue";
import { formatApiErrorDetail } from "@/lib/api";
import {
  compressCampoPhoto,
  MAX_CAMPO_PHOTOS,
  uploadCampoPhotos,
} from "@/lib/campoPhotos";
import { canUseTenantStorage } from "@/lib/storage";
import { useAuth } from "@/context/AuthContext";
import { useTenant } from "@/context/TenantContext";

function localDate() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function clientUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

const EMPTY_FORM = {
  cantiere_id: "",
  computo_voce_id: "",
  mode: "rilievo",
  qta: "",
  data_misura: "",
  descrizione: "",
  parti: "1",
  lunghezza: "",
  larghezza: "",
  altezza: "",
};

function apiDetail(error) {
  return formatApiErrorDetail(error?.response?.data?.detail || error?.message);
}

function formatQuantity(value) {
  return new Intl.NumberFormat("it-IT", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
  }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function PhotoPreview({ photo, onRemove }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const nextUrl = URL.createObjectURL(photo.blob);
    setUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [photo.blob]);
  return (
    <div className="campo-photo-preview">
      {url && <img src={url} alt="Foto pronta per il libretto" />}
      <button type="button" onClick={onRemove} aria-label="Rimuovi foto">
        <X aria-hidden="true" />
      </button>
    </div>
  );
}

export default function Campo() {
  const { slug } = useTenant();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => ({
    ...EMPTY_FORM,
    data_misura: localDate(),
  }));
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const [queued, setQueued] = useState([]);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [installPrompt, setInstallPrompt] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [photoProgress, setPhotoProgress] = useState("");
  const syncingRef = useRef(false);
  const photoInputRef = useRef(null);
  const photosEnabled = canUseTenantStorage(user);

  const bootstrapQuery = useQuery({
    queryKey: ["campo", "cantieri", slug],
    queryFn: async () => {
      try {
        const data = await loadCampoCantieri();
        await cacheCampoBootstrap(slug, data);
        return { data, cached: false };
      } catch (error) {
        const cached = await readCampoBootstrap(slug);
        if (cached) return { data: cached, cached: true };
        throw error;
      }
    },
    retry: 1,
  });
  const cantieri = useMemo(
    () => bootstrapQuery.data?.data || [],
    [bootstrapQuery.data],
  );

  useEffect(() => {
    if (!form.cantiere_id && cantieri.length) {
      setForm((current) => ({
        ...current,
        cantiere_id: cantieri[0].id,
      }));
    }
  }, [cantieri, form.cantiere_id]);

  const selectedCantiere = useMemo(
    () => cantieri.find((item) => item.id === form.cantiere_id),
    [cantieri, form.cantiere_id],
  );
  const selectedVoice = useMemo(
    () =>
      selectedCantiere?.voci?.find((item) => item.id === form.computo_voce_id),
    [selectedCantiere, form.computo_voce_id],
  );

  useEffect(() => {
    const availableVoices = selectedCantiere?.voci || [];
    if (!availableVoices.length) {
      if (form.computo_voce_id) {
        setForm((current) => ({ ...current, computo_voce_id: "" }));
      }
      return;
    }
    if (!availableVoices.some((item) => item.id === form.computo_voce_id)) {
      setForm((current) => ({
        ...current,
        computo_voce_id: availableVoices[0].id,
      }));
    }
  }, [selectedCantiere, form.computo_voce_id]);

  const measuresQuery = useQuery({
    queryKey: ["campo", "misure", slug, form.cantiere_id],
    enabled: Boolean(form.cantiere_id),
    queryFn: async () => {
      try {
        const data = await loadCampoMisure(form.cantiere_id);
        await cacheCampoMisure(slug, form.cantiere_id, data);
        return { data, cached: false };
      } catch (error) {
        const cached = await readCampoMisure(slug, form.cantiere_id);
        if (cached) return { data: cached, cached: true };
        throw error;
      }
    },
    retry: 1,
  });
  const measures = measuresQuery.data?.data || [];

  const refreshQueue = useCallback(async () => {
    const items = await listQueuedCampoMeasurements(slug);
    setQueued(items);
    return items;
  }, [slug]);

  const flushQueue = useCallback(async () => {
    if (!navigator.onLine || syncingRef.current) return;
    syncingRef.current = true;
    setSyncing(true);
    try {
      const result = await syncQueuedCampoMeasurements(async (item) => {
        let body = item.body;
        if (item.photos?.length) {
          const uploadedPaths = await uploadCampoPhotos({
            user,
            cantiereId: item.cantiere_id,
            clientUuid: item.body.client_uuid,
            photos: item.photos,
          });
          body = {
            ...body,
            foto_paths: Array.from(
              new Set([...(body.foto_paths || []), ...uploadedPaths]),
            ),
          };
          await replaceQueuedCampoMeasurement({
            ...item,
            body,
            photos: [],
          });
        }
        return sendCampoMeasurement(item.cantiere_id, body);
      }, slug);
      await refreshQueue();
      if (result.synced) {
        await queryClient.invalidateQueries({ queryKey: ["campo", "misure"] });
        toast.success(
          `${result.synced} ${result.synced === 1 ? "misura sincronizzata" : "misure sincronizzate"}`,
        );
      }
      if (result.failures.length) {
        toast.error(
          `${result.failures.length} misure richiedono un nuovo tentativo`,
        );
      }
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [queryClient, refreshQueue, slug, user]);

  useEffect(() => {
    refreshQueue();
  }, [refreshQueue]);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      flushQueue();
    };
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [flushQueue]);

  useEffect(() => {
    if (isOnline && queued.length) flushQueue();
  }, [flushQueue, isOnline, queued.length]);

  useEffect(() => {
    const manifest = document.querySelector('link[rel="manifest"]');
    const previousManifest = manifest?.getAttribute("href");
    const previousTitle = document.title;
    if (manifest) manifest.setAttribute("href", "/campo.webmanifest");
    document.title = "GB Campo | Libretto di misura";

    const handleInstall = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    window.addEventListener("beforeinstallprompt", handleInstall);
    return () => {
      if (manifest && previousManifest) {
        manifest.setAttribute("href", previousManifest);
      }
      document.title = previousTitle;
      window.removeEventListener("beforeinstallprompt", handleInstall);
    };
  }, []);

  const update = (field, value) => {
    setForm((current) => ({
      ...current,
      [field]: value,
      ...(field === "cantiere_id" ? { computo_voce_id: "" } : {}),
    }));
  };

  const queueMeasurement = async (body, queuedPhotos = []) => {
    await enqueueCampoMeasurement({
      tenant_slug: slug,
      cantiere_id: form.cantiere_id,
      cantiere_label: selectedCantiere?.cliente || "Cantiere",
      voce_label: selectedVoice?.descrizione || "Misura libera",
      body,
      photos: queuedPhotos,
    });
    await refreshQueue();
    toast.success("Misura salvata sul dispositivo", {
      description: "Sara sincronizzata appena torna la connessione.",
    });
  };

  const resetMeasurementFields = () => {
    setForm((current) => ({
      ...EMPTY_FORM,
      cantiere_id: current.cantiere_id,
      computo_voce_id: current.computo_voce_id,
      data_misura: localDate(),
    }));
    setPhotos([]);
    setPhotoProgress("");
    if (photoInputRef.current) photoInputRef.current.value = "";
  };

  const addPhotos = async (event) => {
    const selected = Array.from(event.target.files || []);
    event.target.value = "";
    const available = MAX_CAMPO_PHOTOS - photos.length;
    if (!available) {
      toast.error(`Puoi allegare al massimo ${MAX_CAMPO_PHOTOS} foto`);
      return;
    }
    try {
      const compressed = [];
      for (const file of selected.slice(0, available)) {
        compressed.push(await compressCampoPhoto(file));
      }
      setPhotos((current) => [...current, ...compressed]);
      if (selected.length > available) {
        toast.info(`Sono state mantenute le prime ${MAX_CAMPO_PHOTOS} foto`);
      }
    } catch (error) {
      toast.error("Foto non aggiunta", { description: error.message });
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    const quantity = Number(form.qta);
    if (!form.cantiere_id) {
      toast.error("Seleziona un cantiere");
      return;
    }
    if (!form.computo_voce_id) {
      toast.error("Seleziona una voce di computo confermata", {
        description:
          "Il SAL richiede una voce contrattuale per recuperare unità di misura e prezzo.",
      });
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      toast.error("Inserisci una quantita maggiore di zero");
      return;
    }

    const body = buildCampoMeasurementPayload(form, clientUuid());
    setSaving(true);
    try {
      if (!navigator.onLine) {
        await queueMeasurement(body, photos);
      } else {
        let requestBody = body;
        let queuedPhotos = photos;
        try {
          if (photos.length) {
            const paths = await uploadCampoPhotos({
              user,
              cantiereId: form.cantiere_id,
              clientUuid: body.client_uuid,
              photos,
              onProgress: ({ index, count, uploaded, total }) => {
                const percent = total
                  ? Math.round((uploaded / total) * 100)
                  : 0;
                setPhotoProgress(`Foto ${index + 1}/${count} · ${percent}%`);
              },
            });
            requestBody = { ...body, foto_paths: paths };
            queuedPhotos = [];
          }
          await sendCampoMeasurement(form.cantiere_id, requestBody);
          toast.success(
            form.mode === "rettifica"
              ? "Rettifica registrata"
              : "Misura registrata",
          );
          await queryClient.invalidateQueries({
            queryKey: ["campo", "misure", slug, form.cantiere_id],
          });
        } catch (error) {
          if (!isRetryableCampoError(error)) throw error;
          await queueMeasurement(requestBody, queuedPhotos);
        }
      }
      resetMeasurementFields();
    } catch (error) {
      toast.error("Misura non salvata", { description: apiDetail(error) });
    } finally {
      setSaving(false);
    }
  };

  const install = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    setInstallPrompt(null);
  };

  const error = bootstrapQuery.error || measuresQuery.error;

  return (
    <div className="campo-shell min-h-screen bg-bg text-ink">
      <header className="campo-header sticky top-0 z-40 border-b border-stroke bg-bg/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              to="/dashboard"
              aria-label="Torna alla dashboard"
              className="campo-icon-button"
            >
              <ArrowLeft aria-hidden="true" />
            </Link>
            <div className="min-w-0">
              <div className="font-display text-[10px] uppercase tracking-[0.28em] text-brand">
                GB Construction
              </div>
              <h1 className="truncate font-display text-xl font-bold uppercase tracking-wide">
                Libretto di campo
              </h1>
            </div>
          </div>
          {installPrompt && (
            <button type="button" onClick={install} className="campo-install">
              <Download aria-hidden="true" />
              <span>Installa</span>
            </button>
          )}
        </div>

        <div
          className={`campo-sync-rail ${isOnline ? "is-online" : "is-offline"}`}
        >
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-2">
            <div className="flex min-w-0 items-center gap-2" aria-live="polite">
              {isOnline ? (
                <Cloud aria-hidden="true" />
              ) : (
                <CloudOff aria-hidden="true" />
              )}
              <span className="font-display text-[11px] font-semibold uppercase tracking-[0.16em]">
                {isOnline ? "Online" : "Modalita offline"}
              </span>
              <span className="text-fog">·</span>
              <span className="truncate font-body text-[11px] text-fog">
                {syncing
                  ? "Sincronizzazione…"
                  : queued.length
                    ? `${queued.length} in attesa`
                    : "Tutto sincronizzato"}
              </span>
            </div>
            <button
              type="button"
              onClick={flushQueue}
              disabled={!isOnline || syncing || !queued.length}
              className="campo-sync-button"
              aria-label="Sincronizza misure in attesa"
            >
              <RefreshCw
                className={syncing ? "animate-spin" : ""}
                aria-hidden="true"
              />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-5 px-4 py-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)] lg:py-8">
        <section className="campo-panel" aria-labelledby="nuova-misura-title">
          <div className="campo-panel-heading">
            <div>
              <p className="campo-eyebrow">Rilievo rapido</p>
              <h2 id="nuova-misura-title">Nuova misura</h2>
            </div>
            <Ruler aria-hidden="true" />
          </div>

          {bootstrapQuery.isLoading ? (
            <div className="campo-empty" role="status">
              Caricamento cantieri…
            </div>
          ) : bootstrapQuery.isError ? (
            <div className="campo-alert" role="alert">
              <AlertTriangle aria-hidden="true" />
              <div>
                <strong>Accesso al libretto non disponibile</strong>
                <p>{apiDetail(bootstrapQuery.error)}</p>
              </div>
            </div>
          ) : !cantieri.length ? (
            <div className="campo-empty">
              <HardHat aria-hidden="true" />
              <strong>Nessun cantiere operativo</strong>
              <span>Attiva un cantiere dalla dashboard per iniziare.</span>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <label className="campo-field">
                <span>Cantiere</span>
                <select
                  value={form.cantiere_id}
                  onChange={(event) =>
                    update("cantiere_id", event.target.value)
                  }
                  required
                >
                  {cantieri.map((cantiere) => (
                    <option key={cantiere.id} value={cantiere.id}>
                      {cantiere.cliente}
                      {cantiere.indirizzo ? ` — ${cantiere.indirizzo}` : ""}
                    </option>
                  ))}
                </select>
                {selectedCantiere && (
                  <small>
                    {selectedCantiere.stato === "in_pausa"
                      ? "In pausa"
                      : "Attivo"}
                    {selectedCantiere.capocantiere
                      ? ` · ${selectedCantiere.capocantiere}`
                      : ""}
                  </small>
                )}
              </label>

              <label className="campo-field">
                <span>Voce di computo per il SAL</span>
                <select
                  value={form.computo_voce_id}
                  onChange={(event) =>
                    update("computo_voce_id", event.target.value)
                  }
                  required
                  disabled={!selectedCantiere?.voci?.length}
                >
                  <option value="">Seleziona una voce confermata</option>
                  {(selectedCantiere?.voci || []).map((voce) => (
                    <option key={voce.id} value={voce.id}>
                      {voce.descrizione} · {voce.um}
                    </option>
                  ))}
                </select>
                {selectedVoice && (
                  <small>
                    Contratto: {formatQuantity(selectedVoice.qta_contrattuale)}{" "}
                    {selectedVoice.um}
                  </small>
                )}
                {selectedCantiere && !selectedCantiere.voci?.length && (
                  <small className="text-red-600">
                    Nessuna voce disponibile: collega e conferma un computo per
                    questo cantiere prima di registrare misure destinate al SAL.
                  </small>
                )}
              </label>

              <fieldset>
                <legend className="campo-legend">Tipo registrazione</legend>
                <div className="campo-mode-grid">
                  <button
                    type="button"
                    aria-pressed={form.mode === "rilievo"}
                    onClick={() => update("mode", "rilievo")}
                    className={form.mode === "rilievo" ? "is-active" : ""}
                  >
                    <Plus aria-hidden="true" /> Rilievo
                  </button>
                  <button
                    type="button"
                    aria-pressed={form.mode === "rettifica"}
                    onClick={() => update("mode", "rettifica")}
                    className={
                      form.mode === "rettifica" ? "is-active is-negative" : ""
                    }
                  >
                    <Minus aria-hidden="true" /> Rettifica
                  </button>
                </div>
              </fieldset>

              <div className="campo-measure-row">
                <label className="campo-field campo-quantity">
                  <span>Quantita</span>
                  <div>
                    <span aria-hidden="true">
                      {form.mode === "rettifica" ? "−" : "+"}
                    </span>
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0.001"
                      step="0.001"
                      value={form.qta}
                      onChange={(event) => update("qta", event.target.value)}
                      placeholder="0,000"
                      required
                    />
                    <b>{selectedVoice?.um || "u"}</b>
                  </div>
                </label>
                <label className="campo-field">
                  <span>Data</span>
                  <input
                    type="date"
                    value={form.data_misura}
                    onChange={(event) =>
                      update("data_misura", event.target.value)
                    }
                    required
                  />
                </label>
              </div>

              <label className="campo-field">
                <span>
                  Descrizione <em>facoltativa</em>
                </span>
                <textarea
                  rows="3"
                  maxLength="1000"
                  value={form.descrizione}
                  onChange={(event) =>
                    update("descrizione", event.target.value)
                  }
                  placeholder="Es. parete cucina, tratto lato nord…"
                />
              </label>

              <div className="campo-photo-field">
                <div>
                  <span>
                    Foto <em>facoltative</em>
                  </span>
                  <small>
                    {photosEnabled
                      ? "Compresse sul dispositivo e caricate con ripresa automatica."
                      : "Disponibili con accesso Supabase interno."}
                  </small>
                </div>
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  capture="environment"
                  multiple
                  onChange={addPhotos}
                  disabled={!photosEnabled || photos.length >= MAX_CAMPO_PHOTOS}
                />
                <button
                  type="button"
                  onClick={() => photoInputRef.current?.click()}
                  disabled={!photosEnabled || photos.length >= MAX_CAMPO_PHOTOS}
                  className="campo-photo-button"
                >
                  <Camera aria-hidden="true" />
                  Scatta o scegli foto
                </button>
                {photos.length > 0 && (
                  <div className="campo-photo-grid">
                    {photos.map((photo) => (
                      <PhotoPreview
                        key={photo.id}
                        photo={photo}
                        onRemove={() =>
                          setPhotos((current) =>
                            current.filter((item) => item.id !== photo.id),
                          )
                        }
                      />
                    ))}
                  </div>
                )}
                {photoProgress && (
                  <small aria-live="polite">{photoProgress}</small>
                )}
              </div>

              <details className="campo-details">
                <summary>Dettaglio dimensioni</summary>
                <div className="campo-dimensions">
                  <label className="campo-field">
                    <span>Parti</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min="1"
                      step="1"
                      value={form.parti}
                      onChange={(event) => update("parti", event.target.value)}
                    />
                  </label>
                  {[
                    ["lunghezza", "Lunghezza"],
                    ["larghezza", "Larghezza"],
                    ["altezza", "Altezza"],
                  ].map(([field, label]) => (
                    <label className="campo-field" key={field}>
                      <span>{label}</span>
                      <input
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="0.001"
                        value={form[field]}
                        onChange={(event) => update(field, event.target.value)}
                        placeholder="m"
                      />
                    </label>
                  ))}
                </div>
              </details>

              <button
                type="submit"
                disabled={saving || !form.computo_voce_id}
                className="campo-submit"
              >
                {saving ? (
                  <RefreshCw className="animate-spin" aria-hidden="true" />
                ) : isOnline ? (
                  <CheckCircle2 aria-hidden="true" />
                ) : (
                  <CloudOff aria-hidden="true" />
                )}
                {saving
                  ? "Salvataggio…"
                  : isOnline
                    ? "Registra misura"
                    : "Salva sul dispositivo"}
              </button>
            </form>
          )}
        </section>

        <aside className="space-y-5">
          {queued.length > 0 && (
            <section
              className="campo-panel campo-queue"
              aria-labelledby="queue-title"
            >
              <div className="campo-panel-heading compact">
                <div>
                  <p className="campo-eyebrow">Coda dispositivo</p>
                  <h2 id="queue-title">Da sincronizzare</h2>
                </div>
                <span>{queued.length}</span>
              </div>
              <div className="campo-list">
                {queued.map((item) => (
                  <article
                    key={item.body.client_uuid}
                    className="campo-list-row"
                  >
                    <div>
                      <strong>{item.voce_label}</strong>
                      <span>
                        {item.cantiere_label} ·{" "}
                        {formatDate(item.body.data_misura)}
                      </span>
                    </div>
                    <b
                      className={Number(item.body.qta) < 0 ? "is-negative" : ""}
                    >
                      {Number(item.body.qta) > 0 ? "+" : ""}
                      {formatQuantity(item.body.qta)}
                    </b>
                  </article>
                ))}
              </div>
            </section>
          )}

          <section className="campo-panel" aria-labelledby="recenti-title">
            <div className="campo-panel-heading compact">
              <div>
                <p className="campo-eyebrow">Ultime registrazioni</p>
                <h2 id="recenti-title">Misure recenti</h2>
              </div>
              {measuresQuery.data?.cached && (
                <span className="campo-cache-tag">Cache</span>
              )}
            </div>

            {measuresQuery.isLoading ? (
              <div className="campo-empty compact" role="status">
                Caricamento misure…
              </div>
            ) : error && !measures.length ? (
              <div className="campo-alert" role="alert">
                <AlertTriangle aria-hidden="true" />
                <p>{apiDetail(error)}</p>
              </div>
            ) : !form.cantiere_id || !measures.length ? (
              <div className="campo-empty compact">
                <Ruler aria-hidden="true" />
                <span>Nessuna misura registrata per questo cantiere.</span>
              </div>
            ) : (
              <div className="campo-list">
                {measures.map((misura) => (
                  <article key={misura.id} className="campo-list-row">
                    <div>
                      <strong>
                        {misura.computo_voce_descrizione ||
                          misura.descrizione ||
                          "Misura libera"}
                      </strong>
                      <span>
                        {formatDate(misura.data_misura)}
                        {misura.descrizione ? ` · ${misura.descrizione}` : ""}
                      </span>
                    </div>
                    <b className={Number(misura.qta) < 0 ? "is-negative" : ""}>
                      {Number(misura.qta) > 0 ? "+" : ""}
                      {formatQuantity(misura.qta)}{" "}
                      {misura.computo_voce_um || ""}
                    </b>
                  </article>
                ))}
              </div>
            )}
          </section>

          {(bootstrapQuery.data?.cached || measuresQuery.data?.cached) && (
            <p className="campo-offline-note">
              <CloudOff aria-hidden="true" /> Stai consultando l'ultima copia
              disponibile sul dispositivo.
            </p>
          )}
        </aside>
      </main>
    </div>
  );
}
