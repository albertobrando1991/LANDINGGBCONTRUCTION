import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CalendarRange,
  CheckCircle2,
  ClipboardList,
  HardHat,
  Loader2,
  Plus,
  ReceiptText,
  Ruler,
  Smartphone,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import {
  azioneStatoSal,
  periodoMensile,
  riepilogoSal,
  SAL_STATI,
} from "@/lib/sal";

function currency(value) {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(Number(value || 0));
}

function dateLabel(value) {
  if (!value) return "—";
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function quantity(value) {
  return new Intl.NumberFormat("it-IT", {
    maximumFractionDigits: 3,
  }).format(Number(value || 0));
}

function Metric({ label, value, warning = false }) {
  return (
    <div className="min-w-0 border-l border-stroke pl-4 first:border-l-0 first:pl-0">
      <p className="font-display text-[9px] uppercase tracking-[0.18em] text-fog">
        {label}
      </p>
      <p
        className={`mt-1 truncate font-display text-xl font-bold ${
          warning ? "text-warning" : "text-ink"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function StatusPill({ stato }) {
  const meta = SAL_STATI[stato] || SAL_STATI.bozza;
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 font-display text-[9px] uppercase tracking-[0.16em] ${meta.tone}`}
    >
      {meta.label}
    </span>
  );
}

function SalRow({ item, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`group relative w-full overflow-hidden rounded-2xl border p-4 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-brand/60 ${
        active
          ? "border-brand bg-brand/10"
          : "border-stroke bg-surface hover:border-brand/60 hover:bg-surface-2"
      }`}
    >
      <span
        className={`absolute inset-y-0 left-0 w-1 ${
          item.contiene_eccedenze ? "bg-warning" : "bg-brand"
        }`}
        aria-hidden="true"
      />
      <div className="flex items-start justify-between gap-3 pl-2">
        <div className="min-w-0">
          <p className="font-display text-[10px] uppercase tracking-[0.2em] text-fog">
            Stato avanzamento
          </p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="font-display text-3xl font-bold text-ink">
              {String(item.numero).padStart(2, "0")}
            </span>
            <span className="font-display text-xs uppercase text-fog">SAL</span>
          </div>
        </div>
        <StatusPill stato={item.stato} />
      </div>
      <div className="mt-4 grid grid-cols-[1fr_auto] items-end gap-3 pl-2">
        <div className="min-w-0">
          <p className="truncate font-body text-xs text-fog">
            {dateLabel(item.periodo_da)} — {dateLabel(item.periodo_a)}
          </p>
          {item.contiene_eccedenze && (
            <p className="mt-1 inline-flex items-center gap-1 font-body text-xs text-warning">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
              Eccedenza da verificare
            </p>
          )}
        </div>
        <p className="font-display text-base font-bold text-ink">
          {currency(item.totale_periodo)}
        </p>
      </div>
    </button>
  );
}

function EmptyDetail() {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center rounded-2xl border border-dashed border-stroke bg-surface/40 px-6 text-center">
      <ReceiptText className="h-9 w-9 text-brand" aria-hidden="true" />
      <h2 className="mt-4 font-display text-sm font-semibold uppercase text-ink">
        Seleziona un SAL
      </h2>
      <p className="mt-2 max-w-sm font-body text-sm text-fog">
        Apri una registrazione per consultare quantità, prezzi ed eventuali
        eccedenze rispetto al computo confermato.
      </p>
    </div>
  );
}

