import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Flame, Phone, MessageCircle, CalendarDays, FileWarning, AlertTriangle, ArrowRight } from "lucide-react";
import client from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { formatEuro, relativeDate } from "@/lib/format";
import { priority, STATI } from "@/dashboard/leadMeta";

function Card({ title, badge, children, testId }) {
  return (
    <div data-testid={testId} className="bg-surface border border-stroke rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display font-semibold uppercase text-sm tracking-wider text-ink">{title}</h3>
        {badge}
      </div>
      {children}
    </div>
  );
}

export default function Today() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["today"],
    queryFn: async () => (await client.get("/dashboard/today")).data,
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;
  const d = data || {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display font-bold uppercase text-3xl md:text-4xl text-ink">
          Buongiorno, {user?.name?.split(" ")[0]}. Ecco cosa fare oggi.
        </h1>
        <p className="font-body text-fog mt-1">{d.nuovi_count || 0} lead richiedono attenzione.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card testId="card-nuovi" title="Nuovi lead da contattare"
          badge={d.nuovi_count > 0 && <span className="font-display uppercase text-[10px] bg-brand text-white px-2 py-1 rounded-full animate-pulse-dot">Urgente</span>}>
          <div className="font-display font-bold text-5xl text-brand mb-4">{d.nuovi_count || 0}</div>
          <div className="space-y-2">
            {(d.nuovi_caldi || []).map((l) => (
              <button key={l.id} onClick={() => navigate(`/dashboard/lead/${l.id}`)}
                className="w-full flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2 hover:border-brand transition-colors text-left">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-2 h-2 rounded-full ${priority(l.score).dot}`} />
                  <span className="font-display uppercase text-xs text-ink truncate">{l.nome}</span>
                  <span className="font-body text-xs text-fog">· {l.citta}</span>
                </div>
                <span className="font-display text-xs text-brand">{formatEuro(l.range_basso)}</span>
              </button>
            ))}
          </div>
          <button onClick={() => navigate("/dashboard/inbox")} className="mt-4 font-display uppercase text-xs text-brand inline-flex items-center gap-1 hover:gap-2 transition-all">
            Vedi tutti <ArrowRight className="w-3 h-3" />
          </button>
        </Card>

        <Card testId="card-followup" title="Follow-up & trattative">
          <div className="font-display font-bold text-5xl text-orange-400 mb-4">{d.followup_count || 0}</div>
          <div className="space-y-2">
            {(d.followup || []).map((l) => (
              <div key={l.id} className="flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2">
                <div className="min-w-0">
                  <div className="font-display uppercase text-xs text-ink truncate">{l.nome}</div>
                  <div className="font-body text-[11px] text-fog">{STATI[l.status]?.label}</div>
                </div>
                <button onClick={() => navigate(`/dashboard/lead/${l.id}`)} className="font-display uppercase text-[10px] bg-brand text-white px-3 py-1.5 rounded-full">Fai ora</button>
              </div>
            ))}
            {(!d.followup || d.followup.length === 0) && <p className="font-body text-sm text-fog">Nessun follow-up oggi.</p>}
          </div>
        </Card>

        <Card testId="card-sopralluoghi" title="Sopralluoghi della settimana"
          badge={<CalendarDays className="w-4 h-4 text-violet-400" />}>
          <div className="font-display font-bold text-5xl text-violet-400 mb-2">{d.sopralluoghi_count || 0}</div>
          <p className="font-body text-sm text-fog">Sopralluoghi programmati.</p>
          <button onClick={() => navigate("/dashboard/sopralluoghi")} className="mt-4 font-display uppercase text-xs text-brand inline-flex items-center gap-1 hover:gap-2 transition-all">
            Apri calendario <ArrowRight className="w-3 h-3" />
          </button>
        </Card>

        <Card testId="card-preventivi" title="Preventivi in attesa risposta"
          badge={<FileWarning className="w-4 h-4 text-yellow-400" />}>
          <div className="space-y-2">
            {(d.preventivi_attesa || []).map((l) => (
              <div key={l.id} className="flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-display uppercase text-xs text-ink truncate">{l.nome}</span>
                  <span className={`font-display text-[10px] px-2 py-0.5 rounded-full ${l.giorni_silenzio > 10 ? "bg-red-500/20 text-red-400" : "bg-yellow-500/20 text-yellow-400"}`}>
                    {l.giorni_silenzio}gg
                  </span>
                </div>
                <a href={`https://wa.me/`} target="_blank" rel="noreferrer" className="text-success"><MessageCircle className="w-4 h-4" /></a>
              </div>
            ))}
            {(!d.preventivi_attesa || d.preventivi_attesa.length === 0) && <p className="font-body text-sm text-fog">Nessun preventivo in attesa.</p>}
          </div>
        </Card>
      </div>

      {/* Alert */}
      <Card testId="card-alert" title="Alert urgenti" badge={<AlertTriangle className="w-4 h-4 text-brand" />}>
        {(d.alert && d.alert.length > 0) ? (
          <div className="space-y-2">
            {d.alert.map((l) => (
              <button key={l.id} onClick={() => navigate(`/dashboard/lead/${l.id}`)}
                className="w-full flex items-center gap-3 bg-brand/10 border border-brand/30 rounded-xl px-3 py-2 text-left hover:bg-brand/15 transition-colors">
                <Flame className="w-4 h-4 text-brand shrink-0" />
                <span className="font-body text-sm text-ink">Lead <b>{l.nome}</b> non gestito da oltre 18h · arrivato {relativeDate(l.created_at)}</span>
              </button>
            ))}
          </div>
        ) : <p className="font-body text-sm text-fog">Nessun alert. Tutto sotto controllo. 👷</p>}
      </Card>
    </div>
  );
}
