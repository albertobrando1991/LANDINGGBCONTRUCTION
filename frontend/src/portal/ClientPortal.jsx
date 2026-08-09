import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Download,
  FileCheck2,
  FileText,
  FileSignature,
  HardHat,
  Image as ImageIcon,
  Loader2,
  LogOut,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import client, { extractErrorDetail, formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";
import {
  createPortalAssetUrl,
  portalAssetsByType,
  portalSummary,
} from "@/lib/clientPortal";
import { useAuth } from "@/context/AuthContext";

function dateLabel(value) {
  if (!value) return "—";
  const date = new Date(
    String(value).length === 10 ? `${value}T00:00:00` : value,
  );
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function ProgressRing({ value }) {
  const progress = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div
      className="relative grid h-28 w-28 place-items-center rounded-full"
      style={{
        background: `conic-gradient(var(--brand-primary) ${progress * 3.6}deg, #262626 0deg)`,
      }}
      aria-label={`Avanzamento ${progress}%`}
    >
      <div className="grid h-[88px] w-[88px] place-items-center rounded-full bg-bg">
        <span className="font-display text-2xl font-bold text-ink">
          {progress}%
        </span>
      </div>
    </div>
  );
}

function Metric({ label, value, accent = false }) {
  return (
    <div className="border-l border-stroke pl-4">
      <div className="font-display text-[10px] uppercase tracking-[0.18em] text-fog">
        {label}
      </div>
      <div
        className={`mt-1 font-display text-xl font-bold ${accent ? "text-brand" : "text-ink"}`}
      >
        {value}
      </div>
    </div>
  );
}

function AssetButton({ asset, photo = false }) {
  const [loading, setLoading] = useState(false);
  const open = async () => {
    setLoading(true);
    try {
      const url = await createPortalAssetUrl(asset);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      toast.error(error.message || "File non disponibile");
    } finally {
      setLoading(false);
    }
  };
  return (
    <button
      type="button"
      onClick={open}
      disabled={loading}
      className={`group overflow-hidden rounded-2xl border border-stroke bg-surface text-left transition hover:-translate-y-0.5 hover:border-brand ${
        photo ? "min-h-44" : "p-4"
      }`}
    >
      {photo ? (
        <div className="flex min-h-44 flex-col justify-end bg-gradient-to-br from-brand/20 via-surface to-bg p-4">
          <ImageIcon className="mb-auto h-7 w-7 text-brand" />
          <div className="font-display text-sm font-semibold uppercase text-ink">
            {asset.titolo}
          </div>
          <div className="mt-1 font-body text-xs text-fog">Apri fotografia</div>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileText className="h-4 w-4" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate font-display text-xs font-semibold uppercase text-ink">
              {asset.titolo}
            </div>
            <div className="mt-1 font-body text-[11px] text-fog">
              Condiviso il {dateLabel(asset.created_at)}
            </div>
          </div>
          <Download className="h-4 w-4 text-fog group-hover:text-brand" />
        </div>
      )}
    </button>
  );
}

function SalCard({ sal }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="rounded-2xl border border-stroke bg-surface">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center gap-4 p-4 text-left"
        aria-expanded={open}
      >
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-500/10 text-emerald-400">
          <FileCheck2 className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display text-sm font-bold uppercase text-ink">
            SAL {String(sal.numero).padStart(2, "0")}
          </div>
          <div className="font-body text-xs text-fog">
            {dateLabel(sal.periodo_da)} — {dateLabel(sal.periodo_a)}
          </div>
        </div>
        <div className="text-right">
          <div className="font-display font-bold text-ink">
            {formatEuro(sal.totale_periodo)}
          </div>
          <div className="font-display text-[9px] uppercase text-emerald-400">
            Approvato
          </div>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-fog transition ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="border-t border-stroke px-4 py-3">
          <div className="space-y-2">
            {(sal.righe || []).map((riga) => (
              <div
                key={riga.id}
                className="flex items-start justify-between gap-4 text-sm"
              >
                <div>
                  <div className="font-body text-ink">{riga.descrizione}</div>
                  <div className="font-body text-[11px] text-fog">
                    {riga.qta_periodo} {riga.um} ×{" "}
                    {formatEuro(riga.prezzo_unitario)}
                  </div>
                </div>
                <div className="shrink-0 font-display text-xs text-ink">
                  {formatEuro(riga.importo_periodo)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

function VarianteCard({ variante, onApprove, pending }) {
  const [confirmed, setConfirmed] = useState(false);
  const [details, setDetails] = useState(false);
  return (
    <article className="rounded-2xl border border-stroke bg-surface p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
            Variante {variante.numero_variante || "contrattuale"}
          </div>
          <h3 className="mt-1 font-display text-lg font-bold uppercase text-ink">
            Quadro economico aggiornato
          </h3>
        </div>
        {variante.approvata ? (
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 font-display text-[10px] uppercase text-emerald-400">
            <CheckCircle2 className="h-4 w-4" /> Approvata{" "}
            {dateLabel(variante.approvata_at)}
          </span>
        ) : (
          <span className="rounded-full border border-brand/30 bg-brand/10 px-3 py-1.5 font-display text-[10px] uppercase text-brand">
            In attesa
          </span>
        )}
      </div>
      <div className="mt-5 grid grid-cols-3 gap-3 rounded-xl bg-bg p-4">
        <Metric label="Base" value={formatEuro(variante.totale_base)} />
        <Metric label="Variante" value={formatEuro(variante.totale_variante)} />
        <Metric
          label="Differenza"
          value={formatEuro(variante.delta_importo)}
          accent
        />
      </div>
      <button
        type="button"
        onClick={() => setDetails((current) => !current)}
        className="mt-4 inline-flex items-center gap-2 font-display text-[10px] uppercase text-fog hover:text-brand"
      >
        Dettaglio lavorazioni
        <ChevronDown
          className={`h-4 w-4 transition ${details ? "rotate-180" : ""}`}
        />
      </button>
      {details && (
        <div className="mt-3 space-y-2 border-t border-stroke pt-3">
          {(variante.righe || []).map((riga) => (
            <div
              key={`${riga.variante_id}-${riga.voce_base_id || riga.voce_variante_id}`}
              className="flex items-start justify-between gap-3 text-sm"
            >
              <div>
                <span className="mr-2 rounded bg-surface-2 px-2 py-0.5 font-display text-[9px] uppercase text-fog">
                  {riga.classificazione}
                </span>
                <span className="font-body text-ink">
                  {riga.descrizione_variante || riga.descrizione_base}
                </span>
              </div>
              <span className="shrink-0 font-display text-xs text-brand">
                {formatEuro(riga.delta_importo)}
              </span>
            </div>
          ))}
        </div>
      )}
      {!variante.approvata && (
        <div className="mt-5 border-t border-stroke pt-4">
          <label className="flex items-start gap-3 font-body text-xs text-fog">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              className="mt-0.5 accent-brand"
            />
            Confermo di aver esaminato importi e lavorazioni della variante.
            L’approvazione viene registrata con data, ora e indirizzo IP e non è
            modificabile.
          </label>
          <button
            type="button"
            disabled={!confirmed || pending}
            onClick={() => onApprove(variante)}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-xs font-semibold uppercase text-white disabled:opacity-40 sm:w-auto"
          >
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            Approva variante
          </button>
        </div>
      )}
    </article>
  );
}

export default function ClientPortal() {
  const { user, logout } = useAuth();
  const qc = useQueryClient();
  const {
    data = {},
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["client-portal"],
    queryFn: async () => (await client.get("/portal")).data,
  });
  const approve = useMutation({
    mutationFn: (item) =>
      client.post(
        `/portal/cantieri/${item.cantiere_id}/varianti/${item.variante_id}/approva`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-portal"] });
      toast.success("Variante approvata e registrata");
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });
  const signDocument = useMutation({
    mutationFn: ({ item, decisione, nome }) =>
      client.post(`/documenti-economici/${item.documento_id}/firma`, {
        decisione,
        firmatario_nome: nome,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["client-portal"] });
      toast.success(
        "Decisione registrata con data, identità e hash del documento",
      );
    },
    onError: (error) =>
      toast.error(formatApiErrorDetail(error.response?.data?.detail)),
  });
  const openEconomicDocument = async (item) => {
    try {
      const response = await client.get(
        `/documenti-economici/${item.documento_id}/pdf`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast.error(await extractErrorDetail(error));
    }
  };
  const decideDocument = (item, decisione) => {
    const nome = window.prompt(
      "Inserisci nome e cognome del firmatario",
      user?.name || "",
    );
    if (!nome?.trim()) return;
    signDocument.mutate({ item, decisione, nome: nome.trim() });
  };
  const summary = useMemo(() => portalSummary(data), [data]);
  const assets = useMemo(
    () => portalAssetsByType(data.assets || []),
    [data.assets],
  );

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-bg text-fog">
        <Loader2 className="h-7 w-7 animate-spin" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="grid min-h-screen place-items-center bg-bg px-6 text-center font-body text-red-400">
        Il portale non è disponibile. Riprova tra poco.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg text-ink">
      <header className="sticky top-0 z-20 border-b border-stroke bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-brand font-display font-bold text-white">
              GB
            </div>
            <div>
              <div className="font-display text-xs font-bold uppercase">
                Construction
              </div>
              <div className="font-display text-[9px] uppercase tracking-[0.18em] text-brand">
                Portale cliente
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 font-display text-[10px] uppercase text-fog hover:border-brand hover:text-brand"
          >
            <LogOut className="h-4 w-4" /> Esci
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-10 px-5 py-8 sm:py-12">
        <section className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <div className="font-display text-[10px] uppercase tracking-[0.25em] text-brand">
              Area riservata · {user?.name || user?.email}
            </div>
            <h1 className="mt-3 max-w-3xl font-display text-3xl font-bold uppercase leading-tight sm:text-5xl">
              Il tuo cantiere, senza zone d’ombra.
            </h1>
            <p className="mt-4 max-w-2xl font-body text-sm leading-6 text-fog">
              Avanzamento, documenti, fotografie, SAL approvati e varianti
              condivise da GB Construction in un unico spazio protetto.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-5 rounded-2xl border border-stroke bg-surface p-5 sm:grid-cols-4 lg:grid-cols-2">
            <Metric label="Cantieri" value={summary.cantieri} />
            <Metric label="SAL" value={summary.salApprovati} />
            <Metric label="Documenti" value={assets.documenti.length} />
            <Metric
              label="Da approvare"
              value={summary.variantiDaApprovare}
              accent
            />
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <HardHat className="h-5 w-5 text-brand" />
            <h2 className="font-display text-sm font-semibold uppercase">
              Avanzamento lavori
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {(data.cantieri || []).map((cantiere) => (
              <article
                key={cantiere.cantiere_id}
                className="flex flex-col gap-5 rounded-2xl border border-stroke bg-surface p-5 sm:flex-row sm:items-center"
              >
                <ProgressRing value={cantiere.avanzamento} />
                <div className="min-w-0 flex-1">
                  <div className="font-display text-lg font-bold uppercase">
                    {cantiere.nome_cantiere}
                  </div>
                  <div className="mt-1 flex items-center gap-1 font-body text-xs text-fog">
                    <MapPin className="h-3.5 w-3.5" />{" "}
                    {cantiere.indirizzo || "Indirizzo riservato"}
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-bg p-3">
                    <div>
                      <div className="font-display text-[9px] uppercase text-fog">
                        Prossima tappa
                      </div>
                      <div className="mt-1 font-body text-xs text-ink">
                        {cantiere.milestone || "In aggiornamento"}
                      </div>
                    </div>
                    <div>
                      <div className="font-display text-[9px] uppercase text-fog">
                        Data prevista
                      </div>
                      <div className="mt-1 flex items-center gap-1 font-body text-xs text-ink">
                        <CalendarDays className="h-3.5 w-3.5 text-brand" />{" "}
                        {dateLabel(cantiere.milestone_data)}
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        {assets.foto.length > 0 && (
          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5 text-brand" />
              <h2 className="font-display text-sm font-semibold uppercase">
                Fotografie condivise
              </h2>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {assets.foto.map((asset) => (
                <AssetButton key={asset.id} asset={asset} photo />
              ))}
            </div>
          </section>
        )}

        <section className="grid gap-8 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-brand" />
              <h2 className="font-display text-sm font-semibold uppercase">
                Documenti condivisi
              </h2>
            </div>
            {assets.documenti.length ? (
              <div className="grid gap-3">
                {assets.documenti.map((asset) => (
                  <AssetButton key={asset.id} asset={asset} />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-stroke p-6 font-body text-sm text-fog">
                Nessun documento condiviso al momento.
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <FileCheck2 className="h-5 w-5 text-brand" />
              <h2 className="font-display text-sm font-semibold uppercase">
                SAL approvati
              </h2>
            </div>
            {(data.sal || []).length ? (
              <div className="space-y-3">
                {data.sal.map((sal) => (
                  <SalCard key={sal.sal_id} sal={sal} />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-stroke p-6 font-body text-sm text-fog">
                I SAL approvati compariranno qui.
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CircleDollarSign className="h-5 w-5 text-brand" />
              <h2 className="font-display text-sm font-semibold uppercase">
                Piano pagamenti
              </h2>
            </div>
            {(data.pagamenti || []).length ? (
              <div className="space-y-3">
                {data.pagamenti.map((item) => (
                  <article
                    key={item.incasso_id}
                    className="rounded-2xl border border-stroke bg-surface p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-display text-xs uppercase text-fog">
                          Rata {item.numero_rata} ·{" "}
                          {dateLabel(item.data_prevista)}
                        </p>
                        <h3 className="mt-1 font-display uppercase text-ink">
                          {item.descrizione}
                        </h3>
                        <p className="mt-1 text-xs text-fog">
                          {item.modalita_pagamento ||
                            "Modalità come da contratto"}
                        </p>
                      </div>
                      <p className="font-display text-brand">
                        {formatEuro(item.importo)}
                      </p>
                    </div>
                    <div className="mt-3 flex justify-between border-t border-stroke pt-3 text-xs text-fog">
                      <span>Pagato {formatEuro(item.pagato)}</span>
                      <span>Residuo {formatEuro(item.residuo)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-stroke p-6 text-sm text-fog">
                Il piano pagamenti comparirà dopo la conferma del contratto.
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <FileSignature className="h-5 w-5 text-brand" />
              <h2 className="font-display text-sm font-semibold uppercase">
                Note SAL ed extra da sottoscrivere
              </h2>
            </div>
            {(data.documenti_economici || []).length ? (
              <div className="space-y-3">
                {data.documenti_economici.map((item) => (
                  <article
                    key={item.documento_id}
                    className="rounded-2xl border border-stroke bg-surface p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => openEconomicDocument(item)}
                        className="text-left font-display uppercase text-ink hover:text-brand"
                      >
                        {item.tipo === "riepilogo_sal"
                          ? "Nota riepilogo SAL"
                          : "Autorizzazione lavorazione extra"}
                      </button>
                      <span className="text-[10px] uppercase text-fog">
                        {item.gia_deciso ? "registrata" : "da esaminare"}
                      </span>
                    </div>
                    {!item.gia_deciso && (
                      <div className="mt-4 flex gap-2">
                        <button
                          type="button"
                          disabled={signDocument.isPending}
                          onClick={() => decideDocument(item, "sottoscritto")}
                          className="rounded-lg bg-brand px-3 py-2 text-[10px] font-display uppercase text-white"
                        >
                          Sottoscrivi
                        </button>
                        <button
                          type="button"
                          disabled={signDocument.isPending}
                          onClick={() => decideDocument(item, "rifiutato")}
                          className="rounded-lg border border-stroke px-3 py-2 text-[10px] font-display uppercase text-fog"
                        >
                          Rifiuta
                        </button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-stroke p-6 text-sm text-fog">
                Nessuna nota economica da esaminare.
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-brand" />
            <h2 className="font-display text-sm font-semibold uppercase">
              Varianti contrattuali
            </h2>
          </div>
          {(data.varianti || []).length ? (
            <div className="grid gap-4">
              {data.varianti.map((variante) => (
                <VarianteCard
                  key={variante.variante_id}
                  variante={variante}
                  pending={
                    approve.isPending &&
                    approve.variables?.variante_id === variante.variante_id
                  }
                  onApprove={(item) => approve.mutate(item)}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-stroke p-6 font-body text-sm text-fog">
              Nessuna variante da esaminare.
            </div>
          )}
        </section>

        <footer className="flex flex-col gap-3 border-t border-stroke py-6 font-body text-xs text-fog sm:flex-row sm:items-center sm:justify-between">
          <span className="inline-flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-brand" /> Dati protetti e
            accessibili solo agli utenti invitati.
          </span>
          <a
            href="mailto:info@gbconstruction.it"
            className="inline-flex items-center gap-1 text-ink hover:text-brand"
          >
            info@gbconstruction.it <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        </footer>
      </main>
    </div>
  );
}
