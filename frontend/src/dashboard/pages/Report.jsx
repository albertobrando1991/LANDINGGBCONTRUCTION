import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  BarChart3,
  CalendarRange,
  Inbox,
  Loader2,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro, formatNumber } from "@/lib/format";

const COLORS = ["#C62828", "#D4A847", "#6E6E6E", "#22c55e"];
const PERIOD_OPTIONS = [
  { value: "30d", label: "30 giorni" },
  { value: "90d", label: "90 giorni" },
  { value: "180d", label: "6 mesi" },
  { value: "365d", label: "12 mesi" },
  { value: "all", label: "Tutto" },
];

const tooltipStyle = {
  background: "#1a1a1d",
  border: "1px solid #2e2e31",
  borderRadius: 12,
  color: "#f5f5f5",
  fontSize: 12,
};

function KPI({ label, value, accent = false }) {
  return (
    <article className="min-w-0 rounded-2xl border border-stroke bg-surface p-5">
      <p className="font-display text-[10px] uppercase tracking-[0.16em] text-fog">
        {label}
      </p>
      <p
        className={`mt-1 break-words font-display text-2xl font-bold sm:text-3xl ${
          accent ? "text-brand" : "text-ink"
        }`}
      >
        {value}
      </p>
    </article>
  );
}

function Panel({ id, title, subtitle, children }) {
  return (
    <section
      className="min-w-0 overflow-hidden rounded-2xl border border-stroke bg-surface p-4 sm:p-6"
      aria-labelledby={id}
    >
      <div className="mb-4">
        <h2
          id={id}
          className="font-display text-sm font-semibold uppercase text-ink"
        >
          {title}
        </h2>
        {subtitle && (
          <p className="mt-1 font-body text-xs text-fog">{subtitle}</p>
        )}
      </div>
      {children}
    </section>
  );
}

function EmptyChart({ message }) {
  return (
    <div className="flex h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-stroke bg-bg/40 px-5 text-center">
      <BarChart3 className="h-7 w-7 text-brand" aria-hidden="true" />
      <p className="mt-3 max-w-xs font-body text-sm text-fog">{message}</p>
    </div>
  );
}

function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-label="Caricamento report" aria-busy="true">
      <div className="h-10 w-56 animate-pulse rounded-xl bg-surface" />
      <div className="grid grid-cols-1 gap-4 min-[380px]:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <div
            key={index}
            className="h-28 animate-pulse rounded-2xl border border-stroke bg-surface"
          />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="h-80 animate-pulse rounded-2xl border border-stroke bg-surface" />
        <div className="h-80 animate-pulse rounded-2xl border border-stroke bg-surface" />
      </div>
    </div>
  );
}

