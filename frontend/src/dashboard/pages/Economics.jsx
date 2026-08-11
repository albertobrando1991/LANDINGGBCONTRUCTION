import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import {
  Building2,
  CalendarClock,
  CheckCircle2,
  Download,
  Landmark,
  Loader2,
  Paperclip,
  Pencil,
  Plus,
  ReceiptText,
  TrendingDown,
  TrendingUp,
  WalletCards,
  X,
} from "lucide-react";
import { toast } from "sonner";
import client, { extractErrorDetail } from "@/lib/api";
import {
  ECONOMICS_CATEGORIES,
  FIXED_COST_CATEGORIES,
  filterEconomics,
  isOverdue,
  summarizeFixedMonthlyCosts,
  summarizeMargins,
} from "@/lib/economics";
import {
  canUseTenantStorage,
  createCantiereDocumentUrl,
  displayStorageFilename,
  tenantIdFromUser,
  uploadCantiereDocument,
} from "@/lib/storage";
import { useAuth } from "@/context/AuthContext";
import PaymentControl from "@/dashboard/PaymentControl";

const TABS = [
  "quadro",
  "pagamenti",
  "spese",
  "incassi",
  "scadenze",
  "fornitori",
  "costi fissi",
  "subappalti",
];

function currency(value) {
  return Number(value || 0).toLocaleString("it-IT", {
    style: "currency",
    currency: "EUR",
  });
}

function dateLabel(value) {
  if (!value) return "—";
  return new Date(`${value}T00:00:00`).toLocaleDateString("it-IT");
}

function Metric({ label, value, tone = "ink", note }) {
  const tones = {
    ink: "text-ink",
    brand: "text-brand",
    good: "text-emerald-300",
    bad: "text-red-300",
  };
  return (
    <div className="border-l border-stroke pl-4 first:border-l-0 first:pl-0">
      <p className="text-[10px] font-display uppercase tracking-[0.16em] text-fog">
        {label}
      </p>
      <p className={`mt-1 text-xl font-display ${tones[tone]}`}>{value}</p>
      {note && <p className="mt-1 text-[10px] text-fog">{note}</p>}
    </div>
  );
}