function SalDetail({ sal, loading, onTransition, transitioning }) {
  if (loading) {
    return (
      <div className="flex min-h-72 items-center justify-center rounded-2xl border border-stroke bg-surface">
        <Loader2
          className="h-6 w-6 animate-spin text-brand"
          aria-label="Caricamento SAL"
        />
      </div>
    );
  }
  if (!sal) return <EmptyDetail />;
  const action = azioneStatoSal(sal.stato);

  return (
    <section className="overflow-hidden rounded-2xl border border-stroke bg-surface">
      <div className="relative border-b border-stroke bg-surface-2 p-5 md:p-6">
        <span
          className={`absolute inset-x-0 top-0 h-1 ${
            sal.contiene_eccedenze ? "bg-warning" : "bg-brand"
          }`}
          aria-hidden="true"
        />
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-display text-[10px] uppercase tracking-[0.22em] text-brand">
              Registro economico
            </p>
            <h2 className="mt-1 font-display text-2xl font-bold uppercase text-ink">
              SAL {String(sal.numero).padStart(2, "0")}
            </h2>
            <p className="mt-2 font-body text-sm text-fog">
              {dateLabel(sal.periodo_da)} — {dateLabel(sal.periodo_a)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill stato={sal.stato} />
            {action && (
              <button
                type="button"
                onClick={() => onTransition(action.stato)}
                disabled={transitioning}
                className="inline-flex items-center gap-2 rounded-xl bg-brand px-3.5 py-2 font-display text-[10px] uppercase tracking-wider text-white disabled:opacity-60"
              >
                {transitioning ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                {action.label}
              </button>
            )}
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-stroke pt-4 sm:grid-cols-3">
          <Metric
            label="Importo periodo"
            value={currency(sal.totale_periodo)}
          />
          <Metric label="Voci misurate" value={sal.righe?.length || 0} />
          <Metric
            label="Eccedenze"
            value={(sal.righe || []).filter((row) => row.in_eccedenza).length}
            warning={sal.contiene_eccedenze}
          />
        </div>
      </div>

      <div className="divide-y divide-stroke">
        {(sal.righe || []).map((row) => (
          <article key={row.id} className="p-5 md:p-6">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <div className="flex items-start gap-2">
                  <Ruler
                    className="mt-0.5 h-4 w-4 shrink-0 text-brand"
                    aria-hidden="true"
                  />
                  <h3 className="break-words font-display text-sm font-semibold uppercase text-ink">
                    {row.descrizione}
                  </h3>
                </div>
                <p className="mt-2 pl-6 font-body text-xs text-fog">
                  {currency(row.prezzo_unitario)} / {row.um}
                </p>
              </div>
              <p className="shrink-0 font-display text-lg font-bold text-ink">
                {currency(row.importo_periodo)}
              </p>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 pl-0 md:pl-6">
              <Quantity label="Periodo" value={row.qta_periodo} unit={row.um} />
              <Quantity
                label="Progressiva"
                value={row.qta_progressiva}
                unit={row.um}
              />
              <Quantity
                label="Contratto"
                value={row.qta_contrattuale}
                unit={row.um}
              />
            </div>
            {row.in_eccedenza && (
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5 text-warning md:ml-6">
                <AlertTriangle
                  className="mt-0.5 h-4 w-4 shrink-0"
                  aria-hidden="true"
                />
                <p className="font-body text-xs">
                  Eccedenza di {quantity(row.eccedenza_qta)} {row.um}. Valuta
                  l’apertura di una variante prima dell’approvazione.
                </p>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function Quantity({ label, value, unit }) {
  return (
    <div className="min-w-0 rounded-xl bg-bg px-3 py-2.5">
      <p className="font-display text-[8px] uppercase tracking-wider text-fog">
        {label}
      </p>
      <p className="mt-1 truncate font-display text-sm font-semibold text-ink">
        {quantity(value)} <span className="text-[10px] text-fog">{unit}</span>
      </p>
    </div>
  );
}

export default function Sal() {
  const qc = useQueryClient();
  const [cantiereId, setCantiereId] = useState("");
  const [salId, setSalId] = useState("");
  const [periodo, setPeriodo] = useState(() => periodoMensile());

  const cantieriQuery = useQuery({
    queryKey: ["campo-cantieri"],
    queryFn: async () => (await client.get("/campo/cantieri")).data,
  });
  const cantieri = useMemo(
    () => cantieriQuery.data || [],
    [cantieriQuery.data],
  );

  useEffect(() => {
    if (!cantieri.length) {
      setCantiereId("");
      return;
    }
    if (!cantieri.some((item) => item.id === cantiereId)) {
      setCantiereId(cantieri[0].id);
      setSalId("");
    }
  }, [cantieri, cantiereId]);

  const selectedCantiere = useMemo(
    () => cantieri.find((item) => item.id === cantiereId),
    [cantieri, cantiereId],
  );

  const salQuery = useQuery({
    queryKey: ["sal", cantiereId],
    queryFn: async () => (await client.get(`/cantieri/${cantiereId}/sal`)).data,
    enabled: Boolean(cantiereId),
  });
  const salItems = useMemo(() => salQuery.data || [], [salQuery.data]);
  const summary = useMemo(() => riepilogoSal(salItems), [salItems]);

  useEffect(() => {
    if (!salItems.length) {
      setSalId("");
      return;
    }
    if (!salItems.some((item) => item.id === salId)) setSalId(salItems[0].id);
  }, [salItems, salId]);

  const detailQuery = useQuery({
    queryKey: ["sal-detail", salId],
    queryFn: async () => (await client.get(`/sal/${salId}`)).data,
    enabled: Boolean(salId),
  });

  const createSal = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/cantieri/${cantiereId}/sal`, {
          periodo_da: periodo.periodo_da,
          periodo_a: periodo.periodo_a,
        })
      ).data,
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["sal", cantiereId] });
      qc.setQueryData(["sal-detail", created.id], created);
      setSalId(created.id);
      toast.success(`SAL ${created.numero} generato dal libretto`);
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });

  const transitionSal = useMutation({
    mutationFn: async (stato) =>
      (await client.patch(`/sal/${salId}/stato`, { stato })).data,
    onSuccess: (updated) => {
      qc.setQueryData(["sal-detail", updated.id], updated);
      qc.invalidateQueries({ queryKey: ["sal", cantiereId] });
      toast.success(`SAL ${updated.numero}: ${SAL_STATI[updated.stato].label}`);
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });

  const submit = (event) => {
    event.preventDefault();
    if (!cantiereId) return;
    if (!periodo.periodo_da || !periodo.periodo_a) {
      toast.error("Inserisci entrambe le date del periodo");
      return;
    }
    if (periodo.periodo_da > periodo.periodo_a) {
      toast.error("La data iniziale non può superare la data finale");
      return;
    }
    createSal.mutate();
  };

  return (
    <div className="space-y-6" data-testid="sal-page">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.24em] text-brand">
            Contabilità di cantiere
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold uppercase text-ink">
            Stati avanzamento lavori
          </h1>
          <p className="mt-2 max-w-2xl font-body text-sm text-fog">
            Genera ogni SAL dalle misure registrate sul campo. Quantità e prezzi
            vengono congelati nel documento economico.
          </p>
        </div>
        <Link
          to="/campo"
          className="inline-flex w-fit items-center gap-2 rounded-xl border border-stroke bg-surface px-4 py-2.5 font-display text-[10px] uppercase tracking-wider text-fog hover:border-brand hover:text-ink"
        >
          <Smartphone className="h-4 w-4 text-brand" /> Apri modalità campo
        </Link>
      </header>

      <section className="rounded-2xl border border-stroke bg-surface p-4 md:p-5">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric label="SAL generati" value={summary.totale} />
          <Metric label="Maturato" value={currency(summary.maturato)} />
          <Metric label="Approvati" value={summary.approvati} />
          <Metric
            label="Con eccedenze"
            value={summary.eccedenze}
            warning={summary.eccedenze > 0}
          />
        </div>
      </section>

      <section className="rounded-2xl border border-stroke bg-surface p-5">
        <div className="mb-4 flex items-center gap-2">
          <Plus className="h-5 w-5 text-brand" aria-hidden="true" />
          <h2 className="font-display text-sm font-semibold uppercase text-ink">
            Genera dal libretto
          </h2>
        </div>
        <form
          onSubmit={submit}
          className="grid grid-cols-1 items-end gap-3 md:grid-cols-2 xl:grid-cols-[2fr_1fr_1fr_auto]"
        >
          <label className="space-y-1">
            <span className="font-display text-[10px] uppercase text-fog">
              Cantiere
            </span>
            <select
              value={cantiereId}
              onChange={(event) => {
                setCantiereId(event.target.value);
                setSalId("");
              }}
              disabled={cantieriQuery.isLoading || cantieri.length === 0}
              className="w-full rounded-xl border border-stroke bg-bg px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none disabled:opacity-60"
            >
              {cantieri.length === 0 && (
                <option value="">Nessun cantiere operativo</option>
              )}
              {cantieri.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.cliente} · {item.indirizzo || "Senza indirizzo"}
                </option>
              ))}
            </select>
          </label>
          <DateField
            label="Dal"
            value={periodo.periodo_da}
            onChange={(value) =>
              setPeriodo((current) => ({ ...current, periodo_da: value }))
            }
          />
          <DateField
            label="Al"
            value={periodo.periodo_a}
            onChange={(value) =>
              setPeriodo((current) => ({ ...current, periodo_a: value }))
            }
          />
          <button
            type="submit"
            disabled={!cantiereId || createSal.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 font-display text-[10px] uppercase tracking-wider text-white disabled:opacity-60"
          >
            {createSal.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ClipboardList className="h-4 w-4" />
            )}
            Genera SAL
          </button>
        </form>
        {selectedCantiere && (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-stroke pt-4 font-body text-xs text-fog">
            <span className="inline-flex items-center gap-1.5">
              <HardHat className="h-3.5 w-3.5 text-brand" />
              {selectedCantiere.stato === "in_pausa"
                ? "Cantiere in pausa"
                : "Cantiere attivo"}
            </span>
            <span>
              {selectedCantiere.voci?.length || 0} voci confermate disponibili
            </span>
          </div>
        )}
      </section>

      {cantieriQuery.isError ? (
        <ErrorPanel message="Impossibile caricare i cantieri operativi." />
      ) : cantieriQuery.isLoading ? (
        <LoadingPanel label="Caricamento cantieri" />
      ) : cantieri.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stroke bg-surface p-8 text-center">
          <HardHat className="mx-auto h-9 w-9 text-brand" />
          <h2 className="mt-4 font-display text-sm font-semibold uppercase text-ink">
            Nessun cantiere operativo
          </h2>
          <p className="mt-2 font-body text-sm text-fog">
            Crea un cantiere e collega un computo confermato prima di generare
            il SAL.
          </p>
          <Link
            to="/dashboard/cantieri"
            className="mt-4 inline-flex items-center gap-2 font-display text-[10px] uppercase tracking-wider text-brand"
          >
            Vai ai cantieri <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.5fr)]">
          <section aria-labelledby="sal-register-title">
            <div className="mb-3 flex items-center justify-between">
              <h2
                id="sal-register-title"
                className="font-display text-xs font-semibold uppercase tracking-wider text-ink"
              >
                Registro SAL
              </h2>
              <span className="font-body text-xs text-fog">
                {salItems.length} documenti
              </span>
            </div>
            {salQuery.isLoading ? (
              <LoadingPanel label="Caricamento registro" compact />
            ) : salQuery.isError ? (
              <ErrorPanel message="Impossibile caricare il registro SAL." />
            ) : salItems.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-stroke bg-surface p-6 text-center">
                <CalendarRange className="mx-auto h-8 w-8 text-brand" />
                <p className="mt-3 font-body text-sm text-fog">
                  Nessun SAL per questo cantiere. Scegli il periodo e genera il
                  primo.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {salItems.map((item) => (
                  <SalRow
                    key={item.id}
                    item={item}
                    active={item.id === salId}
                    onClick={() => setSalId(item.id)}
                  />
                ))}
              </div>
            )}
          </section>

          <SalDetail
            sal={detailQuery.data}
            loading={detailQuery.isLoading && Boolean(salId)}
            transitioning={transitionSal.isPending}
            onTransition={(stato) => transitionSal.mutate(stato)}
          />
        </div>
      )}
    </div>
  );
}

function DateField({ label, value, onChange }) {
  return (
    <label className="space-y-1">
      <span className="font-display text-[10px] uppercase text-fog">
        {label}
      </span>
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-stroke bg-bg px-3 py-2.5 text-sm text-ink focus:border-brand focus:outline-none"
      />
    </label>
  );
}

function LoadingPanel({ label, compact = false }) {
  return (
    <div
      className={`flex items-center justify-center gap-2 rounded-2xl border border-stroke bg-surface font-display text-[10px] uppercase tracking-wider text-fog ${
        compact ? "min-h-32" : "min-h-52"
      }`}
      role="status"
    >
      <Loader2 className="h-4 w-4 animate-spin text-brand" /> {label}
    </div>
  );
}

function ErrorPanel({ message }) {
  return (
    <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 font-body text-sm text-red-300">
      {message}
    </div>
  );
}
