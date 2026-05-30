import { useQuery } from "@tanstack/react-query";
import { MapPin, Phone, Clock, CheckCircle2, User } from "lucide-react";
import client from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default function Sopralluoghi() {
  const { data: list = [], isLoading } = useQuery({
    queryKey: ["sopralluoghi"],
    queryFn: async () => (await client.get("/sopralluoghi")).data,
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;

  return (
    <div className="space-y-5">
      <h1 className="font-display font-bold uppercase text-3xl text-ink">Sopralluoghi</h1>
      {list.length === 0 ? (
        <p className="font-body text-fog">Nessun sopralluogo programmato.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {list.map((s) => (
            <div key={s.id} data-testid={`sopralluogo-${s.id}`} className="bg-surface border border-stroke rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="font-display font-bold uppercase text-ink">{s.cliente}</div>
                {s.completato
                  ? <span className="font-display uppercase text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-full inline-flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Completato</span>
                  : <span className="font-display uppercase text-[10px] bg-violet-500/20 text-violet-400 px-2 py-1 rounded-full">Programmato</span>}
              </div>
              <div className="space-y-2 font-body text-sm text-fog">
                <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-brand" /> {formatDateTime(s.data)}</div>
                <a href={`https://maps.google.com/?q=${encodeURIComponent(s.indirizzo)}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 hover:text-ink"><MapPin className="w-4 h-4 text-brand" /> {s.indirizzo}</a>
                <div className="flex items-center gap-2 capitalize"><User className="w-4 h-4 text-brand" /> Tecnico: {s.tecnico}</div>
                <div className="capitalize">Progetto: {s.tipo_immobile} · {s.mq}mq</div>
              </div>
              <div className="flex gap-2 mt-4">
                <a href={`tel:${s.telefono}`} className="flex-1 bg-bg border border-stroke rounded-xl py-2 text-center font-display uppercase text-xs text-fog hover:text-ink hover:border-brand transition-colors inline-flex items-center justify-center gap-1"><Phone className="w-3 h-3" /> Chiama</a>
                <button className="flex-1 bg-brand text-white rounded-xl py-2 font-display uppercase text-xs hover:scale-[1.02] transition-transform">
                  {s.completato ? "Genera preventivo" : "Avvia sopralluogo"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
