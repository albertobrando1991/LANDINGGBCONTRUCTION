import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import client from "@/lib/api";
import { formatEuro } from "@/lib/format";
import { STATI, priority, initials, ageColor } from "@/dashboard/leadMeta";

export default function Pipeline() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["pipeline"],
    queryFn: async () => (await client.get("/pipeline")).data,
    refetchInterval: 30000,
  });

  const move = useMutation({
    mutationFn: ({ id, status }) => client.patch(`/leads/${id}`, { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pipeline"] }); toast.success("Lead spostato"); },
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;

  const onDrop = (colKey) => {
    if (dragId) move.mutate({ id: dragId, status: colKey });
    setDragId(null);
    setOverCol(null);
  };

  return (
    <div className="space-y-5">
      <h1 className="font-display font-bold uppercase text-3xl text-ink">Pipeline</h1>
      <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar">
        {(data?.columns || []).map((col) => (
          <div key={col.key}
            role="group"
            aria-label={`${col.label}: ${col.count} lead`}
            onDragOver={(e) => { e.preventDefault(); setOverCol(col.key); }}
            onDrop={() => onDrop(col.key)}
            className={`w-72 shrink-0 bg-surface border rounded-2xl p-3 transition-colors ${overCol === col.key ? "border-brand" : "border-stroke"}`}>
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${STATI[col.key]?.dot}`} />
                <span className="font-display uppercase text-xs text-ink">{col.label}</span>
                <span className="font-display text-xs text-fog">{col.count}</span>
              </div>
            </div>
            <div className="font-display text-[10px] uppercase text-fog px-1 mb-2">{formatEuro(col.valore)}</div>
            <div className="space-y-2 min-h-[60px]">
              {col.leads.map((l) => (
                <div key={l.id} draggable data-testid={`kanban-card-${l.id}`}
                  onDragStart={() => setDragId(l.id)}
                  className={`bg-bg border border-stroke border-l-4 ${ageColor(l.giorni_in_stato)} rounded-xl p-3 cursor-grab active:cursor-grabbing hover:border-brand transition-colors`}>
                  <button
                    type="button"
                    onClick={() => navigate(`/dashboard/lead/${l.id}`)}
                    className="block w-full text-left"
                  >
                  <div className="flex items-center justify-between">
                    <span className="font-display uppercase text-xs text-ink truncate">{l.nome}</span>
                    <span className={`w-2 h-2 rounded-full ${priority(l.score).dot}`} />
                  </div>
                  <div className="font-body text-[11px] text-fog">{l.citta}</div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="font-display text-xs text-brand">{formatEuro(l.range_basso)}</span>
                    {l.owner && <span className="w-6 h-6 rounded-full bg-brand/20 text-brand inline-flex items-center justify-center font-display text-[9px]">{initials(l.owner)}</span>}
                  </div>
                  <div className="font-body text-[10px] text-fog mt-1">{l.giorni_in_stato}gg in stato</div>
                  </button>
                  <label className="mt-3 block">
                    <span className="sr-only">Sposta {l.nome} in un altro stato</span>
                    <select
                      value={col.key}
                      disabled={move.isPending}
                      onPointerDown={(event) => event.stopPropagation()}
                      onChange={(event) => {
                        event.stopPropagation();
                        move.mutate({ id: l.id, status: event.target.value });
                      }}
                      className="w-full rounded-lg border border-stroke bg-surface px-2 py-1.5 font-display text-[10px] uppercase text-fog outline-none focus:border-brand disabled:opacity-50"
                    >
                      {(data?.columns || []).map((target) => (
                        <option key={target.key} value={target.key}>
                          {target.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
