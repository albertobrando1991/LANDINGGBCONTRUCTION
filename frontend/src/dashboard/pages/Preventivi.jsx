import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { MessageCircle, FileText } from "lucide-react";
import client from "@/lib/api";
import { formatEuro } from "@/lib/format";
import { buildWhatsappUrl } from "@/lib/whatsapp";
import { STATI } from "@/dashboard/leadMeta";

export default function Preventivi() {
  const navigate = useNavigate();
  const { data: list = [], isLoading } = useQuery({
    queryKey: ["preventivi"],
    queryFn: async () => (await client.get("/preventivi")).data,
    refetchInterval: 30000,
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="font-display font-bold uppercase text-3xl text-ink">Preventivi</h1>
        <button className="bg-brand text-white rounded-full px-5 py-2 font-display uppercase text-xs tracking-wider hover:scale-105 transition-transform">+ Nuovo preventivo</button>
      </div>

      <div className="bg-surface border border-stroke rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stroke text-left font-display uppercase text-[10px] tracking-wider text-fog">
              <th className="px-4 py-3">Cliente</th>
              <th className="px-4 py-3">Città</th>
              <th className="px-4 py-3">Soluzione</th>
              <th className="px-4 py-3">Range €</th>
              <th className="px-4 py-3">Stato</th>
              <th className="px-4 py-3">Silenzio</th>
              <th className="px-4 py-3 text-right">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id} className="border-b border-stroke/60 hover:bg-surface-2/50 cursor-pointer" onClick={() => navigate(`/dashboard/lead/${p.id}`)}>
                <td className="px-4 py-3 font-display uppercase text-xs text-ink">{p.cliente}</td>
                <td className="px-4 py-3 font-body text-xs text-fog">{p.citta}</td>
                <td className="px-4 py-3 font-body text-xs text-fog capitalize">{p.livello}</td>
                <td className="px-4 py-3 font-display text-xs text-brand">{formatEuro(p.range_basso)}</td>
                <td className="px-4 py-3"><span className={`font-display uppercase text-[10px] px-2 py-1 rounded-full ${STATI[p.status]?.bg} ${STATI[p.status]?.color}`}>{STATI[p.status]?.label}</span></td>
                <td className="px-4 py-3">
                  {["preventivo_inviato", "follow_up", "in_trattativa"].includes(p.status)
                    ? <span className={`font-display text-[10px] px-2 py-0.5 rounded-full ${p.giorni_silenzio > 10 ? "bg-red-500/20 text-red-400" : p.giorni_silenzio >= 5 ? "bg-yellow-500/20 text-yellow-400" : "bg-emerald-500/20 text-emerald-400"}`}>{p.giorni_silenzio}gg</span>
                    : <span className="text-fog text-xs">—</span>}
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-2 text-fog">
                    <button className="hover:text-ink"><FileText className="w-4 h-4" /></button>
                    {buildWhatsappUrl(p.telefono, p.cliente) ? (
                      <a href={buildWhatsappUrl(p.telefono, p.cliente)} target="_blank" rel="noreferrer" className="hover:text-success"><MessageCircle className="w-4 h-4" /></a>
                    ) : (
                      <span className="opacity-30"><MessageCircle className="w-4 h-4" /></span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {list.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center font-body text-fog">Nessun preventivo.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
