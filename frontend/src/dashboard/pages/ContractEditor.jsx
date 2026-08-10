import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  FilePlus2,
  Loader2,
  MailPlus,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import client, { extractErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";

const DOCUMENT_TYPES = [
  ["contratto", "Contratto"],
  ["sal", "SAL"],
  ["fattura", "Fattura"],
  ["contabile_pagamento", "Contabile pagamento"],
  ["ricevuta", "Ricevuta"],
  ["extra", "Extra"],
  ["verbale", "Verbale"],
  ["altro", "Altro"],
];

function statusLabel(status) {
  return (
    {
      bozza: "Bozza modificabile",
      validato: "Validato",
      pubblicato: "Validato e pubblicato",
      firmato: "Firmato",
    }[status] || "Non ancora salvato"
  );
}

export default function ContractEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sections, setSections] = useState([]);
  const [invite, setInvite] = useState({ email: "", nome: "" });
  const [document, setDocument] = useState({
    tipo: "altro",
    titolo: "",
    file: null,
  });
  const { data, isLoading } = useQuery({
    queryKey: ["contract-editor", id],
    queryFn: async () => (await client.get(`/preventivi/${id}/contratto`)).data,
  });

  useEffect(() => {
    if (data?.sezioni) setSections(data.sezioni);
    if (data?.preventivo) {
      setInvite((current) => ({
        email: current.email || data.preventivo.cliente_email || "",
        nome: current.nome || data.preventivo.cliente_nome || "",
      }));
    }
  }, [data]);

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["contract-editor", id] });

  const save = useMutation({
    mutationFn: () =>
      client.put(`/preventivi/${id}/contratto/bozza`, { sezioni: sections }),
    onSuccess: () => {
      refresh();
      toast.success("Bozza e nuova versione salvate");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });
  const validate = useMutation({
    mutationFn: async () => {
      await client.put(`/preventivi/${id}/contratto/bozza`, {
        sezioni: sections,
      });
      return client.post(`/preventivi/${id}/contratto/valida`);
    },
    onSuccess: () => {
      refresh();
      toast.success("Contratto validato e pubblicato nell'area cliente");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });
  const inviteClient = useMutation({
    mutationFn: () => client.post(`/preventivi/${id}/portale/invita`, invite),
    onSuccess: (response) => {
      refresh();
      toast.success(
        response.data.invited
          ? "Invito cliente inviato"
          : "Accesso cliente collegato ed email inviata",
      );
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });
  const upload = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("file", document.file);
      form.append("tipo", document.tipo);
      form.append("titolo", document.titolo);
      form.append("preventivo_id", id);
      return client.post("/documenti-cliente", form);
    },
    onSuccess: () => {
      setDocument({ tipo: "altro", titolo: "", file: null });
      refresh();
      toast.success("Documento pubblicato nel fascicolo cliente");
    },
    onError: async (error) => toast.error(await extractErrorDetail(error)),
  });

  const updateSection = (index, field, value) =>
    setSections((current) =>
      current.map((section, sectionIndex) =>
        sectionIndex === index ? { ...section, [field]: value } : section,
      ),
    );
  const removeSection = (index) =>
    setSections((current) =>
      current.filter((_, sectionIndex) => sectionIndex !== index),
    );
  const addSection = () =>
    setSections((current) => [
      ...current,
      { titolo: `ART. ${current.length + 1} — NUOVA SEZIONE`, testo: "" },
    ]);

  const downloadContract = async () => {
    try {
      const response = await client.get(`/preventivi/${id}/contratto/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${data?.contratto?.numero || "contratto"}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(await extractErrorDetail(error));
    }
  };
  const downloadDocument = async (item) => {
    if (!item.storage_path) return downloadContract();
    try {
      const response = await client.get(
        `/documenti-cliente/${item.id}/download`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = item.nome_file || item.titolo;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(await extractErrorDetail(error));
    }
  };

  if (isLoading)
    return (
      <div className="py-16 text-center text-fog">Caricamento editor…</div>
    );
  const choice = data?.scelta_pagamento;
  const selectedOption = data?.modalita_pagamento?.find(
    (item) => item.tipo === choice?.tipo,
  );
  const ready = Boolean(choice);

  return (
    <div className="space-y-6 pb-16">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/dashboard/preventivi")}
            className="rounded-xl border border-stroke p-2 text-fog hover:text-brand"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <p className="font-display text-[10px] uppercase tracking-wider text-brand">
              {data?.preventivo?.numero}
            </p>
            <h1 className="font-display text-2xl font-bold uppercase text-ink">
              Editor contratto
            </h1>
            <p className="text-xs text-fog">
              {data?.preventivo?.cliente_nome} ·{" "}
              {formatEuro(data?.preventivo?.totale_documento)}
            </p>
          </div>
        </div>
        <span className="rounded-full border border-stroke bg-surface px-3 py-2 font-display text-[10px] uppercase text-fog">
          {statusLabel(data?.contratto?.stato)} · v
          {data?.contratto?.versione_corrente || 0}
        </span>
      </div>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-stroke bg-surface p-5">
          <div className="flex items-center gap-2 text-brand">
            <MailPlus className="h-4 w-4" />
            <h2 className="font-display text-xs uppercase">Accesso cliente</h2>
          </div>
          <p className="mt-2 text-xs leading-5 text-fog">
            Invita il cliente: troverà il preventivo nel portale e dovrà
            scegliere il pagamento prima della validazione.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <input
              value={invite.nome}
              onChange={(e) => setInvite({ ...invite, nome: e.target.value })}
              placeholder="Nome cliente"
              className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink"
            />
            <input
              type="email"
              value={invite.email}
              onChange={(e) => setInvite({ ...invite, email: e.target.value })}
              placeholder="Email cliente"
              className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink"
            />
          </div>
          <button
            type="button"
            disabled={!invite.email || inviteClient.isPending}
            onClick={() => inviteClient.mutate()}
            className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 font-display text-[10px] uppercase text-white disabled:opacity-40"
          >
            {inviteClient.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <MailPlus className="h-4 w-4" />
            )}{" "}
            Invita o collega
          </button>
          {(data?.clienti || []).map((clientItem) => (
            <p
              key={clientItem.user_id}
              className="mt-3 text-xs text-emerald-400"
            >
              Accesso attivo: {clientItem.email}
            </p>
          ))}
        </div>
        <div
          className={`rounded-2xl border p-5 ${ready ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5"}`}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck
              className={`h-4 w-4 ${ready ? "text-emerald-400" : "text-amber-400"}`}
            />
            <h2 className="font-display text-xs uppercase">
              Modalità scelta dal cliente
            </h2>
          </div>
          {ready ? (
            <>
              <p className="mt-3 font-display text-sm uppercase text-ink">
                {selectedOption?.titolo}
              </p>
              <p className="mt-2 text-xs leading-5 text-fog">
                {selectedOption?.sintesi}
              </p>
              <p className="mt-3 inline-flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle2 className="h-4 w-4" /> Confermata dal cliente
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-amber-300">
              In attesa della scelta nel portale cliente. La validazione resta
              bloccata.
            </p>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-sm font-semibold uppercase text-ink">
              Testo contrattuale
            </h2>
            <p className="mt-1 text-xs text-fog">
              Ogni salvataggio crea una nuova versione; la validazione congela
              lo snapshot pubblicato.
            </p>
          </div>
          <button
            type="button"
            onClick={addSection}
            className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 font-display text-[10px] uppercase text-fog hover:border-brand hover:text-brand"
          >
            <Plus className="h-4 w-4" /> Aggiungi parte
          </button>
        </div>
        {sections.map((section, index) => (
          <article
            key={`${index}-${section.titolo}`}
            className="rounded-2xl border border-stroke bg-surface p-4"
          >
            <div className="flex gap-3">
              <input
                value={section.titolo}
                onChange={(e) => updateSection(index, "titolo", e.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-stroke bg-bg px-3 py-2 font-display text-xs uppercase text-ink"
                aria-label={`Titolo sezione ${index + 1}`}
              />
              <button
                type="button"
                onClick={() => removeSection(index)}
                disabled={sections.length === 1}
                className="rounded-xl border border-stroke p-2 text-fog hover:text-red-400 disabled:opacity-30"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            <textarea
              value={section.testo}
              onChange={(e) => updateSection(index, "testo", e.target.value)}
              rows={4}
              className="mt-3 w-full rounded-xl border border-stroke bg-bg px-3 py-2 font-body text-sm leading-6 text-ink"
              aria-label={`Testo sezione ${index + 1}`}
            />
          </article>
        ))}
      </section>

      <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-end gap-3 rounded-2xl border border-stroke bg-bg/95 p-3 shadow-xl backdrop-blur">
        {data?.contratto?.stato && data.contratto.stato !== "bozza" && (
          <button
            type="button"
            onClick={downloadContract}
            className="inline-flex items-center gap-2 rounded-xl border border-stroke px-4 py-3 font-display text-[10px] uppercase text-ink"
          >
            <Download className="h-4 w-4" /> Scarica PDF
          </button>
        )}
        <button
          type="button"
          disabled={save.isPending}
          onClick={() => save.mutate()}
          className="inline-flex items-center gap-2 rounded-xl border border-brand px-4 py-3 font-display text-[10px] uppercase text-brand disabled:opacity-40"
        >
          <Save className="h-4 w-4" /> Salva versione
        </button>
        <button
          type="button"
          disabled={!ready || validate.isPending}
          onClick={() => validate.mutate()}
          className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-[10px] uppercase text-white disabled:opacity-40"
        >
          {validate.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ShieldCheck className="h-4 w-4" />
          )}{" "}
          Valida e pubblica
        </button>
      </div>

      <section className="rounded-2xl border border-stroke bg-surface p-5">
        <div className="flex items-center gap-2">
          <FilePlus2 className="h-4 w-4 text-brand" />
          <h2 className="font-display text-xs uppercase text-ink">
            Fascicolo documentale cliente
          </h2>
        </div>
        <p className="mt-2 text-xs text-fog">
          Contratti, SAL, fatture, contabili, ricevute, verbali ed extra restano
          consultabili e scaricabili nel portale.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-[180px_1fr_1fr_auto]">
          <select
            value={document.tipo}
            onChange={(e) => setDocument({ ...document, tipo: e.target.value })}
            className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink"
          >
            {DOCUMENT_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            value={document.titolo}
            onChange={(e) =>
              setDocument({ ...document, titolo: e.target.value })
            }
            placeholder="Titolo documento"
            className="rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink"
          />
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx"
            onChange={(e) =>
              setDocument({ ...document, file: e.target.files?.[0] || null })
            }
            className="rounded-xl border border-stroke bg-bg px-3 py-2 text-xs text-fog"
          />
          <button
            type="button"
            disabled={!document.file || !document.titolo || upload.isPending}
            onClick={() => upload.mutate()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2 font-display text-[10px] uppercase text-white disabled:opacity-40"
          >
            <Upload className="h-4 w-4" /> Pubblica
          </button>
        </div>
        <div className="mt-5 grid gap-2">
          {(data?.documenti || []).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => downloadDocument(item)}
              className="flex items-center justify-between gap-3 rounded-xl border border-stroke bg-bg p-3 text-left hover:border-brand"
            >
              <div>
                <p className="font-display text-xs uppercase text-ink">
                  {item.titolo}
                </p>
                <p className="mt-1 text-[11px] text-fog">
                  {item.tipo.replaceAll("_", " ")} · {item.provenienza} ·{" "}
                  {item.stato}
                </p>
              </div>
              <Download className="h-4 w-4 text-brand" />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
