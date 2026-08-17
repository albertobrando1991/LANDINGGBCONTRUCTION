import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Loader2,
  Plus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import client from "@/lib/api";
import { fetchComputi, prefetchComputo } from "@/lib/computiPrefetch";
import { toast } from "sonner";
import { refreshLeadViews } from "@/lib/leadSync";

const INITIAL_IMPORT = {
  file: null,
  leadId: "",
  cantiereId: "",
  prezzarioId: "",
  autoPreventivo: true,
  sconto: 0,
  iva: 10,
};

function ImportComputoModal({
  open,
  pending,
  initialLeadId,
  onClose,
  onSubmit,
}) {
  const [form, setForm] = useState(INITIAL_IMPORT);
  const { data: leads = [], isLoading: loadingLeads } = useQuery({
    queryKey: ["leads", "computo-import"],
    queryFn: async () => (await client.get("/leads")).data,
    enabled: open,
  });
  const { data: cantieri = [], isLoading: loadingCantieri } = useQuery({
    queryKey: ["campo-cantieri", "computo-import"],
    queryFn: async () => (await client.get("/campo/cantieri")).data,
    enabled: open,
  });
  const { data: prezzari = [], isLoading: loadingPrezzari } = useQuery({
    queryKey: ["prezzari"],
    queryFn: async () => (await client.get("/prezzario")).data,
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    setForm((current) => ({
      ...INITIAL_IMPORT,
      leadId: initialLeadId || "",
      prezzarioId:
        current.prezzarioId ||
        prezzari.find((prezzario) => prezzario.is_default)?.id ||
        prezzari[0]?.id ||
        "",
    }));
  }, [initialLeadId, open, prezzari]);

  if (!open) return null;
  const loadingOptions = loadingLeads || loadingCantieri || loadingPrezzari;
  const canSubmit =
    form.file && form.leadId && form.prezzarioId && !pending && !loadingOptions;

  const submit = (event) => {
    event.preventDefault();
    if (!canSubmit) return;
    onSubmit(form);
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-computo-title"
    >
      <form
        onSubmit={submit}
        className="max-h-[92vh] w-full max-w-3xl overflow-y-auto border border-stroke bg-surface shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-stroke px-5 py-4">
          <div>
            <p className="text-[10px] font-display uppercase tracking-[0.2em] text-brand">
              Elaborazione automatica
            </p>
            <h2
              id="import-computo-title"
              className="mt-1 text-2xl font-display uppercase text-ink"
            >
              Nuovo computo da PDF ACCA
            </h2>
            <p className="mt-1 text-sm text-fog">
              Associa cliente e listino GB una sola volta: il sistema estrae,
              valorizza e prepara il preventivo.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            aria-label="Chiudi importazione"
            className="flex h-11 w-11 items-center justify-center border border-stroke text-fog hover:text-ink disabled:opacity-40"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid gap-5 p-5 md:grid-cols-2">
          <label className="md:col-span-2">
            <span className="text-[10px] font-display uppercase tracking-wider text-fog">
              Computo metrico ACCA / PriMus
            </span>
            <span className="mt-2 flex min-h-24 cursor-pointer items-center gap-4 border border-dashed border-brand/60 bg-brand/5 px-4 py-3 focus-within:outline focus-within:outline-2 focus-within:outline-brand">
              <FileText className="h-7 w-7 shrink-0 text-brand" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-ink">
                  {form.file?.name || "Seleziona il PDF del computo"}
                </span>
                <span className="mt-1 block text-xs text-fog">
                  PDF ACCA, massimo 15 MB. Il totale deve quadrare al centesimo.
                </span>
              </span>
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    file: event.target.files?.[0] || null,
                  }))
                }
              />
            </span>
          </label>

          <label>
            <span className="text-[10px] font-display uppercase tracking-wider text-fog">
              Cliente / lead obbligatorio
            </span>
            <select
              value={form.leadId}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  leadId: event.target.value,
                }))
              }
              className="mt-1 h-11 w-full border border-stroke bg-surface-2 px-3 text-sm text-ink"
            >
              <option value="">Seleziona il cliente...</option>
              {leads.map((lead) => (
                <option key={lead.id} value={lead.id}>
                  {lead.nome} - {lead.email || lead.citta || "senza recapito"}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-[10px] font-display uppercase tracking-wider text-fog">
              Cantiere facoltativo
            </span>
            <select
              value={form.cantiereId}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  cantiereId: event.target.value,
                }))
              }
              className="mt-1 h-11 w-full border border-stroke bg-surface-2 px-3 text-sm text-ink"
            >
              <option value="">Intervento non ancora aperto</option>
              {cantieri.map((cantiere) => (
                <option key={cantiere.id} value={cantiere.id}>
                  {cantiere.cliente} - {cantiere.indirizzo || cantiere.stato}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-[10px] font-display uppercase tracking-wider text-fog">
              Listino prezzi GB
            </span>
            <select
              value={form.prezzarioId}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  prezzarioId: event.target.value,
                }))
              }
              className="mt-1 h-11 w-full border border-stroke bg-surface-2 px-3 text-sm text-ink"
            >
              <option value="">Seleziona il listino...</option>
              {prezzari.map((prezzario) => (
                <option key={prezzario.id} value={prezzario.id}>
                  {prezzario.nome}
                  {prezzario.is_default ? " - predefinito" : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="text-[10px] font-display uppercase tracking-wider text-fog">
                Sconto %
              </span>
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={form.sconto}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    sconto: event.target.value,
                  }))
                }
                className="mt-1 h-11 w-full border border-stroke bg-surface-2 px-3 text-right text-sm text-ink"
              />
            </label>
            <label>
              <span className="text-[10px] font-display uppercase tracking-wider text-fog">
                IVA %
              </span>
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={form.iva}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    iva: event.target.value,
                  }))
                }
                className="mt-1 h-11 w-full border border-stroke bg-surface-2 px-3 text-right text-sm text-ink"
              />
            </label>
          </div>

          <label className="md:col-span-2 flex cursor-pointer items-start gap-3 border border-stroke bg-surface-2 p-4">
            <input
              type="checkbox"
              checked={form.autoPreventivo}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  autoPreventivo: event.target.checked,
                }))
              }
              className="mt-1 h-4 w-4 rounded border-stroke text-brand focus:ring-brand"
            />
            <span>
              <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                <CheckCircle2 className="h-4 w-4 text-success" />
                Genera automaticamente il preventivo professionale
              </span>
              <span className="mt-1 block text-xs leading-5 text-fog">
                Il sistema procede soltanto se ogni codice ACCA trova una sola
                voce GB con la stessa unità di misura. Ambiguità e voci mancanti
                vengono fermate nell’editor. La bozza generata resta sempre
                modificabile e non viene confermata automaticamente.
              </span>
            </span>
          </label>

          <div className="md:col-span-2 flex items-start gap-3 border-l-2 border-amber-400 bg-amber-400/5 px-4 py-3 text-xs leading-5 text-fog">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            La precisione è protetta da tre controlli: quadratura del PDF,
            numerazione completa delle voci e corrispondenza univoca codice +
            UM.
          </div>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-stroke px-5 py-4 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="min-h-11 border border-stroke px-5 text-xs font-display uppercase text-fog hover:text-ink disabled:opacity-40"
          >
            Annulla
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex min-h-11 items-center justify-center gap-2 bg-brand px-5 text-xs font-display uppercase tracking-wider text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {pending ? "Elaborazione in corso..." : "Importa ed elabora"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function Computi() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedLeadId = searchParams.get("lead") || "";
  const [importOpen, setImportOpen] = useState(
    searchParams.get("import") === "1",
  );
  const { data: computi = [], isLoading } = useQuery({
    queryKey: ["computi"],
    queryFn: fetchComputi,
  });

  const crea = useMutation({
    mutationFn: async ({ leadId } = {}) =>
      (
        await client.post("/computi", {
          tipo: "estimativo",
          lead_id: leadId || undefined,
        })
      ).data,
    onSuccess: (computo) => {
      toast.success("Computo creato");
      qc.invalidateQueries({ queryKey: ["computi"] });
      refreshLeadViews(qc, { leadId: requestedLeadId || undefined });
      navigate(`/dashboard/computi/${computo.id}`);
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore creazione"),
  });

  const importa = useMutation({
    mutationFn: async (options) => {
      const form = new FormData();
      form.append("file", options.file);
      form.append("lead_id", options.leadId);
      if (options.cantiereId) form.append("cantiere_id", options.cantiereId);
      form.append("prezzario_id", options.prezzarioId);
      form.append("auto_preventivo", String(options.autoPreventivo));
      form.append("sconto", String(options.sconto || 0));
      form.append("iva", String(options.iva || 0));
      return (await client.post("/computi/importa-pdf", form)).data;
    },
    onSuccess: (computo) => {
      const extraction = computo.importazione || {};
      setImportOpen(false);
      qc.invalidateQueries({ queryKey: ["computi"] });
      qc.invalidateQueries({ queryKey: ["preventivi"] });
      refreshLeadViews(qc, { leadId: requestedLeadId || undefined });
      if (computo.preventivo) {
        toast.success(
          `${extraction.n_voci || 0} voci estratte. Bozza ${computo.preventivo.numero} creata: controlla e modifica le singole voci prima della conferma.`,
        );
        navigate(`/dashboard/computi/${computo.id}`);
        return;
      }
      if (Number(extraction.n_da_verificare || 0) > 0) {
        toast.warning(
          `${extraction.n_prezzi_gb || 0}/${extraction.n_voci || 0} prezzi GB abbinati. Verifica le voci evidenziate.`,
        );
      } else {
        toast.success("Computo importato e pronto per la conferma");
      }
      navigate(`/dashboard/computi/${computo.id}`);
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Importazione PDF non riuscita",
      ),
  });

  const elimina = useMutation({
    mutationFn: async (computo) =>
      (await client.delete(`/computi/${computo.id}`)).data,
    onMutate: async (computo) => {
      await qc.cancelQueries({ queryKey: ["computi"] });
      const previous = qc.getQueryData(["computi"]);
      qc.setQueryData(["computi"], (current = []) =>
        current.filter((item) => String(item.id) !== String(computo.id)),
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Computo eliminato");
      void qc.invalidateQueries({ queryKey: ["computi"] });
      void qc.invalidateQueries({ queryKey: ["preventivi"] });
    },
    onError: (error, _computo, context) => {
      if (context?.previous !== undefined) {
        qc.setQueryData(["computi"], context.previous);
      }
      toast.error(
        error?.response?.data?.detail || "Impossibile eliminare il computo",
      );
    },
  });

  if (isLoading) {
    return (
      <div className="p-6 text-sm font-display uppercase tracking-widest text-fog">
        Caricamento computi...
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display uppercase text-ink">Computi</h1>
          <p className="text-sm text-fog">
            Importazione ACCA, prezzi GB, controllo e preventivo automatico
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={() => setImportOpen(true)}
            className="inline-flex min-h-11 items-center gap-2 border border-brand px-3 py-2 text-xs font-display uppercase tracking-wider text-brand"
          >
            <Upload className="h-4 w-4" /> Importa ed elabora
          </button>
          <button
            type="button"
            onClick={() => crea.mutate({ leadId: requestedLeadId })}
            className="inline-flex min-h-11 items-center gap-2 bg-brand px-3 py-2 text-xs font-display uppercase tracking-wider text-white"
          >
            <Plus className="h-4 w-4" />
            {requestedLeadId ? "Nuovo manuale per il cliente" : "Nuovo manuale"}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto border border-stroke">
        <table className="min-w-full text-sm">
          <thead className="bg-surface-2 text-[10px] font-display uppercase tracking-wider text-fog">
            <tr>
              <th className="px-3 py-2 text-left">Computo</th>
              <th className="px-3 py-2 text-left">Cliente</th>
              <th className="px-3 py-2 text-left">Tipo</th>
              <th className="px-3 py-2 text-left">Stato</th>
              <th className="px-3 py-2 text-right">Totale</th>
              <th className="px-3 py-2 text-right">Voci</th>
              <th className="px-3 py-2 text-right">Da verificare</th>
              <th className="px-3 py-2 text-right">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {computi.map((computo) => (
              <tr
                key={computo.id}
                className="border-t border-stroke/60 hover:bg-surface-2/40"
              >
                <td className="px-3 py-2">
                  <Link
                    to={`/dashboard/computi/${computo.id}`}
                    onPointerEnter={() => void prefetchComputo(qc, computo.id)}
                    onPointerDown={() => void prefetchComputo(qc, computo.id)}
                    onFocus={() => void prefetchComputo(qc, computo.id)}
                    className="font-mono text-xs text-brand"
                  >
                    {computo.numero || `${String(computo.id).slice(0, 8)}...`}
                  </Link>
                </td>
                <td className="px-3 py-2 text-ink">
                  {computo.cliente || "Non associato"}
                </td>
                <td className="px-3 py-2 text-fog">{computo.tipo}</td>
                <td className="px-3 py-2">
                  <span className="border border-stroke bg-surface-2 px-2 py-0.5 text-[10px] uppercase tracking-wider text-ink">
                    {computo.stato}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-ink">
                  €{" "}
                  {Number(computo.totale || 0).toLocaleString("it-IT", {
                    minimumFractionDigits: 2,
                  })}
                </td>
                <td className="px-3 py-2 text-right text-fog">
                  {computo.n_voci || 0}
                </td>
                <td className="px-3 py-2 text-right">
                  {Number(computo.n_da_validare || 0) > 0 ? (
                    <span className="font-display text-xs text-brand">
                      {computo.n_da_validare}
                    </span>
                  ) : (
                    <span className="text-success">0</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    aria-label={`Elimina computo ${computo.numero || computo.id}`}
                    title="Elimina computo"
                    disabled={elimina.isPending}
                    onClick={() => {
                      const label =
                        computo.numero || String(computo.id).slice(0, 8);
                      if (
                        window.confirm(
                          `Eliminare definitivamente il computo ${label}? La bozza preventivo collegata, il contratto e la relativa documentazione verranno eliminati insieme.`,
                        )
                      ) {
                        elimina.mutate(computo);
                      }
                    }}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-red-500/30 text-red-400 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-35"
                  >
                    {elimina.isPending &&
                    elimina.variables?.id === computo.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ImportComputoModal
        open={importOpen}
        pending={importa.isPending}
        initialLeadId={requestedLeadId}
        onClose={() => setImportOpen(false)}
        onSubmit={(options) => importa.mutate(options)}
      />
    </div>
  );
}
