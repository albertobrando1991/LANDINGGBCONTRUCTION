import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  Check,
  Copy,
  FileDown,
  Loader2,
  Save,
  Trash2,
} from "lucide-react";
import client from "@/lib/api";
import { moveVoceIds } from "@/lib/computo";
import { toast } from "sonner";
import VarianteComparison from "@/dashboard/components/VarianteComparison";

const LOCKED_STATES = new Set(["confermato", "archiviato"]);

function IconButton({ label, disabled, onClick, children, danger = false }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-35 ${
        danger
          ? "border-red-500/30 text-red-400 hover:bg-red-500/10"
          : "border-stroke text-fog hover:border-brand/50 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function VoceRow({
  voce,
  index,
  total,
  locked,
  saving,
  removing,
  validating,
  reordering,
  onSave,
  onRemove,
  onValidate,
  onMove,
}) {
  const [draft, setDraft] = useState({
    descrizione: voce.descrizione,
    qta: String(voce.qta),
    prezzo_unitario: String(voce.prezzo_unitario),
  });

  useEffect(() => {
    setDraft({
      descrizione: voce.descrizione,
      qta: String(voce.qta),
      prezzo_unitario: String(voce.prezzo_unitario),
    });
  }, [voce.descrizione, voce.prezzo_unitario, voce.qta]);

  const description = draft.descrizione.trim();
  const quantity = Number(draft.qta);
  const unitPrice = Number(draft.prezzo_unitario);
  const changed =
    description !== voce.descrizione ||
    quantity !== Number(voce.qta) ||
    unitPrice !== Number(voce.prezzo_unitario);
  const valid =
    description.length > 0 &&
    Number.isFinite(quantity) &&
    quantity >= 0 &&
    Number.isFinite(unitPrice) &&
    unitPrice >= 0;

  return (
    <tr
      className={`border-t border-stroke/60 ${
        voce.generata_da_ai && !voce.validata_umano ? "bg-brand/5" : ""
      }`}
    >
      <td className="min-w-[280px] px-3 py-2">
        <input
          aria-label={`Descrizione voce ${index + 1}`}
          value={draft.descrizione}
          disabled={locked}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              descrizione: event.target.value,
            }))
          }
          className="w-full rounded-lg border border-stroke bg-surface-2 px-2 py-1.5 text-sm text-ink disabled:border-transparent disabled:bg-transparent"
        />
      </td>
      <td className="px-3 py-2 text-fog">{voce.um}</td>
      <td className="w-28 px-3 py-2">
        <input
          aria-label={`Quantità voce ${index + 1}`}
          type="number"
          min="0"
          step="0.001"
          value={draft.qta}
          disabled={locked}
          onChange={(event) =>
            setDraft((current) => ({ ...current, qta: event.target.value }))
          }
          className="w-full rounded-lg border border-stroke bg-surface-2 px-2 py-1.5 text-right text-sm text-ink disabled:border-transparent disabled:bg-transparent"
        />
      </td>
      <td className="w-32 px-3 py-2">
        <input
          aria-label={`Prezzo voce ${index + 1}`}
          type="number"
          min="0"
          step="0.01"
          value={draft.prezzo_unitario}
          disabled={locked}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              prezzo_unitario: event.target.value,
            }))
          }
          className="w-full rounded-lg border border-stroke bg-surface-2 px-2 py-1.5 text-right text-sm text-ink disabled:border-transparent disabled:bg-transparent"
        />
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-right text-ink">
        € {Number(valid ? quantity * unitPrice : voce.totale || 0).toFixed(2)}
      </td>
      <td className="min-w-[130px] px-3 py-2 text-center text-xs">
        {voce.origine_voce_id ? (
          <span className="inline-flex items-center gap-1 text-success">
            <Check className="h-3.5 w-3.5" /> Prezzo GB
          </span>
        ) : voce.generata_da_ai ? (
          voce.validata_umano ? (
            <span className="inline-flex items-center gap-1 text-success">
              <Check className="h-3.5 w-3.5" /> Validata
            </span>
          ) : (
            <button
              type="button"
              disabled={locked || validating}
              onClick={onValidate}
              className="rounded-full border border-brand/40 px-2 py-1 text-brand disabled:opacity-40"
            >
              {validating ? "Validazione…" : "Valida voce"}
            </button>
          )
        ) : (
          <span className="text-fog">Manuale</span>
        )}
      </td>
      <td className="min-w-[190px] px-3 py-2">
        <div className="flex items-center justify-end gap-1.5">
          <IconButton
            label={`Sposta su ${voce.descrizione}`}
            disabled={locked || reordering || index === 0}
            onClick={() => onMove(-1)}
          >
            <ArrowUp className="h-4 w-4" />
          </IconButton>
          <IconButton
            label={`Sposta giù ${voce.descrizione}`}
            disabled={locked || reordering || index === total - 1}
            onClick={() => onMove(1)}
          >
            <ArrowDown className="h-4 w-4" />
          </IconButton>
          <IconButton
            label={`Salva ${voce.descrizione}`}
            disabled={locked || saving || !changed || !valid}
            onClick={() =>
              onSave({
                descrizione: description,
                qta: quantity,
                prezzo_unitario: unitPrice,
              })
            }
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
          </IconButton>
          <IconButton
            label={`Elimina ${voce.descrizione}`}
            danger
            disabled={locked || removing}
            onClick={onRemove}
          >
            {removing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </IconButton>
        </div>
      </td>
    </tr>
  );
}

