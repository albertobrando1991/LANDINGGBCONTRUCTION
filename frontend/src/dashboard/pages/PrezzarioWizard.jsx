import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams, Link } from "react-router-dom";
import client from "@/lib/api";
import { toast } from "sonner";

export default function PrezzarioWizard() {
  const [params] = useSearchParams();
  const prezzarioId = params.get("id");
  const qc = useQueryClient();
  const [draft, setDraft] = useState({});

  const { data: voci = [], isLoading } = useQuery({
    queryKey: ["wizard", prezzarioId],
    enabled: Boolean(prezzarioId),
    queryFn: async () => (await client.get(`/prezzario/${prezzarioId}/wizard`)).data,
  });

  const groups = useMemo(() => {
    const map = {};
    for (const v of voci) {
      const k = v.super_categoria || "Altro";
      (map[k] ||= []).push(v);
    }
    return map;
  }, [voci]);

  const save = useMutation({
    mutationFn: async () => {
      const correzioni = {};
      for (const [id, val] of Object.entries(draft)) {
        if (val !== "" && val != null) correzioni[id] = Number(val);
      }
      return (await client.post(`/prezzario/${prezzarioId}/wizard`, { correzioni })).data;
    },
    onSuccess: (d) => {
      toast.success(`Aggiornate ${d.voci_chiave_aggiornate} chiavi, propagate ${d.voci_propagate}`);
      setDraft({});
      qc.invalidateQueries({ queryKey: ["wizard"] });
      qc.invalidateQueries({ queryKey: ["prezzario-voci"] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Salvataggio fallito"),
  });

  if (!prezzarioId) {
    return (
      <div className="p-6">
        <p className="text-fog">Seleziona un prezzario dalla lista.</p>
        <Link to="/dashboard/prezzario" className="text-brand underline text-sm">Torna al prezzario</Link>
      </div>
    );
  }

  if (isLoading) {
    return <div className="p-6 text-fog text-sm font-display uppercase tracking-widest">Caricamento wizard…</div>;
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl uppercase text-ink">Wizard 28 voci</h1>
          <p className="text-fog text-sm">Calibra le voci chiave: le altre della stessa categoria si aggiornano in proporzione.</p>
        </div>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending || Object.keys(draft).length === 0}
          className="px-4 py-2 rounded-xl bg-brand text-white text-xs font-display uppercase tracking-wider disabled:opacity-40"
        >
          Salva correzioni
        </button>
      </div>

      {Object.entries(groups).map(([superCat, list]) => (
        <section key={superCat} className="rounded-2xl border border-stroke bg-surface p-4 space-y-3">
          <h2 className="font-display uppercase text-sm text-brand tracking-wider">{superCat}</h2>
          <div className="space-y-2">
            {list.map((v) => (
              <div key={v.id} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
                <div className="md:col-span-6 text-sm text-ink">{v.descrizione}</div>
                <div className="md:col-span-2 text-xs text-fog">{v.um}</div>
                <div className="md:col-span-2 text-xs text-fog">ref € {Number(v.prezzo_riferimento || v.prezzo_unitario).toFixed(2)}</div>
                <div className="md:col-span-2">
                  <input
                    type="number"
                    step="0.01"
                    className="w-full bg-surface-2 border border-stroke rounded-lg px-2 py-1.5 text-sm text-ink"
                    placeholder={String(Number(v.prezzo_unitario).toFixed(2))}
                    value={draft[v.id] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [v.id]: e.target.value }))}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
