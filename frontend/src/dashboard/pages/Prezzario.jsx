import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Copy, Pencil, Plus, RefreshCw, Save, Star, Upload, X } from "lucide-react";
import client from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

const EMPTY_VOCE = {
  codice: "",
  super_categoria: "Lavorazioni",
  categoria: "Generale",
  sub_categoria: "",
  descrizione: "",
  um: "cad",
  prezzo_unitario: "",
  tipo: "a_misura",
};

export default function Prezzario() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState(null);
  const [voceForm, setVoceForm] = useState(EMPTY_VOCE);

  const { data: prezzari = [], isLoading } = useQuery({
    queryKey: ["prezzari"],
    queryFn: async () => (await client.get("/prezzario")).data,
  });

  const activeId = selected || prezzari.find((p) => p.is_default)?.id || prezzari[0]?.id;

  const { data: vociData = { items: [], total: 0, pages: 1 } } = useQuery({
    queryKey: ["prezzario-voci", activeId, q, page],
    enabled: Boolean(activeId),
    queryFn: async () =>
      (await client.get(`/prezzario/${activeId}/voci`, { params: { q: q || undefined, page, page_size: 50 } })).data,
  });
  const voci = vociData.items || [];

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

  const salvaVoce = useMutation({
    mutationFn: async () => {
      const body = {
        ...voceForm,
        codice: voceForm.codice.trim() || null,
        sub_categoria: voceForm.sub_categoria.trim() || null,
        prezzo_unitario: Number(voceForm.prezzo_unitario),
      };
      if (editor === "new") {
        return (await client.post(`/prezzario/${activeId}/voci`, body)).data;
      }
      return (
        await client.patch(`/prezzario/${activeId}/voci/${editor}`, body)
      ).data;
    },
    onSuccess: () => {
      toast.success(editor === "new" ? "Nuova voce aggiunta" : "Voce aggiornata");
      setEditor(null);
      setVoceForm(EMPTY_VOCE);
      qc.invalidateQueries({ queryKey: ["prezzario-voci", activeId] });
      qc.invalidateQueries({ queryKey: ["prezzari"] });
    },
    onError: (e) =>
      toast.error(e?.response?.data?.detail || "Salvataggio voce non riuscito"),
  });

  const active = useMemo(() => prezzari.find((p) => p.id === activeId), [prezzari, activeId]);
  const canEdit = ["owner", "admin"].includes(user?.role) && active && !active.is_sistema;

  const openNew = () => {
    setVoceForm(EMPTY_VOCE);
    setEditor("new");
  };

  const openEdit = (voce) => {
    setVoceForm({
      codice: voce.codice || "",
      super_categoria: voce.super_categoria || "Lavorazioni",
      categoria: voce.categoria || "Generale",
      sub_categoria: voce.sub_categoria || "",
      descrizione: voce.descrizione || "",
      um: voce.um || "cad",
      prezzo_unitario: String(voce.prezzo_unitario ?? ""),
      tipo: voce.tipo || "a_misura",
    });
    setEditor(voce.id);
  };

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
              {canEdit && (
                <button
                  type="button"
                  onClick={openNew}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-brand text-xs font-display uppercase tracking-wider text-white"
                >
                  <Plus className="w-4 h-4" /> Nuova voce
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {prezzari.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => { setSelected(p.id); setPage(1); }}
            className={`px-3 py-2 rounded-xl text-xs font-display uppercase tracking-wider border ${
              p.id === activeId ? "border-brand bg-brand/15 text-brand" : "border-stroke text-fog"
            }`}
          >
            {p.nome} {p.is_sistema ? "· sistema" : ""} {p.is_default ? "· default" : ""}
          </button>
        ))}
      </div>

      {editor && canEdit && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            salvaVoce.mutate();
          }}
          className="rounded-2xl border border-brand/40 bg-surface p-4 space-y-4"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-sm uppercase text-ink">
              {editor === "new" ? "Aggiungi voce al Listino GB" : "Modifica voce Listino GB"}
            </h2>
            <button type="button" onClick={() => setEditor(null)} aria-label="Chiudi editor">
              <X className="h-4 w-4 text-fog" />
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <input value={voceForm.codice} onChange={(e) => setVoceForm((v) => ({ ...v, codice: e.target.value }))} placeholder="Codice" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink" />
            <input required value={voceForm.super_categoria} onChange={(e) => setVoceForm((v) => ({ ...v, super_categoria: e.target.value }))} placeholder="Super categoria" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink" />
            <input required value={voceForm.categoria} onChange={(e) => setVoceForm((v) => ({ ...v, categoria: e.target.value }))} placeholder="Categoria" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink" />
            <input value={voceForm.sub_categoria} onChange={(e) => setVoceForm((v) => ({ ...v, sub_categoria: e.target.value }))} placeholder="Sottocategoria" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink" />
            <input required value={voceForm.descrizione} onChange={(e) => setVoceForm((v) => ({ ...v, descrizione: e.target.value }))} placeholder="Descrizione lavorazione" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink md:col-span-2" />
            <select value={voceForm.um} onChange={(e) => setVoceForm((v) => ({ ...v, um: e.target.value }))} className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink">
              {["mq", "ml", "mc", "cad", "corpo", "kg", "h", "n"].map((um) => <option key={um} value={um}>{um}</option>)}
            </select>
            <input required min="0" step="0.01" type="number" value={voceForm.prezzo_unitario} onChange={(e) => setVoceForm((v) => ({ ...v, prezzo_unitario: e.target.value }))} placeholder="Prezzo unitario" className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink" />
          </div>
          <button type="submit" disabled={salvaVoce.isPending} className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 font-display text-xs uppercase text-white disabled:opacity-60">
            <Save className="h-4 w-4" /> Salva voce
          </button>
        </form>
      )}

      <div className="flex items-center gap-2">
        <input
          aria-label="Cerca voce o codice nel prezzario"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
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

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-fog">
        <span>{Number(vociData.total || 0).toLocaleString("it-IT")} voci complete · pagina {page} di {vociData.pages || 1}</span>
        <div className="flex gap-2">
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-stroke p-2 disabled:opacity-40" aria-label="Pagina precedente"><ChevronLeft className="h-4 w-4" /></button>
          <button type="button" disabled={page >= (vociData.pages || 1)} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-stroke p-2 disabled:opacity-40" aria-label="Pagina successiva"><ChevronRight className="h-4 w-4" /></button>
        </div>
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
              {canEdit && <th className="text-center px-3 py-2">Modifica</th>}
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
                {canEdit && (
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      onClick={() => openEdit(v)}
                      className="rounded-lg border border-stroke p-2 text-fog hover:border-brand hover:text-brand"
                      aria-label={`Modifica ${v.descrizione}`}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
