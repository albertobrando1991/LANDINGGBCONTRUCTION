import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import client from "@/lib/api";
import { toast } from "sonner";

export default function ComputoEditor() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [voceId, setVoceId] = useState("");
  const [qta, setQta] = useState(1);
  const [prezzarioId, setPrezzarioId] = useState("");

  const { data: computo, isLoading } = useQuery({
    queryKey: ["computo", id],
    queryFn: async () => (await client.get(`/computi/${id}`)).data,
  });

  const { data: prezzari = [] } = useQuery({
    queryKey: ["prezzari"],
    queryFn: async () => (await client.get("/prezzario")).data,
  });

  const activePrezz = prezzarioId || prezzari.find((p) => p.is_default)?.id || prezzari[0]?.id;

  const { data: vociPrezz = [] } = useQuery({
    queryKey: ["prezzario-voci-editor", activePrezz],
    enabled: Boolean(activePrezz),
    queryFn: async () => (await client.get(`/prezzario/${activePrezz}/voci`)).data,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["computo", id] });

  const add = useMutation({
    mutationFn: async () =>
      (await client.post(`/computi/${id}/voci`, { prezzario_voce_id: voceId, qta: Number(qta) })).data,
    onSuccess: () => {
      toast.success("Voce aggiunta");
      setVoceId("");
      refresh();
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Errore"),
  });

  const conferma = useMutation({
    mutationFn: async () => (await client.post(`/computi/${id}/conferma`)).data,
    onSuccess: () => {
      toast.success("Computo confermato");
      refresh();
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Conferma bloccata"),
  });

  const validaTutte = useMutation({
    mutationFn: async () => (await client.post(`/computi/${id}/valida-ai`, {})).data,
    onSuccess: (d) => {
      toast.success(`Validate ${d.validate} voci AI`);
      refresh();
    },
  });

  const toPrev = useMutation({
    mutationFn: async () => (await client.post(`/computi/${id}/preventivo`, { sconto: 0, iva: 10 })).data,
    onSuccess: (p) => toast.success(`Preventivo ${p.numero} creato`),
    onError: (e) => toast.error(e?.response?.data?.detail || "Errore preventivo"),
  });

  if (isLoading || !computo) {
    return <div className="p-6 text-fog text-sm font-display uppercase tracking-widest">Caricamento…</div>;
  }

  const totali = computo.totali || {};
  const daValidare = Number(totali.n_da_validare || 0);

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/dashboard/computi" className="text-xs text-fog hover:text-brand">← Computi</Link>
          <h1 className="font-display text-2xl uppercase text-ink mt-1">Editor computo</h1>
          <p className="text-fog text-sm">
            Stato <span className="text-ink">{computo.stato}</span> · Totale{" "}
            <span className="text-brand">€ {Number(totali.totale || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}</span>
            {daValidare > 0 && (
              <span className="ml-2 text-brand">· {daValidare} voci AI da validare</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {daValidare > 0 && (
            <button type="button" onClick={() => validaTutte.mutate()} className="px-3 py-2 rounded-xl border border-stroke text-xs font-display uppercase text-ink">
              Valida tutte AI
            </button>
          )}
          <button type="button" onClick={() => conferma.mutate()} className="px-3 py-2 rounded-xl bg-brand text-white text-xs font-display uppercase">
            Conferma
          </button>
          <button type="button" onClick={() => toPrev.mutate()} className="px-3 py-2 rounded-xl border border-brand/40 text-brand text-xs font-display uppercase">
            → Preventivo
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-stroke bg-surface p-4 grid md:grid-cols-12 gap-2 items-end">
        <div className="md:col-span-3">
          <label className="text-[10px] uppercase tracking-wider text-fog font-display">Prezzario</label>
          <select
            className="w-full mt-1 bg-surface-2 border border-stroke rounded-lg px-2 py-2 text-sm text-ink"
            value={activePrezz || ""}
            onChange={(e) => setPrezzarioId(e.target.value)}
          >
            {prezzari.map((p) => (
              <option key={p.id} value={p.id}>{p.nome}</option>
            ))}
          </select>
        </div>
        <div className="md:col-span-6">
          <label className="text-[10px] uppercase tracking-wider text-fog font-display">Voce</label>
          <select
            className="w-full mt-1 bg-surface-2 border border-stroke rounded-lg px-2 py-2 text-sm text-ink"
            value={voceId}
            onChange={(e) => setVoceId(e.target.value)}
          >
            <option value="">Seleziona…</option>
            {vociPrezz.map((v) => (
              <option key={v.id} value={v.id}>
                {v.codice} — {v.descrizione} (€ {Number(v.prezzo_unitario).toFixed(2)})
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-1">
          <label className="text-[10px] uppercase tracking-wider text-fog font-display">Q.tà</label>
          <input type="number" step="0.001" value={qta} onChange={(e) => setQta(e.target.value)}
            className="w-full mt-1 bg-surface-2 border border-stroke rounded-lg px-2 py-2 text-sm text-ink" />
        </div>
        <div className="md:col-span-2">
          <button type="button" disabled={!voceId} onClick={() => add.mutate()}
            className="w-full px-3 py-2 rounded-xl bg-surface-2 border border-stroke text-xs font-display uppercase text-ink disabled:opacity-40">
            Aggiungi
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-stroke">
        <table className="min-w-full text-sm">
          <thead className="bg-surface-2 text-fog font-display uppercase text-[10px] tracking-wider">
            <tr>
              <th className="text-left px-3 py-2">Descrizione</th>
              <th className="text-left px-3 py-2">UM</th>
              <th className="text-right px-3 py-2">Q.tà</th>
              <th className="text-right px-3 py-2">Prezzo</th>
              <th className="text-right px-3 py-2">Totale</th>
              <th className="text-center px-3 py-2">AI</th>
            </tr>
          </thead>
          <tbody>
            {(computo.voci || []).map((v) => (
              <tr key={v.id} className={`border-t border-stroke/60 ${v.generata_da_ai && !v.validata_umano ? "bg-brand/5" : ""}`}>
                <td className="px-3 py-2 text-ink">{v.descrizione}</td>
                <td className="px-3 py-2 text-fog">{v.um}</td>
                <td className="px-3 py-2 text-right">{Number(v.qta).toFixed(2)}</td>
                <td className="px-3 py-2 text-right">€ {Number(v.prezzo_unitario).toFixed(2)}</td>
                <td className="px-3 py-2 text-right text-ink">€ {Number(v.totale || 0).toFixed(2)}</td>
                <td className="px-3 py-2 text-center text-xs">
                  {v.generata_da_ai ? (v.validata_umano ? "ok" : "da validare") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