function Status({ children, danger = false, good = false }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-display uppercase tracking-wider ${
        danger
          ? "border-red-500/40 bg-red-500/10 text-red-300"
          : good
            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
            : "border-stroke text-fog"
      }`}
    >
      {children}
    </span>
  );
}

function Field({ label, children, wide = false }) {
  return (
    <label className={`block ${wide ? "md:col-span-2" : ""}`}>
      <span className="text-[10px] font-display uppercase tracking-wider text-fog">
        {label}
      </span>
      {children}
    </label>
  );
}

const inputClass =
  "mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function EntryForm({
  kind,
  cantieri,
  fornitori,
  storageEnabled,
  pending,
  selectedCantiereId,
  onClose,
  onSubmit,
}) {
  const today = new Date().toISOString().slice(0, 10);
  const title = {
    spesa: "Registra spesa",
    incasso: "Registra incasso",
    scadenza: "Nuova scadenza",
    fornitore: "Nuovo fornitore",
  }[kind];
  return (
    <section
      className="rounded-2xl border border-brand/40 bg-surface p-5"
      aria-labelledby="entry-title"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-display uppercase tracking-[0.2em] text-brand">
            Nuovo movimento
          </p>
          <h2
            id="entry-title"
            className="mt-1 text-xl font-display uppercase text-ink"
          >
            {title}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Chiudi modulo"
          className="text-fog hover:text-ink"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <form
        onSubmit={(event) => onSubmit(event, kind)}
        className="mt-5 grid gap-4 md:grid-cols-2"
      >
        {kind !== "fornitore" && (
          <Field label="Cantiere" wide>
            <select
              name="cantiere_id"
              required
              defaultValue={selectedCantiereId}
              className={inputClass}
            >
              <option value="">Seleziona cantiere…</option>
              {cantieri.map((item) => (
                <option key={item.cantiere_id} value={item.cantiere_id}>
                  {item.cliente}
                </option>
              ))}
            </select>
          </Field>
        )}
        {kind === "fornitore" && (
          <>
            <Field label="Ragione sociale" wide>
              <input
                name="ragione_sociale"
                required
                minLength={2}
                className={inputClass}
              />
            </Field>
            <Field label="Partita IVA">
              <input name="piva" className={inputClass} />
            </Field>
            <Field label="Codice fiscale">
              <input name="codice_fiscale" className={inputClass} />
            </Field>
            <Field label="Email">
              <input name="email" type="email" className={inputClass} />
            </Field>
            <Field label="Telefono">
              <input name="telefono" className={inputClass} />
            </Field>
          </>
        )}
        {kind === "spesa" && (
          <>
            <Field label="Fornitore">
              <select name="fornitore_id" className={inputClass}>
                <option value="">Non associato</option>
                {fornitori
                  .filter((item) => item.attivo)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.ragione_sociale}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Categoria">
              <select name="categoria" className={inputClass}>
                {ECONOMICS_CATEGORIES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Descrizione" wide>
              <input
                name="descrizione"
                required
                minLength={2}
                className={inputClass}
              />
            </Field>
            <Field label="Numero documento">
              <input name="numero_documento" className={inputClass} />
            </Field>
            <Field label="Data documento">
              <input
                name="data_documento"
                type="date"
                defaultValue={today}
                required
                className={inputClass}
              />
            </Field>
            <Field label="Imponibile">
              <input
                name="imponibile"
                type="number"
                min="0"
                step="0.01"
                required
                className={inputClass}
              />
            </Field>
            <Field label="IVA %">
              <input
                name="iva_percentuale"
                type="number"
                min="0"
                max="100"
                step="0.01"
                defaultValue="22"
                required
                className={inputClass}
              />
            </Field>
            <Field label="Allegato privato" wide>
              <input
                name="allegato"
                type="file"
                disabled={!storageEnabled}
                accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx"
                className={inputClass}
              />
              {!storageEnabled && (
                <span className="mt-1 block text-[10px] text-fog">
                  Upload disponibile con sessione Supabase staff.
                </span>
              )}
            </Field>
          </>
        )}
        {kind === "incasso" && (
          <>
            <Field label="Descrizione" wide>
              <input
                name="descrizione"
                required
                minLength={2}
                className={inputClass}
              />
            </Field>
            <Field label="Importo">
              <input
                name="importo"
                type="number"
                min="0.01"
                step="0.01"
                required
                className={inputClass}
              />
            </Field>
            <Field label="Data prevista">
              <input
                name="data_prevista"
                type="date"
                defaultValue={today}
                required
                className={inputClass}
              />
            </Field>
            <Field label="Metodo">
              <input
                name="metodo"
                placeholder="Bonifico, assegno…"
                className={inputClass}
              />
            </Field>
          </>
        )}
        {kind === "scadenza" && (
          <>
            <Field label="Tipo">
              <select name="tipo" className={inputClass}>
                <option value="pagamento">Pagamento</option>
                <option value="incasso">Incasso</option>
                <option value="adempimento">Adempimento</option>
              </select>
            </Field>
            <Field label="Data scadenza">
              <input
                name="data_scadenza"
                type="date"
                defaultValue={today}
                required
                className={inputClass}
              />
            </Field>
            <Field label="Titolo" wide>
              <input
                name="titolo"
                required
                minLength={2}
                className={inputClass}
              />
            </Field>
            <Field label="Importo">
              <input
                name="importo"
                type="number"
                min="0"
                step="0.01"
                className={inputClass}
              />
            </Field>
          </>
        )}
        <Field label="Note" wide>
          <textarea name="note" rows={2} className={inputClass} />
        </Field>
        <div className="md:col-span-2 flex justify-end">
          <button
            type="submit"
            disabled={pending}
            className="inline-flex items-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-xs font-display uppercase text-white disabled:opacity-40"
          >
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}{" "}
            Salva
          </button>
        </div>
      </form>
    </section>
  );
}

function FixedCostForm({ item, pending, onClose, onSubmit }) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <section className="rounded-2xl border border-brand/40 bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-display uppercase tracking-[0.2em] text-brand">
            Overhead aziendale
          </p>
          <h2 className="mt-1 text-xl font-display uppercase text-ink">
            {item ? "Modifica costo fisso" : "Nuovo costo fisso"}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Chiudi modulo costo fisso"
          className="min-h-11 min-w-11 rounded-full border border-stroke text-fog"
        >
          <X className="mx-auto h-5 w-5" />
        </button>
      </div>
      <form
        key={item?.id || "new-fixed-cost"}
        onSubmit={(event) => onSubmit(event, item)}
        className="mt-5 grid gap-4 md:grid-cols-2"
      >
        <Field label="Categoria">
          <select
            name="categoria"
            defaultValue={item?.categoria || "altro"}
            className={inputClass}
          >
            {FIXED_COST_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Descrizione">
          <input
            name="descrizione"
            required
            minLength={2}
            defaultValue={item?.descrizione || ""}
            className={inputClass}
          />
        </Field>
        <Field label="Importo mensile">
          <input
            name="importo_mensile"
            type="number"
            min="0"
            step="0.01"
            required
            defaultValue={item?.importo_mensile ?? ""}
            className={inputClass}
          />
        </Field>
        <Field label="Data inizio">
          <input
            name="data_inizio"
            type="date"
            required
            defaultValue={item?.data_inizio || today}
            className={inputClass}
          />
        </Field>
        <Field label="Data fine">
          <input
            name="data_fine"
            type="date"
            defaultValue={item?.data_fine || ""}
            className={inputClass}
          />
        </Field>
        <label className="flex items-end gap-2 pb-2 text-sm text-ink">
          <input
            name="attivo"
            type="checkbox"
            value="true"
            defaultChecked={item?.attivo ?? true}
            className="h-4 w-4 accent-brand"
          />
          Costo attivo
        </label>
        <Field label="Note" wide>
          <textarea
            name="note"
            rows={2}
            defaultValue={item?.note || ""}
            className={inputClass}
          />
        </Field>
        <div className="md:col-span-2 flex justify-end">
          <button
            type="submit"
            disabled={pending}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-5 text-xs font-display uppercase text-white disabled:opacity-40"
          >
            {pending && <Loader2 className="h-4 w-4 animate-spin" />}
            Salva costo fisso
          </button>
        </div>
      </form>
    </section>
  );
}

export default function Economics() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [cantiereId, setCantiereId] = useState("");
  const [tab, setTab] = useState("quadro");
  const [formKind, setFormKind] = useState(null);
  const [fixedCostEditing, setFixedCostEditing] = useState(undefined);
  const storageEnabled = canUseTenantStorage(user);
  const authorized = ["owner", "admin"].includes(user?.role);
  const tenantId = tenantIdFromUser(user);
  const query = useQuery({
    queryKey: ["economics"],
    queryFn: async () => (await client.get("/economics")).data,
    enabled: authorized,
  });
  const fixedCostsQuery = useQuery({
    queryKey: ["economics", "costi-fissi"],
    queryFn: async () => (await client.get("/economics/costi-fissi")).data,
    enabled: authorized,
  });
  const subcontractQuery = useQuery({
    queryKey: ["economics", "subappalti", cantiereId],
    queryFn: async () =>
      (
        await client.get("/economics/subappalti", {
          params: cantiereId ? { cantiere_id: cantiereId } : {},
        })
      ).data,
    enabled: authorized,
  });
  const allData = query.data;
  const data = useMemo(
    () => filterEconomics(allData, cantiereId),
    [allData, cantiereId],
  );
  const summary = useMemo(() => summarizeMargins(data?.cantieri || []), [data]);
  const fixedCosts = useMemo(
    () => fixedCostsQuery.data?.righe || [],
    [fixedCostsQuery.data],
  );
  const fixedMonthlyTotal = useMemo(
    () => summarizeFixedMonthlyCosts(fixedCosts),
    [fixedCosts],
  );

  const refresh = () => qc.invalidateQueries({ queryKey: ["economics"] });
  const create = useMutation({
    mutationFn: async ({ kind, values, file }) => {
      const endpoint = {
        fornitore: "fornitori",
        spesa: "spese",
        incasso: "incassi",
        scadenza: "scadenze",
      }[kind];
      const body = { ...values };
      if (kind === "spesa" && file?.size) {
        const uploaded = await uploadCantiereDocument({
          tenantId,
          cantiereId: values.cantiere_id,
          file,
        });
        body.allegato_path = uploaded.path;
      }
      return (await client.post(`/economics/${endpoint}`, body)).data;
    },
    onSuccess: async () => {
      toast.success("Movimento economico registrato");
      setFormKind(null);
      await refresh();
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail ||
          error.message ||
          "Salvataggio non riuscito",
      ),
  });
  const update = useMutation({
    mutationFn: async ({ group, id, body }) =>
      (await client.patch(`/economics/${group}/${id}`, body)).data,
    onSuccess: async () => {
      toast.success("Stato aggiornato");
      await refresh();
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Aggiornamento non riuscito",
      ),
  });
  const saveFixedCost = useMutation({
    mutationFn: async ({ id, body }) =>
      id
        ? (await client.patch(`/economics/costi-fissi/${id}`, body)).data
        : (await client.post("/economics/costi-fissi", body)).data,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["economics", "costi-fissi"] });
      setFixedCostEditing(undefined);
      toast.success("Costo fisso salvato");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });

  const submit = (event, kind) => {
    event.preventDefault();
    const form = event.currentTarget;
    const raw = Object.fromEntries(new FormData(form));
    const file = form.elements.allegato?.files?.[0];
    const values = Object.fromEntries(
      Object.entries(raw).map(([key, value]) => [
        key,
        value === "" ? null : value,
      ]),
    );
    if (kind === "spesa") {
      values.imponibile = Number(values.imponibile);
      values.iva_percentuale = Number(values.iva_percentuale);
    }
    if (kind === "incasso") values.importo = Number(values.importo);
    if (kind === "scadenza" && values.importo !== null)
      values.importo = Number(values.importo);
    delete values.allegato;
    create.mutate({ kind, values, file });
  };

  const submitFixedCost = (event, item) => {
    event.preventDefault();
    const form = event.currentTarget;
    const raw = Object.fromEntries(new FormData(form));
    const body = {
      categoria: raw.categoria,
      descrizione: raw.descrizione,
      importo_mensile: Number(raw.importo_mensile),
      data_inizio: raw.data_inizio,
      data_fine: raw.data_fine || null,
      attivo: form.elements.attivo.checked,
      note: raw.note || null,
    };
    saveFixedCost.mutate({ id: item?.id, body });
  };

  const downloadCsv = async () => {
    try {
      const response = await client.get("/economics/export.csv", {
        params: cantiereId ? { cantiere_id: cantiereId } : {},
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = cantiereId
        ? "economics-cantiere.csv"
        : "economics-cantieri.csv";
      link.click();
      URL.revokeObjectURL(url);
      toast.success("Export CSV scaricato");
    } catch (error) {
      toast.error(await extractErrorDetail(error));
    }
  };

  const downloadAttachment = async (item) => {
    if (!storageEnabled) {
      toast.error("Download disponibile con sessione Supabase staff");
      return;
    }
    try {
      const downloadName = displayStorageFilename(
        String(item.allegato_path).split("/").pop(),
      );
      const url = await createCantiereDocumentUrl({
        tenantId,
        cantiereId: item.cantiere_id,
        path: item.allegato_path,
        downloadName,
      });
      window.location.assign(url);
    } catch (error) {
      toast.error(error.message || "Allegato non disponibile");
    }
  };

  if (!authorized) return <Navigate to="/dashboard" replace />;

  if (query.isLoading)
    return (
      <div className="py-16 text-center font-display uppercase tracking-widest text-fog">
        Caricamento economics…
      </div>
    );
  if (query.isError || !allData)
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6 text-red-300">
        Impossibile caricare i dati economici.
      </div>
    );

  const costRatio = summary.ricavi_maturati
    ? Math.min(100, (summary.costi_registrati / summary.ricavi_maturati) * 100)
    : 0;
  const marginTone = summary.margine < 0 ? "bad" : "good";

  return (
    <div className="space-y-6" data-testid="economics-page">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-display uppercase tracking-[0.24em] text-brand">
            Controllo di gestione
          </p>
          <h1 className="mt-1 text-3xl font-display font-bold uppercase text-ink">
            Economics cantiere
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-fog">
            SAL maturati, costi registrati, cassa e scadenze in un unico
            registro operativo.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            aria-label="Filtra cantiere"
            value={cantiereId}
            onChange={(event) => setCantiereId(event.target.value)}
            className="rounded-xl border border-stroke bg-surface px-3 py-2 text-sm text-ink"
          >
            <option value="">Tutti i cantieri</option>
            {allData.cantieri.map((item) => (
              <option key={item.cantiere_id} value={item.cantiere_id}>
                {item.cliente}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={downloadCsv}
            className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 text-xs font-display uppercase text-ink"
          >
            <Download className="h-4 w-4" /> CSV
          </button>
        </div>
      </header>

      <section className="overflow-hidden rounded-2xl border border-stroke bg-surface">
        <div className="relative bg-surface-2 p-5 md:p-7">
          <div
            className={`absolute inset-y-0 left-0 w-1 ${summary.margine < 0 ? "bg-red-400" : "bg-emerald-400"}`}
          />
          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <div>
              <p className="flex items-center gap-2 text-[10px] font-display uppercase tracking-[0.2em] text-fog">
                <Landmark className="h-4 w-4" /> Margine maturato
              </p>
              <div
                className={`mt-2 flex items-center gap-3 text-4xl font-display ${summary.margine < 0 ? "text-red-300" : "text-emerald-300"}`}
              >
                {summary.margine < 0 ? (
                  <TrendingDown className="h-7 w-7" />
                ) : (
                  <TrendingUp className="h-7 w-7" />
                )}
                {currency(summary.margine)}
              </div>
              <p className="mt-1 text-xs text-fog">
                {summary.margine_percentuale === null
                  ? "Margine disponibile dopo il primo SAL emesso"
                  : `${summary.margine_percentuale.toFixed(2)}% sui ricavi maturati`}
              </p>
              <div
                className="mt-5 h-2 overflow-hidden rounded-full bg-bg"
                aria-label={`Incidenza costi ${costRatio.toFixed(0)}%`}
              >
                <div
                  className={`h-full ${summary.margine < 0 ? "bg-red-400" : "bg-brand"}`}
                  style={{ width: `${costRatio}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-y-5">
              <Metric
                label="Ricavi SAL"
                value={currency(summary.ricavi_maturati)}
                tone="brand"
              />
              <Metric
                label="Costi"
                value={currency(summary.costi_registrati)}
              />
              <Metric
                label="Incassato"
                value={currency(summary.incassato)}
                tone="good"
              />
              <Metric
                label="Da incassare"
                value={currency(summary.da_incassare)}
                note={`${summary.scadenze_scadute} scadute`}
                tone={summary.scadenze_scadute ? "bad" : "ink"}
              />
            </div>
          </div>
        </div>
      </section>

      <section
        className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5"
        data-testid="fixed-cost-summary"
      >
        <div>
          <p className="flex items-center gap-2 font-display text-[10px] uppercase tracking-[0.18em] text-amber-300">
            <WalletCards className="h-4 w-4" /> Costi fissi aziendali
          </p>
          <p className="mt-2 font-display text-2xl text-ink">
            {currency(fixedMonthlyTotal)} / mese
          </p>
        </div>
        <p className="max-w-md text-xs text-fog">
          Indicatore aziendale separato: non modifica il margine dei singoli
          cantieri.
        </p>
      </section>

      <div className="flex flex-wrap gap-2">
        {[
          { kind: "spesa", label: "Spesa", Icon: ReceiptText },
          { kind: "incasso", label: "Incasso", Icon: Landmark },
          { kind: "scadenza", label: "Scadenza", Icon: CalendarClock },
          { kind: "fornitore", label: "Fornitore", Icon: Building2 },
        ].map(({ kind, label, Icon }) => (
          <button
            key={kind}
            type="button"
            onClick={() => setFormKind(kind)}
            className="inline-flex items-center gap-2 rounded-xl border border-stroke bg-surface px-3 py-2 text-xs font-display uppercase text-ink hover:border-brand/50"
          >
            <Plus className="h-3.5 w-3.5" />
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setFixedCostEditing(null)}
          className="inline-flex items-center gap-2 rounded-xl border border-stroke bg-surface px-3 py-2 text-xs font-display uppercase text-ink hover:border-brand/50"
        >
          <Plus className="h-3.5 w-3.5" />
          <WalletCards className="h-4 w-4" />
          Costo fisso
        </button>
      </div>

      {formKind && (
        <EntryForm
          kind={formKind}
          cantieri={allData.cantieri}
          fornitori={allData.fornitori}
          storageEnabled={storageEnabled}
          selectedCantiereId={cantiereId}
          pending={create.isPending}
          onClose={() => setFormKind(null)}
          onSubmit={submit}
        />
      )}

      {fixedCostEditing !== undefined && (
        <FixedCostForm
          item={fixedCostEditing}
          pending={saveFixedCost.isPending}
          onClose={() => setFixedCostEditing(undefined)}
          onSubmit={submitFixedCost}
        />
      )}

      <div
        className="flex gap-1 overflow-x-auto border-b border-stroke"
        role="tablist"
        aria-label="Sezioni economics"
      >
        {TABS.map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            onClick={() => setTab(item)}
            className={`border-b-2 px-4 py-3 text-xs font-display uppercase tracking-wider ${tab === item ? "border-brand text-brand" : "border-transparent text-fog"}`}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === "quadro" && (
        <div className="grid gap-3 md:grid-cols-2">
          {data.cantieri.map((item) => (
            <article
              key={item.cantiere_id}
              className="rounded-2xl border border-stroke bg-surface p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-display uppercase tracking-wider text-fog">
                    Cantiere
                  </p>
                  <h2 className="mt-1 font-display uppercase text-ink">
                    {item.cliente}
                  </h2>
                </div>
                <Status
                  danger={Number(item.margine) < 0}
                  good={Number(item.margine) >= 0}
                >
                  {Number(item.margine_percentuale || 0).toFixed(1)}%
                </Status>
              </div>
              <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-[10px] uppercase text-fog">SAL</p>
                  <p className="mt-1 text-brand">
                    {currency(item.ricavi_maturati)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-fog">Costi</p>
                  <p className="mt-1 text-ink">
                    {currency(item.costi_registrati)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase text-fog">Margine</p>
                  <p
                    className={`mt-1 ${Number(item.margine) < 0 ? "text-red-300" : "text-emerald-300"}`}
                  >
                    {currency(item.margine)}
                  </p>
                </div>
              </div>
            </article>
          ))}
          {data.cantieri.length === 0 && (
            <p className="col-span-full py-10 text-center text-fog">
              Nessun cantiere disponibile.
            </p>
          )}
        </div>
      )}

      {tab === "pagamenti" && <PaymentControl cantiereId={cantiereId} />}

      {tab === "spese" && (
        <div className="overflow-x-auto rounded-2xl border border-stroke">
          <table className="min-w-[860px] w-full text-sm">
            <thead className="bg-surface-2 text-[10px] font-display uppercase tracking-wider text-fog">
              <tr>
                <th className="px-4 py-3 text-left">Data / documento</th>
                <th className="px-4 py-3 text-left">Fornitore / descrizione</th>
                <th className="px-4 py-3 text-left">Categoria</th>
                <th className="px-4 py-3 text-right">Totale</th>
                <th className="px-4 py-3 text-right">Stato</th>
              </tr>
            </thead>
            <tbody>
              {data.spese.map((item) => (
                <tr key={item.id} className="border-t border-stroke/60">
                  <td className="px-4 py-3 text-fog">
                    {dateLabel(item.data_documento)}
                    <span className="block text-[10px]">
                      {item.numero_documento || "senza numero"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink">
                    {item.fornitore || "Fornitore non associato"}
                    <span className="block text-xs text-fog">
                      {item.descrizione}
                    </span>
                    {item.allegato_path && (
                      <button
                        type="button"
                        onClick={() => downloadAttachment(item)}
                        className="mt-1 inline-flex items-center gap-1 text-[10px] text-brand"
                      >
                        <Paperclip className="h-3.5 w-3.5" /> Allegato
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-fog capitalize">
                    {item.categoria}
                  </td>
                  <td className="px-4 py-3 text-right text-ink">
                    {currency(item.totale)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {item.stato === "registrata" ? (
                      <button
                        type="button"
                        onClick={() =>
                          update.mutate({
                            group: "spese",
                            id: item.id,
                            body: { stato: "pagata" },
                          })
                        }
                        className="text-xs text-brand"
                      >
                        Segna pagata
                      </button>
                    ) : (
                      <Status
                        good={item.stato === "pagata"}
                        danger={item.stato === "annullata"}
                      >
                        {item.stato}
                      </Status>
                    )}
                  </td>
                </tr>
              ))}
              {!data.spese.length && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-fog">
                    Nessuna spesa registrata.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "incassi" && (
        <div className="grid gap-3 md:grid-cols-2">
          {data.incassi.map((item) => (
            <article
              key={item.id}
              className="rounded-2xl border border-stroke bg-surface p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-display uppercase text-ink">
                    {item.descrizione}
                  </p>
                  <p className="mt-1 text-xs text-fog">
                    Previsto {dateLabel(item.data_prevista)}
                    {item.sal_numero ? ` · SAL ${item.sal_numero}` : ""}
                  </p>
                </div>
                <p className="font-display text-lg text-brand">
                  {currency(item.importo)}
                </p>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <Status
                  good={item.stato === "incassato"}
                  danger={item.stato === "annullato"}
                >
                  {item.stato}
                </Status>
                {item.stato === "previsto" && (
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({
                        group: "incassi",
                        id: item.id,
                        body: { stato: "incassato" },
                      })
                    }
                    className="inline-flex items-center gap-1 text-xs text-emerald-300"
                  >
                    <CheckCircle2 className="h-4 w-4" /> Segna incassato
                  </button>
                )}
              </div>
            </article>
          ))}
          {!data.incassi.length && (
            <p className="col-span-full py-10 text-center text-fog">
              Nessun incasso registrato.
            </p>
          )}
        </div>
      )}

      {tab === "scadenze" && (
        <div className="space-y-2">
          {data.scadenze.map((item) => {
            const overdue = isOverdue(item);
            return (
              <article
                key={item.id}
                className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 ${overdue ? "border-red-500/40 bg-red-500/5" : "border-stroke bg-surface"}`}
              >
                <div>
                  <p className="text-[10px] font-display uppercase tracking-wider text-fog">
                    {item.tipo} · {dateLabel(item.data_scadenza)}
                  </p>
                  <h2 className="mt-1 font-display uppercase text-ink">
                    {item.titolo}
                  </h2>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-ink">
                    {item.importo === null ? "" : currency(item.importo)}
                  </span>
                  {item.stato === "aperta" ? (
                    <button
                      type="button"
                      onClick={() =>
                        update.mutate({
                          group: "scadenze",
                          id: item.id,
                          body: { stato: "completata" },
                        })
                      }
                      className={`text-xs ${overdue ? "text-red-300" : "text-brand"}`}
                    >
                      {overdue ? "Scaduta · " : ""}Completa
                    </button>
                  ) : (
                    <Status good={item.stato === "completata"}>
                      {item.stato}
                    </Status>
                  )}
                </div>
              </article>
            );
          })}
          {!data.scadenze.length && (
            <p className="py-10 text-center text-fog">Nessuna scadenza.</p>
          )}
        </div>
      )}

      {tab === "costi fissi" && (
        <div className="space-y-3">
          {fixedCostsQuery.isLoading && (
            <p className="py-10 text-center text-fog">
              Caricamento costi fissi...
            </p>
          )}
          {fixedCostsQuery.isError && (
            <p className="rounded-xl border border-red-500/30 p-4 text-red-300">
              Costi fissi non disponibili.
            </p>
          )}
          {fixedCosts.map((item) => (
            <article
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-stroke bg-surface p-4"
            >
              <div>
                <p className="text-[10px] font-display uppercase tracking-wider text-fog">
                  {String(item.categoria || "altro").replaceAll("_", " ")}
                </p>
                <h2 className="mt-1 font-display uppercase text-ink">
                  {item.descrizione}
                </h2>
                <p className="mt-1 text-xs text-fog">
                  Dal {dateLabel(item.data_inizio)}
                  {item.data_fine
                    ? ` al ${dateLabel(item.data_fine)}`
                    : " · ricorrente"}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="font-display text-lg text-brand">
                    {currency(item.importo_mensile)}
                  </p>
                  <Status good={item.corrente} danger={!item.attivo}>
                    {item.corrente
                      ? "corrente"
                      : item.attivo
                        ? "fuori periodo"
                        : "inattivo"}
                  </Status>
                </div>
                <button
                  type="button"
                  onClick={() => setFixedCostEditing(item)}
                  aria-label={`Modifica costo fisso ${item.descrizione}`}
                  className="min-h-11 min-w-11 rounded-xl border border-stroke text-fog hover:border-brand hover:text-brand"
                >
                  <Pencil className="mx-auto h-4 w-4" />
                </button>
              </div>
            </article>
          ))}
          {!fixedCostsQuery.isLoading && !fixedCosts.length && (
            <p className="py-10 text-center text-fog">
              Nessun costo fisso registrato.
            </p>
          )}
        </div>
      )}

      {tab === "subappalti" && (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric
              label="Subappalti registrati"
              value={currency(subcontractQuery.data?.totale_speso)}
            />
            <Metric
              label="Subappalti pagati"
              value={currency(subcontractQuery.data?.totale_pagato)}
              tone="good"
            />
          </div>
          {subcontractQuery.isLoading ? (
            <p className="py-10 text-center text-fog">
              Caricamento subappalti...
            </p>
          ) : subcontractQuery.isError ? (
            <p className="rounded-xl border border-red-500/30 p-4 text-red-300">
              Aggregazione subappalti non disponibile.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-stroke">
              <table className="min-w-[760px] w-full text-sm">
                <thead className="bg-surface-2 text-[10px] font-display uppercase tracking-wider text-fog">
                  <tr>
                    <th className="px-4 py-3 text-left">Fornitore</th>
                    <th className="px-4 py-3 text-left">Cantiere</th>
                    <th className="px-4 py-3 text-right">Spese</th>
                    <th className="px-4 py-3 text-right">Totale</th>
                    <th className="px-4 py-3 text-right">Pagato</th>
                    <th className="px-4 py-3 text-right">Ultima spesa</th>
                  </tr>
                </thead>
                <tbody>
                  {(subcontractQuery.data?.righe || []).map((item) => {
                    const cantiere = allData.cantieri.find(
                      (row) => row.cantiere_id === item.cantiere_id,
                    );
                    return (
                      <tr
                        key={`${item.fornitore_id}-${item.cantiere_id}`}
                        className="border-t border-stroke/60"
                      >
                        <td className="px-4 py-3 text-ink">
                          {item.ragione_sociale}
                        </td>
                        <td className="px-4 py-3 text-fog">
                          {cantiere?.cliente || item.cantiere_id}
                        </td>
                        <td className="px-4 py-3 text-right text-fog">
                          {item.numero_spese}
                        </td>
                        <td className="px-4 py-3 text-right text-ink">
                          {currency(item.totale_speso)}
                        </td>
                        <td className="px-4 py-3 text-right text-emerald-300">
                          {currency(item.totale_pagato)}
                        </td>
                        <td className="px-4 py-3 text-right text-fog">
                          {dateLabel(item.ultima_spesa)}
                        </td>
                      </tr>
                    );
                  })}
                  {!(subcontractQuery.data?.righe || []).length && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-10 text-center text-fog"
                      >
                        Nessuna spesa di subappalto nel perimetro selezionato.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "fornitori" && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {allData.fornitori.map((item) => (
            <article
              key={item.id}
              className="rounded-2xl border border-stroke bg-surface p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <Building2 className="h-5 w-5 text-brand" />
                <Status good={item.attivo}>
                  {item.attivo ? "attivo" : "archiviato"}
                </Status>
              </div>
              <h2 className="mt-4 font-display uppercase text-ink">
                {item.ragione_sociale}
              </h2>
              <p className="mt-1 text-xs text-fog">
                {item.piva || "P.IVA non indicata"}
              </p>
              <p className="mt-3 text-sm text-fog">
                {item.email || item.telefono || "Contatti non indicati"}
              </p>
            </article>
          ))}
          {!allData.fornitori.length && (
            <p className="col-span-full py-10 text-center text-fog">
              Nessun fornitore.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
