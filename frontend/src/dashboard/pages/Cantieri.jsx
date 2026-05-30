import { useQuery } from "@tanstack/react-query";
import { MapPin, User, AlertTriangle, Flag } from "lucide-react";
import client from "@/lib/api";
import { formatEuro, formatDateTime } from "@/lib/format";

const FASE_COLOR = {
  completata: "bg-emerald-500",
  in_corso: "bg-brand",
  da_iniziare: "bg-stroke",
};

export default function Cantieri() {
  const { data: list = [], isLoading } = useQuery({
    queryKey: ["cantieri"],
    queryFn: async () => (await client.get("/cantieri")).data,
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;

  return (
    <div className="space-y-5">
      <h1 className="font-display font-bold uppercase text-3xl text-ink">Cantieri attivi</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {list.map((c) => (
          <div key={c.id} data-testid={`cantiere-${c.id}`} className="bg-surface border border-stroke rounded-2xl p-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="font-display font-bold uppercase text-ink">{c.cliente}</div>
                <div className="font-body text-xs text-fog flex items-center gap-1 mt-1"><MapPin className="w-3 h-3" /> {c.indirizzo}</div>
              </div>
              <div className="font-display font-bold text-lg text-brand">{formatEuro(c.importo)}</div>
            </div>

            <div className="mb-2 flex items-center justify-between">
              <span className="font-display uppercase text-xs text-fog">Avanzamento</span>
              <span className="font-display font-bold text-sm text-ink">{c.avanzamento}%</span>
            </div>
            <div className="h-2 bg-bg rounded-full overflow-hidden mb-4">
              <div className="h-full accent-gradient" style={{ width: `${c.avanzamento}%` }} />
            </div>

            {/* Gantt fasi */}
            <div className="flex gap-1 mb-4">
              {c.fasi.map((f, i) => (
                <div key={i} className="flex-1" title={f.nome}>
                  <div className={`h-1.5 rounded-full ${FASE_COLOR[f.stato]}`} />
                  <div className="font-body text-[9px] text-fog mt-1 truncate text-center">{f.nome}</div>
                </div>
              ))}
            </div>

            <div className="space-y-2 font-body text-sm text-fog">
              <div className="flex items-center gap-2"><Flag className="w-4 h-4 text-brand" /> {c.milestone} · {formatDateTime(c.milestone_data)}</div>
              <div className="flex items-center gap-2 capitalize"><User className="w-4 h-4 text-brand" /> {c.capocantiere}</div>
              {c.criticita && (
                <div className="flex items-center gap-2 text-warning bg-warning/10 border border-warning/30 rounded-xl px-3 py-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" /> {c.criticita}
                </div>
              )}
            </div>
          </div>
        ))}
        {list.length === 0 && <p className="font-body text-fog">Nessun cantiere attivo.</p>}
      </div>
    </div>
  );
}