export default function ComputoEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
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

  const activePrezz =
    prezzarioId ||
    prezzari.find((prezzario) => prezzario.is_default)?.id ||
    prezzari[0]?.id;

  const { data: vociPrezz = [] } = useQuery({
    queryKey: ["prezzario-voci-editor", activePrezz],
    enabled: Boolean(activePrezz),
    queryFn: async () =>
      (await client.get(`/prezzario/${activePrezz}/voci`)).data,
  });

  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["computo", id] }),
      qc.invalidateQueries({ queryKey: ["confronto-variante", id] }),
      qc.invalidateQueries({ queryKey: ["computi"] }),
      qc.invalidateQueries({ queryKey: ["preventivi"] }),
    ]);

  const add = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/computi/${id}/voci`, {
          prezzario_voce_id: voceId,
          qta: Number(qta),
        })
      ).data,
    onSuccess: async () => {
      toast.success(
        computo?.preventivo_bozza_id
          ? "Voce aggiunta e bozza preventivo aggiornata"
          : "Voce aggiunta",
      );
      setVoceId("");
      await refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore aggiunta voce"),
  });

  const update = useMutation({
    mutationFn: async ({ id: currentVoceId, patch }) =>
      (await client.patch(`/computi/voci/${currentVoceId}`, patch)).data,
    onSuccess: async () => {
      toast.success(
        computo?.preventivo_bozza_id
          ? "Voce aggiornata e bozza preventivo sincronizzata"
          : "Voce aggiornata",
      );
      await refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore aggiornamento voce"),
  });

  const remove = useMutation({
    mutationFn: async (currentVoceId) =>
      (await client.delete(`/computi/voci/${currentVoceId}`)).data,
    onSuccess: async () => {
      toast.success(
        computo?.preventivo_bozza_id
          ? "Voce eliminata e bozza preventivo aggiornata"
          : "Voce eliminata",
      );
      await refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore eliminazione voce"),
  });

  const reorder = useMutation({
    mutationFn: async (ordine) =>
      (await client.post(`/computi/${id}/riordina`, { ordine })).data,
    onSuccess: refresh,
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore riordino voci"),
  });

  const confirm = useMutation({
    mutationFn: async () => (await client.post(`/computi/${id}/conferma`)).data,
    onSuccess: async () => {
      toast.success("Dati confermati: il preventivo è pronto per l’invio");
      await refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Conferma bloccata"),
  });

  const validate = useMutation({
    mutationFn: async (ids) =>
      (
        await client.post(`/computi/${id}/valida-ai`, {
          voce_ids: ids || undefined,
        })
      ).data,
    onSuccess: async (data) => {
      toast.success(`Validate ${data.validate} voci automatiche`);
      await refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore validazione voci"),
  });

  const duplicate = useMutation({
    mutationFn: async ({ tipo, variante = false }) =>
      variante
        ? (await client.post(`/computi/${id}/varianti`)).data
        : (
            await client.post(`/computi/${id}/duplica`, null, {
              params: { tipo },
            })
          ).data,
    onSuccess: (copy) => {
      toast.success(
        copy.tipo === "variante" ? "Variante creata" : "Computo duplicato",
      );
      qc.invalidateQueries({ queryKey: ["computi"] });
      navigate(`/dashboard/computi/${copy.id}`);
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Errore duplicazione computo",
      ),
  });

  const toPreventivo = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/computi/${id}/preventivo`, {
          sconto: 0,
          iva: 10,
        })
      ).data,
    onSuccess: async (preventivo) => {
      await refresh();
      toast.success(`Preventivo ${preventivo.numero} pronto`);
      navigate("/dashboard/preventivi");
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Errore preventivo"),
  });

  const previewPdf = useMutation({
    mutationFn: async () =>
      (
        await client.get(`/preventivi/${computo.preventivo_bozza_id}/pdf`, {
          responseType: "blob",
        })
      ).data,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${computo.preventivo_bozza_numero || "preventivo-bozza"}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Anteprima PDF non disponibile",
      ),
  });

  if (isLoading || !computo) {
    return (
      <div className="p-6 text-sm font-display uppercase tracking-widest text-fog">
        Caricamento…
      </div>
    );
  }

  const totali = computo.totali || {};
  const voci = computo.voci || [];
  const daValidare = Number(totali.n_da_validare || 0);
  const locked = LOCKED_STATES.has(computo.stato);

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/dashboard/computi"
            className="text-xs text-fog hover:text-brand"
          >
            ← Computi
          </Link>
          <h1 className="mt-1 text-2xl font-display uppercase text-ink">
            Editor computo
          </h1>
          <p className="text-sm text-fog">
            Stato <span className="text-ink">{computo.stato}</span> · Totale{" "}
            <span className="text-brand">
              €{" "}
              {Number(totali.totale || 0).toLocaleString("it-IT", {
                minimumFractionDigits: 2,
              })}
            </span>
            {daValidare > 0 && (
              <span className="ml-2 text-brand">
                · {daValidare} voci automatiche da validare
              </span>
            )}
          </p>
          <p className="mt-1 text-xs text-fog">
            Cliente:{" "}
            <span className="text-ink">
              {computo.cliente || "Non associato"}
            </span>
            {computo.prezzario_nome && (
              <>
                {" "}
                - Listino:{" "}
                <span className="text-ink">{computo.prezzario_nome}</span>
              </>
            )}
          </p>
          {computo.note && (
            <p className="mt-2 border-l-2 border-brand/70 pl-3 text-xs leading-5 text-fog">
              {computo.note}
            </p>
          )}
          {locked && (
            <p className="mt-2 text-xs text-fog">
              Il computo è bloccato. Crea una variante per modificarne le voci.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {!locked && daValidare > 0 && (
            <button
              type="button"
              onClick={() => validate.mutate(null)}
              disabled={validate.isPending}
              className="rounded-xl border border-stroke px-3 py-2 text-xs font-display uppercase text-ink disabled:opacity-40"
            >
              Valida tutte
            </button>
          )}
          {computo.tipo !== "variante" && (
            <button
              type="button"
              onClick={() => duplicate.mutate({ tipo: computo.tipo })}
              disabled={duplicate.isPending}
              className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 text-xs font-display uppercase text-ink disabled:opacity-40"
            >
              <Copy className="h-4 w-4" /> Duplica
            </button>
          )}
          {locked && computo.tipo !== "variante" && (
            <button
              type="button"
              onClick={() => duplicate.mutate({ variante: true })}
              disabled={duplicate.isPending}
              className="rounded-xl border border-brand/40 px-3 py-2 text-xs font-display uppercase text-brand disabled:opacity-40"
            >
              Crea variante
            </button>
          )}
          {!locked && (
            <button
              type="button"
              onClick={() => confirm.mutate()}
              disabled={confirm.isPending || voci.length === 0}
              className="rounded-xl bg-brand px-3 py-2 text-xs font-display uppercase text-white disabled:opacity-40"
            >
              Conferma dati finali
            </button>
          )}
          {!locked && computo.preventivo_bozza_id && (
            <button
              type="button"
              onClick={() => previewPdf.mutate()}
              disabled={previewPdf.isPending}
              className="inline-flex items-center gap-2 rounded-xl border border-brand/40 px-3 py-2 text-xs font-display uppercase text-brand disabled:opacity-40"
            >
              {previewPdf.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="h-4 w-4" />
              )}
              Anteprima bozza
            </button>
          )}
          <button
            type="button"
            onClick={() =>
              computo.preventivo_bozza_id
                ? navigate("/dashboard/preventivi")
                : toPreventivo.mutate()
            }
            disabled={computo.stato !== "confermato" || toPreventivo.isPending}
            title={
              computo.stato !== "confermato"
                ? "Conferma prima i dati finali"
                : computo.preventivo_bozza_id
                  ? "Apri il preventivo confermato"
                  : "Crea preventivo"
            }
            className="rounded-xl border border-brand/40 px-3 py-2 text-xs font-display uppercase text-brand disabled:cursor-not-allowed disabled:opacity-40"
          >
            {computo.preventivo_bozza_id
              ? "Apri preventivo"
              : "Genera preventivo"}
          </button>
        </div>
      </div>

      {!locked && computo.preventivo_bozza_id && (
        <div className="border-l-4 border-brand bg-brand/5 px-5 py-4">
          <p className="text-sm font-semibold text-ink">
            Bozza {computo.preventivo_bozza_numero} generata e modificabile
          </p>
          <p className="mt-1 text-xs leading-5 text-fog">
            Puoi modificare descrizione, quantità, prezzo, ordine, aggiungere o
            eliminare singole voci. Totali e PDF vengono sincronizzati sulla
            stessa bozza. Conferma i dati soltanto quando il controllo è
            concluso.
          </p>
        </div>
      )}

      {computo.tipo === "variante" && <VarianteComparison computoId={id} />}

      {!locked && (
        <div className="grid items-end gap-2 rounded-2xl border border-stroke bg-surface p-4 md:grid-cols-12">
          <div className="md:col-span-3">
            <label className="text-[10px] font-display uppercase tracking-wider text-fog">
              Prezzario
            </label>
            <select
              className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
              value={activePrezz || ""}
              onChange={(event) => setPrezzarioId(event.target.value)}
            >
              {prezzari.map((prezzario) => (
                <option key={prezzario.id} value={prezzario.id}>
                  {prezzario.nome}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-6">
            <label className="text-[10px] font-display uppercase tracking-wider text-fog">
              Voce
            </label>
            <select
              className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
              value={voceId}
              onChange={(event) => setVoceId(event.target.value)}
            >
              <option value="">Seleziona…</option>
              {vociPrezz.map((voce) => (
                <option key={voce.id} value={voce.id}>
                  {voce.codice} — {voce.descrizione} (€{" "}
                  {Number(voce.prezzo_unitario).toFixed(2)})
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-1">
            <label className="text-[10px] font-display uppercase tracking-wider text-fog">
              Q.tà
            </label>
            <input
              type="number"
              min="0"
              step="0.001"
              value={qta}
              onChange={(event) => setQta(event.target.value)}
              className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
            />
          </div>
          <div className="md:col-span-2">
            <button
              type="button"
              disabled={!voceId || add.isPending}
              onClick={() => add.mutate()}
              className="w-full rounded-xl border border-stroke bg-surface-2 px-3 py-2 text-xs font-display uppercase text-ink disabled:opacity-40"
            >
              {add.isPending ? "Aggiunta…" : "Aggiungi"}
            </button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-2xl border border-stroke">
        <table className="min-w-[1080px] text-sm">
          <thead className="bg-surface-2 text-[10px] font-display uppercase tracking-wider text-fog">
            <tr>
              <th className="px-3 py-2 text-left">Descrizione</th>
              <th className="px-3 py-2 text-left">UM</th>
              <th className="px-3 py-2 text-right">Q.tà</th>
              <th className="px-3 py-2 text-right">Prezzo</th>
              <th className="px-3 py-2 text-right">Totale</th>
              <th className="px-3 py-2 text-center">Origine</th>
              <th className="px-3 py-2 text-right">Azioni</th>
            </tr>
          </thead>
          <tbody>
            {voci.map((voce, index) => (
              <VoceRow
                key={voce.id}
                voce={voce}
                index={index}
                total={voci.length}
                locked={locked}
                saving={update.isPending && update.variables?.id === voce.id}
                removing={remove.isPending && remove.variables === voce.id}
                validating={
                  validate.isPending && validate.variables?.includes(voce.id)
                }
                reordering={reorder.isPending}
                onSave={(patch) => update.mutate({ id: voce.id, patch })}
                onRemove={() => {
                  if (
                    window.confirm(
                      `Eliminare la voce “${voce.descrizione}” dal computo?`,
                    )
                  ) {
                    remove.mutate(voce.id);
                  }
                }}
                onValidate={() => validate.mutate([voce.id])}
                onMove={(delta) =>
                  reorder.mutate(moveVoceIds(voci, index, delta))
                }
              />
            ))}
            {voci.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-sm text-fog"
                >
                  Nessuna voce nel computo.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
