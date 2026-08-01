import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import client from "@/lib/api";
import { toast } from "sonner";

export default function Computi() {
  const qc = useQueryClient();
  const { data: computi = [], isLoading } = useQuery({
    queryKey: ["computi"],
    queryFn: async () => (await client.get("/computi")).data,
  });

  const crea = useMutation({
    mutationFn: async () => (await client.post("/computi", { tipo: "estimativo" })).data,
    onSuccess: (c) => {
      toast.success("Computo creato");
      qc.invalidateQueries({ queryKey: ["computi"] });
      window.location.href = `/dashboard/computi/${c.id}`;
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Errore creazione"),
  });

  if (isLoading) {
    return <div className="p-6 text-fog text-sm font-display uppercase tracking-widest">Caricamento computi…</div>;
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl uppercase text-ink">Computi</h1>
          <p className="text-fog text-sm">Estimativi, esecutivi e bozze AI da validare</p>
        </div>
        <button
          type="button"
          onClick={() => crea.mutate()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-brand text-white text-xs font-display uppercase tracking-wider"
        >
          <Plus className="w-4 h-4" /> Nuovo computo
        </button>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-stroke">
        <table className="min-w-full text-sm">
          <thead className="bg-surface-2 text-fog font-display uppercase text-[10px] tracking-wider">
            <tr>
              <th className="text-left px-3 py-2">ID</th>
              <th className="text-left px-3 py-2">Tipo</th>
              <th className="text-left px-3 py-2">Stato</th>
              <th className="text-right px-3 py-2">Totale</th>
              <th className="text-right px-3 py-2">Voci</th>
              <th className="text-right px-3 py-2">Da validare</th>
            </tr>
          </thead>
          <tbody>
            {computi.map((c) => (
              <tr key={c.id} className="border-t border-stroke/60 hover:bg-surface-2/40">
                <td className="px-3 py-2">
                  <Link to={`/dashboard/computi/${c.id}`} className="text-brand font-mono text-xs">
                    {String(c.id).slice(0, 8)}…
                  </Link>
                </td>
                <td className="px-3 py-2 text-fog">{c.tipo}</td>
                <td className="px-3 py-2">
                  <span className="px-2 py-0.5 rounded-full bg-surface-2 border border-stroke text-[10px] uppercase tracking-wider text-ink">
                    {c.stato}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-ink">€ {Number(c.totale || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}</td>
                <td className="px-3 py-2 text-right text-fog">{c.n_voci || 0}</td>
                <td className="px-3 py-2 text-right">
                  {Number(c.n_da_validare || 0) > 0 ? (
                    <span className="text-brand font-display text-xs">{c.n_da_validare}</span>
                  ) : (
                    <span className="text-fog">0</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
