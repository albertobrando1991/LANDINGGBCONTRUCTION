import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Copy, RefreshCw, Star, Upload } from "lucide-react";
import client from "@/lib/api";
import { toast } from "sonner";

export default function Prezzario() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");

  const { data: prezzari = [], isLoading } = useQuery({
    queryKey: ["prezzari"],
    queryFn: async () => (await client.get("/prezzario")).data,
  });

  const activeId = selected || prezzari.find((p) => p.is_default)?.id || prezzari[0]?.id;

  const { data: voci = [] } = useQuery({
    queryKey: ["prezzario-voci", activeId, q],
    enabled: Boolean(activeId),
    queryFn: async () =>
      (await client.get(`/prezzario/${activeId}/voci`, { params: { q: q || undefined } })).data,
  });

  const duplica = useMutation({
    mutationFn: async (id) =>
      (
        await client.post(`/prezzario/${id}/duplica`, {
          nome: "Listino personalizzato",
          rendi_default: true,
        })
      ).data,
    onSuccess: (data) => {
      toast.success("Prezzario duplicato e impostato come predefinito");
      setSelected(data.id);
      qc.invalidateQueries({ queryKey: ["prezzari"] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Errore duplicazione"),
  });

  const impostaDefault = useMutation({
    mutationFn: async (id) =>
      (await client.post(`/prezzario/${id}/default`)).data,
    onSuccess: (data) => {
      toast.success("Prezzario predefinito aggiornato");
      setSelected(data.id);
      qc.invalidateQueries({ queryKey: ["prezzari"] });
    },
    onError: (e) =>
      toast.error(e?.response?.data?.detail || "Errore aggiornamento predefinito"),
  });

  const ripristina = useMutation({
    mutationFn: async () =>
      (await client.post("/prezzario/ripristina", { prezzario_id: activeId })).data,
    onSuccess: (d) => {
      toast.success(`Ripristinate ${d.ripristinate} voci`);
      qc.invalidateQueries({ queryKey: ["prezzario-voci"] });
    },
    onError: (e) => toast.error(e?.response?.data?.detail || "Errore ripristino"),
  });

  const active = useMemo(() => prezzari.find((p) => p.id === activeId), [prezzari, activeId]);

  if (isLoading) {
    return <div className="p-6 text-fog font-display uppercase tracking-widest text-sm">Caricamento prezzari…</div>;
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl uppercase text-ink">Prezzario</h1>
          <p className="text-fog text-sm font-body">Listini Campania e personalizzati per tenant</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {active && (
            <>
              <button
                type="button"
                onClick={() => duplica.mutate(active.id)}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-2 border border-stroke text-xs font-display uppercase tracking-wider text-ink hover:border-brand"
              >
                <Copy className="w-4 h-4" /> Duplica
              </button>
              {!active.is_default && (
                <button
                  type="button"
                  onClick={() => impostaDefault.mutate(active.id)}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-2 border border-stroke text-xs font-display uppercase tracking-wider text-ink hover:border-brand"
                >
                  <Star className="w-4 h-4" /> Usa come default
                </button>
              )}
              {!active.is_sistema && (
                <button
                  type="button"
                  onClick={() => ripristina.mutate()}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-2 border border-stroke text-xs font-display uppercase tracking-wider text-ink hover:border-brand"
                >
                  <RefreshCw className="w-4 h-4" /> Ripristina Campania
                </button>
              )}
              <Link
                to={`/dashboard/prezzario/wizard?id=${active.id}`}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-brand/20 border border-brand/40 text-xs font-display uppercase tracking-wider text-brand"
              >
                Wizard 28 voci
              </Link>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {prezzari.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setSelected(p.id)}
            className={`px-3 py-2 rounded-xl text-xs font-display uppercase tracking-wider border ${
              p.id === activeId ? "border-brand bg-brand/15 text-brand" : "border-stroke text-fog"
            }`}
          >
            {p.nome} {p.is_sistema ? "· sistema" : ""} {p.is_default ? "· default" : ""}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Cerca voce o codice…"
          className="w-full max-w-md bg-surface border border-stroke rounded-xl px-3 py-2 text-sm text-ink"
        />
        <label className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-stroke text-xs font-display uppercase text-fog cursor-pointer">
          <Upload className="w-4 h-4" /> CSV
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file || !activeId) return;
              const fd = new FormData();
              fd.append("file", file);
              try {
                const { data } = await client.post(`/prezzario/${activeId}/importa-csv`, fd);
                toast.success(`Importate ${data.importate}, scarti ${data.n_scarti}`);
                qc.invalidateQueries({ queryKey: ["prezzario-voci"] });
              } catch (err) {
                toast.error(err?.response?.data?.detail || "Import fallito");
              }
            }}
          />
        </label>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-stroke">
        <table className="min-w-full text-sm">
          <thead className="bg-surface-2 text-fog font-display uppercase text-[10px] tracking-wider">
            <tr>
              <th className="text-left px-3 py-2">Codice</th>
              <th className="text-left px-3 py-2">Descrizione</th>
              <th className="text-left px-3 py-2">Cat.</th>
              <th className="text-left px-3 py-2">UM</th>
              <th className="text-right px-3 py-2">Prezzo</th>
              <th className="text-center px-3 py-2">Wizard</th>
            </tr>
          </thead>
          <tbody>
            {voci.map((v) => (
              <tr key={v.id} className="border-t border-stroke/60 hover:bg-surface-2/40">
                <td className="px-3 py-2 text-fog font-mono text-xs">{v.codice}</td>
                <td className="px-3 py-2 text-ink">{v.descrizione}</td>
                <td className="px-3 py-2 text-fog">{v.categoria}</td>
                <td className="px-3 py-2 text-fog">{v.um}</td>
                <td className="px-3 py-2 text-right text-ink">€ {Number(v.prezzo_unitario).toFixed(2)}</td>
                <td className="px-3 py-2 text-center">{v.chiave_wizard ? "★" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
