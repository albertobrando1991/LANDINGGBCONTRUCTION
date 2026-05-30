import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { Sparkles, Loader2, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";

const COLORS = ["#C62828", "#D4A847", "#6E6E6E", "#22c55e", "#f59e0b"];

function KPI({ label, value, accent }) {
  return (
    <div className="bg-surface border border-stroke rounded-2xl p-5">
      <div className="font-display uppercase text-[10px] tracking-wider text-fog">{label}</div>
      <div className={`font-display font-bold text-3xl mt-1 ${accent ? "text-brand" : "text-ink"}`}>{value}</div>
    </div>
  );
}

const tooltipStyle = { background: "#1a1a1d", border: "1px solid #2e2e31", borderRadius: 12, color: "#f5f5f5", fontSize: 12 };

export default function Report() {
  const [insights, setInsights] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: async () => (await client.get("/reports")).data,
  });
  const [loadingAi, setLoadingAi] = useState(false);

  const genInsights = async () => {
    setLoadingAi(true);
    try {
      const { data: r } = await client.post("/reports/insights");
      setInsights(r.insights);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoadingAi(false);
    }
  };

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;
  const k = data?.kpi || {};

  return (
    <div className="space-y-6">
      <h1 className="font-display font-bold uppercase text-3xl text-ink">Report</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Lead ricevuti" value={k.lead_ricevuti} accent />
        <KPI label="Qualificati" value={k.lead_qualificati} />
        <KPI label="Sopralluoghi" value={k.sopralluoghi} />
        <KPI label="Preventivi" value={k.preventivi} />
        <KPI label="Contratti chiusi" value={k.chiusi_vinti} accent />
        <KPI label="Tasso conversione" value={`${k.conversione}%`} />
        <KPI label="Pipeline aperta" value={formatEuro(k.valore_pipeline)} />
        <KPI label="Valore chiuso" value={formatEuro(k.valore_chiuso)} accent />
      </div>

      {/* AI insights */}
      <div className="bg-surface border border-stroke rounded-2xl p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-semibold uppercase text-sm text-ink flex items-center gap-2"><TrendingUp className="w-4 h-4 text-brand" /> Insight AI</h3>
          <button data-testid="report-insights" onClick={genInsights} disabled={loadingAi}
            className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1.5 rounded-full inline-flex items-center gap-1 hover:bg-brand/25 transition-colors disabled:opacity-60">
            {loadingAi ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />} Genera insight
          </button>
        </div>
        <p className="font-body text-sm text-ink whitespace-pre-line bg-bg border border-stroke rounded-xl p-4 min-h-[60px]">
          {insights || "Genera insight AI basati sui dati del funnel di vendita."}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-surface border border-stroke rounded-2xl p-6">
          <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Lead nel tempo</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data?.timeline || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2e2e31" />
              <XAxis dataKey="data" tick={{ fill: "#6E6E6E", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6E6E6E", fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="lead" stroke="#C62828" strokeWidth={2} dot={{ fill: "#C62828" }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface border border-stroke rounded-2xl p-6">
          <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Distribuzione soluzioni</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data?.distribuzione || []} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {(data?.distribuzione || []).map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface border border-stroke rounded-2xl p-6">
          <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Funnel conversione</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data?.funnel || []} layout="vertical">
              <XAxis type="number" tick={{ fill: "#6E6E6E", fontSize: 10 }} allowDecimals={false} />
              <YAxis type="category" dataKey="step" tick={{ fill: "#6E6E6E", fontSize: 10 }} width={90} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="#C62828" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface border border-stroke rounded-2xl p-6">
          <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Provenienza geografica</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={(data?.geografia || []).slice(0, 8)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2e2e31" />
              <XAxis dataKey="citta" tick={{ fill: "#6E6E6E", fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={50} />
              <YAxis tick={{ fill: "#6E6E6E", fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="lead" fill="#D4A847" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-surface border border-stroke rounded-2xl p-6">
        <h3 className="font-display font-semibold uppercase text-sm text-ink mb-4">Lead persi</h3>
        {(data?.persi || []).length === 0 ? <p className="font-body text-sm text-fog">Nessun lead perso.</p> : (
          <div className="space-y-2">
            {data.persi.map((p, i) => (
              <div key={i} className="flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2">
                <span className="font-display uppercase text-xs text-ink">{p.nome} · <span className="text-fog">{p.citta}</span></span>
                <span className="font-body text-xs text-fog capitalize">{p.livello} · {formatEuro(p.range)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