function dateLabel(value, includeYear = true) {
  if (!value) return "—";
  const normalized = /^\d{4}-\d{2}$/.test(value)
    ? `${value}-01`
    : value.slice(0, 10);
  const parsed = new Date(`${normalized}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("it-IT", {
    day: /^\d{4}-\d{2}$/.test(value) ? undefined : "2-digit",
    month: "short",
    year: includeYear ? "2-digit" : undefined,
  });
}

function generatedAtLabel(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function cityTick({ x, y, payload }) {
  const value = String(payload?.value || "");
  const shortened = value.length > 15 ? `${value.slice(0, 14)}…` : value;
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fill="#6E6E6E" fontSize={10}>
      {shortened}
    </text>
  );
}

export default function Report() {
  const [period, setPeriod] = useState("180d");
  const [insights, setInsights] = useState("");
  const [insightSource, setInsightSource] = useState(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const { data, error, isError, isFetching, isLoading, refetch } = useQuery({
    queryKey: ["reports", period],
    queryFn: async ({ signal }) =>
      (
        await client.get("/reports", {
          params: { period },
          signal,
        })
      ).data,
    staleTime: 60_000,
  });

  useEffect(() => {
    setInsights("");
    setInsightSource(null);
  }, [period]);

  const genInsights = async () => {
    setLoadingAi(true);
    try {
      const { data: response } = await client.post("/reports/insights", null, {
        params: { period },
      });
      setInsights(response.insights || "");
      setInsightSource(response.source || "ai");
    } catch (requestError) {
      toast.error(formatApiErrorDetail(requestError.response?.data?.detail));
    } finally {
      setLoadingAi(false);
    }
  };

  if (isLoading) return <ReportSkeleton />;

  if (isError && !data) {
    return (
      <section
        className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6"
        role="alert"
      >
        <AlertCircle className="h-7 w-7 text-red-300" aria-hidden="true" />
        <h1 className="mt-4 font-display text-xl font-bold uppercase text-ink">
          Report non disponibile
        </h1>
        <p className="mt-2 max-w-xl font-body text-sm text-fog">
          {formatApiErrorDetail(error?.response?.data?.detail)}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 py-2 font-display text-xs uppercase text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Riprova
        </button>
      </section>
    );
  }

  const kpi = data?.kpi || {};
  const meta = data?.meta || {};
  const hasLeads = Number(kpi.lead_ricevuti || 0) > 0;
  const timeline = data?.timeline || [];
  const distribution = data?.distribuzione || [];
  const funnel = data?.funnel || [];
  const geography = (data?.geografia || []).slice(0, 8);
  const lost = data?.persi || [];
  const updatedAt = generatedAtLabel(meta.generated_at);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
            Analisi commerciale
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold uppercase text-ink">
            Report
          </h1>
          <p className="mt-2 font-body text-sm text-fog">
            KPI, funnel e provenienza dei lead in un’unica vista.
            {updatedAt ? ` Aggiornato alle ${updatedAt}.` : ""}
          </p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <label className="relative min-w-0 flex-1 sm:flex-none">
            <span className="sr-only">Periodo del report</span>
            <CalendarRange
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brand"
              aria-hidden="true"
            />
            <select
              aria-label="Periodo del report"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              className="min-h-11 w-full appearance-none rounded-xl border border-stroke bg-surface py-2 pl-9 pr-8 font-display text-[11px] uppercase text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/30 sm:w-auto"
            >
              {PERIOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Aggiorna report"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-stroke bg-surface text-fog transition-colors hover:border-brand hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-60"
          >
            <RefreshCw
              className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
          </button>
        </div>
      </header>

      {isError && data && (
        <div
          className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 font-body text-sm text-amber-200"
          role="status"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          Aggiornamento non riuscito: sono ancora visibili gli ultimi dati
          disponibili.
        </div>
      )}

      <section
        className="grid grid-cols-1 gap-4 min-[380px]:grid-cols-2 xl:grid-cols-4"
        aria-label="Indicatori principali"
      >
        <KPI
          label="Lead ricevuti"
          value={formatNumber(kpi.lead_ricevuti || 0)}
          accent
        />
        <KPI
          label="Qualificati"
          value={formatNumber(kpi.lead_qualificati || 0)}
        />
        <KPI label="Sopralluoghi" value={formatNumber(kpi.sopralluoghi || 0)} />
        <KPI
          label="Preventivi inviati"
          value={formatNumber(kpi.preventivi || 0)}
        />
        <KPI
          label="Contratti chiusi"
          value={formatNumber(kpi.chiusi_vinti || 0)}
          accent
        />
        <KPI label="Tasso conversione" value={`${kpi.conversione ?? 0}%`} />
        <KPI
          label="Pipeline aperta"
          value={formatEuro(kpi.valore_pipeline || 0)}
        />
        <KPI
          label="Valore chiuso"
          value={formatEuro(kpi.valore_chiuso || 0)}
          accent
        />
      </section>

      <section
        className="rounded-2xl border border-stroke bg-surface p-4 sm:p-6"
        aria-labelledby="ai-insights-title"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2
              id="ai-insights-title"
              className="flex items-center gap-2 font-display text-sm font-semibold uppercase text-ink"
            >
              <TrendingUp className="h-4 w-4 text-brand" aria-hidden="true" />
              Insight AI
            </h2>
            <p className="mt-1 font-body text-xs text-fog">
              Analisi riferita a{" "}
              {meta.period_label?.toLowerCase() || "questo periodo"}.
            </p>
          </div>
          <button
            type="button"
            data-testid="report-insights"
            onClick={genInsights}
            disabled={loadingAi || !hasLeads}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand/15 px-4 py-2 font-display text-[10px] uppercase text-brand transition-colors hover:bg-brand/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {loadingAi ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            )}
            {insights ? "Rigenera insight" : "Genera insight"}
          </button>
        </div>
        <div
          className="mt-4 min-h-[76px] whitespace-pre-line rounded-xl border border-stroke bg-bg p-4 font-body text-sm leading-6 text-ink"
          aria-live="polite"
        >
          {insights ||
            (hasLeads
              ? "Genera suggerimenti operativi basati sui dati del periodo selezionato."
              : "Gli insight saranno disponibili quando il periodo conterrà almeno un lead.")}
        </div>
        {insightSource === "fallback" && (
          <p className="mt-2 font-body text-[11px] text-fog">
            Suggerimento operativo standard: il provider AI non era disponibile
            e non è stato addebitato alcun credito.
          </p>
        )}
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel
          id="timeline-title"
          title="Lead nel tempo"
          subtitle="Andamento con intervalli senza nuovi contatti inclusi."
        >
          {!hasLeads || timeline.length === 0 ? (
            <EmptyChart message="Nessun lead nel periodo selezionato." />
          ) : (
            <div
              className="h-[260px] min-w-0"
              role="img"
              aria-label="Grafico dei lead nel tempo"
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={timeline}
                  margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                  accessibilityLayer
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#2e2e31"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="data"
                    tick={{ fill: "#6E6E6E", fontSize: 10 }}
                    tickFormatter={(value) => dateLabel(value, false)}
                    minTickGap={24}
                  />
                  <YAxis
                    tick={{ fill: "#6E6E6E", fontSize: 10 }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(value) => dateLabel(value)}
                    formatter={(value) => [formatNumber(value), "Lead"]}
                  />
                  <Line
                    type="monotone"
                    dataKey="lead"
                    stroke="#C62828"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 5, fill: "#C62828" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel
          id="distribution-title"
          title="Distribuzione soluzioni"
          subtitle="Preferenze dichiarate dai lead con progetto definito."
        >
          {!hasLeads || distribution.length === 0 ? (
            <EmptyChart message="Nessuna soluzione disponibile per questo periodo." />
          ) : (
            <div className="grid min-h-[260px] grid-cols-1 items-center gap-3 min-[460px]:grid-cols-[minmax(0,1fr)_auto]">
              <div
                className="h-[220px] min-w-0"
                role="img"
                aria-label="Grafico della distribuzione delle soluzioni"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart accessibilityLayer>
                    <Pie
                      data={distribution}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={48}
                      outerRadius={78}
                      paddingAngle={3}
                      stroke="none"
                    >
                      {distribution.map((entry, index) => (
                        <Cell
                          key={entry.name}
                          fill={COLORS[index % COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value) => [formatNumber(value), "Lead"]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="grid gap-2" aria-label="Legenda soluzioni">
                {distribution.map((entry, index) => (
                  <li
                    key={entry.name}
                    className="flex min-w-32 items-center justify-between gap-4 text-xs"
                  >
                    <span className="flex items-center gap-2 font-body text-fog">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{
                          backgroundColor: COLORS[index % COLORS.length],
                        }}
                        aria-hidden="true"
                      />
                      {entry.name}
                    </span>
                    <strong className="font-display text-ink">
                      {formatNumber(entry.value)}
                    </strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        <Panel
          id="funnel-title"
          title="Funnel conversione"
          subtitle="Ogni fase include i lead che sono già avanzati oltre."
        >
          {!hasLeads || funnel.length === 0 ? (
            <EmptyChart message="Il funnel è vuoto per questo periodo." />
          ) : (
            <div
              className="h-[260px] min-w-0"
              role="img"
              aria-label="Grafico del funnel di conversione"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={funnel}
                  layout="vertical"
                  margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
                  accessibilityLayer
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#6E6E6E", fontSize: 10 }}
                    tickFormatter={formatNumber}
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="step"
                    tick={{ fill: "#6E6E6E", fontSize: 10 }}
                    width={86}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value, _name, item) => [
                      `${formatNumber(value)} (${item?.payload?.percentuale || 0}%)`,
                      "Lead",
                    ]}
                  />
                  <Bar dataKey="value" fill="#C62828" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel
          id="geography-title"
          title="Provenienza geografica"
          subtitle="Prime 8 località per numero di lead."
        >
          {!hasLeads || geography.length === 0 ? (
            <EmptyChart message="Nessuna località disponibile per questo periodo." />
          ) : (
            <div
              className="h-[260px] min-w-0"
              role="img"
              aria-label="Grafico della provenienza geografica"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={geography}
                  layout="vertical"
                  margin={{ top: 4, right: 12, left: 8, bottom: 0 }}
                  accessibilityLayer
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#2e2e31"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{ fill: "#6E6E6E", fontSize: 10 }}
                    tickFormatter={formatNumber}
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="citta"
                    tick={cityTick}
                    width={98}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value) => [formatNumber(value), "Lead"]}
                  />
                  <Bar dataKey="lead" fill="#D4A847" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>
      </div>

      <Panel
        id="lost-title"
        title="Lead persi"
        subtitle={
          meta.lost_total > lost.length
            ? `${lost.length} più recenti su ${meta.lost_total} nel periodo.`
            : `${meta.lost_total || 0} nel periodo selezionato.`
        }
      >
        {lost.length === 0 ? (
          <div className="flex min-h-32 flex-col items-center justify-center rounded-xl border border-dashed border-stroke bg-bg/40 px-5 text-center">
            <Inbox className="h-7 w-7 text-emerald-400" aria-hidden="true" />
            <p className="mt-3 font-body text-sm text-fog">
              Nessun lead perso nel periodo.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {lost.map((item, index) => (
              <article
                key={item.id || `${item.nome}-${index}`}
                className="flex flex-col gap-3 rounded-xl border border-stroke bg-bg px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="break-words font-display text-xs uppercase text-ink">
                    {item.nome}
                  </p>
                  <p className="mt-1 font-body text-xs text-fog">
                    {item.citta || "Località non indicata"} ·{" "}
                    {item.livello || "Da definire"}
                  </p>
                </div>
                <div className="shrink-0 text-left sm:text-right">
                  <p className="font-display text-sm font-semibold text-ink">
                    {formatEuro(item.range)}
                  </p>
                  <p className="mt-1 font-body text-[11px] text-fog">
                    {dateLabel(item.data)}
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
