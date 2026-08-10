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
import { moveVoceIds, raggruppaVociPerFase } from "@/lib/computo";
import { fetchComputo, prefetchComputi } from "@/lib/computiPrefetch";
import { toast } from "sonner";
import VarianteComparison from "@/dashboard/components/VarianteComparison";

const LOCKED_STATES = new Set(["confermato", "archiviato"]);

const euro = (value) =>
  `€ ${Number(value || 0).toLocaleString("it-IT", { minimumFractionDigits: 2 })}`;

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
  numero,
  total,
  locked,
  fasi,
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
  const [area, setArea] = useState(voce.area || "");

  useEffect(() => {
    setDraft({
      descrizione: voce.descrizione,
      qta: String(voce.qta),
      prezzo_unitario: String(voce.prezzo_unitario),
    });
  }, [voce.descrizione, voce.prezzo_unitario, voce.qta]);

  useEffect(() => setArea(voce.area || ""), [voce.area]);

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
      <td className="w-14 px-3 py-2 align-top text-xs text-fog">{numero}</td>
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
      <td className="min-w-[210px] px-3 py-2">
        <select
          aria-label={`Fase voce ${index + 1}`}
          value={voce.fase || ""}
          disabled={locked}
          onChange={(event) => onSave({ fase: event.target.value })}
          className="w-full rounded-lg border border-stroke bg-surface-2 px-2 py-1.5 text-xs text-ink disabled:border-transparent disabled:bg-transparent"
        >
          {!voce.fase && <option value="">Da classificare</option>}
          {fasi.map((nome) => (
            <option key={nome} value={nome}>
              {nome}
            </option>
          ))}
        </select>
        <input
          aria-label={`Area voce ${index + 1}`}
          value={area}
          maxLength={120}
          disabled={locked}
          placeholder="Area / ambiente…"
          onChange={(event) => setArea(event.target.value)}
          onBlur={() => {
            if ((voce.area || "") !== area) onSave({ area });
          }}
          className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-1 text-xs text-fog disabled:border-transparent disabled:bg-transparent"
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
  const [prezzarioQuery, setPrezzarioQuery] = useState("");
  const [modalitaVoce, setModalitaVoce] = useState("prezzario");
  const [voceLibera, setVoceLibera] = useState({
    descrizione: "",
    um: "cad",
    qta: 1,
    prezzo_unitario: "",
  });
  const [cronoprogrammaDraft, setCronoprogrammaDraft] = useState({
    superficie_mq: "",
    durate_fasi: {},
  });

  const { data: computo, isLoading } = useQuery({
    queryKey: ["computo", id],
    queryFn: fetchComputo,
  });

  useEffect(() => {
    if (!computo) return;
    setCronoprogrammaDraft({
      superficie_mq:
        computo.superficie_mq === null || computo.superficie_mq === undefined
          ? ""
          : String(computo.superficie_mq),
      durate_fasi: Object.fromEntries(
        Object.entries(computo.durate_fasi || {}).map(([ordine, giorni]) => [
          String(ordine),
          String(giorni),
        ]),
      ),
    });
  }, [computo]);

  const { data: prezzari = [] } = useQuery({
    queryKey: ["prezzari"],
    queryFn: async () => (await client.get("/prezzario")).data,
  });

  const activePrezz =
    prezzarioId ||
    prezzari.find((prezzario) => prezzario.is_default)?.id ||
    prezzari[0]?.id;

  const { data: vociPrezzData = { items: [] } } = useQuery({
    queryKey: ["prezzario-voci-editor", activePrezz, prezzarioQuery],
    enabled: Boolean(activePrezz),
    queryFn: async () =>
      (
        await client.get(`/prezzario/${activePrezz}/voci`, {
          params: { q: prezzarioQuery || undefined, page_size: 50 },
        })
      ).data,
  });
  const vociPrezz = vociPrezzData.items || [];

  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["computo", id] }),
      qc.invalidateQueries({ queryKey: ["confronto-variante", id] }),
      qc.invalidateQueries({ queryKey: ["computi"] }),
      qc.invalidateQueries({ queryKey: ["preventivi"] }),
    ]);

  const add = useMutation({
    mutationFn: async () => {
      if (modalitaVoce === "libera") {
        return (
          await client.post(`/computi/${id}/voci-libere`, {
            descrizione: voceLibera.descrizione.trim(),
            um: voceLibera.um.trim(),
            qta: Number(voceLibera.qta),
            prezzo_unitario: Number(voceLibera.prezzo_unitario),
          })
        ).data;
      }
      return (
        await client.post(`/computi/${id}/voci`, {
          prezzario_voce_id: voceId,
          qta: Number(qta),
        })
      ).data;
    },
    onSuccess: async () => {
      toast.success(
        computo?.preventivo_bozza_id
          ? "Voce aggiunta e bozza preventivo aggiornata"
          : "Voce aggiunta",
      );
      setVoceId("");
      setVoceLibera({
        descrizione: "",
        um: "cad",
        qta: 1,
        prezzo_unitario: "",
      });
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

  const salvaCronoprogramma = useMutation({
    mutationFn: async () => {
      const superficie = Number(cronoprogrammaDraft.superficie_mq);
      const durate = Object.fromEntries(
        Object.entries(cronoprogrammaDraft.durate_fasi)
          .filter(([, giorni]) => String(giorni).trim() !== "")
          .map(([ordine, giorni]) => [ordine, Number(giorni)]),
      );
      return (
        await client.put(`/computi/${id}/cronoprogramma`, {
          superficie_mq:
            cronoprogrammaDraft.superficie_mq === "" ? null : superficie,
          durate_fasi: durate,
        })
      ).data;
    },
    onSuccess: async () => {
      toast.success(
        computo?.preventivo_bozza_id
          ? "Cronoprogramma salvato e PDF della bozza aggiornato"
          : "Cronoprogramma salvato",
      );
      await refresh();
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Cronoprogramma non salvato",
      ),
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

  const riclassifica = useMutation({
    mutationFn: async (forza) =>
      (
        await client.post(`/computi/${id}/riclassifica`, null, {
          params: { forza: Boolean(forza) },
        })
      ).data,
    onSuccess: async (data) => {
      toast.success(
        data.riclassificate
          ? `Assegnata la fase a ${data.riclassificate} voci`
          : "Tutte le voci hanno già una fase",
      );
      await refresh();
    },
    onError: (error) =>
      toast.error(
        error?.response?.data?.detail || "Errore classificazione in fasi",
      ),
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
    mutationFn: async (dettaglio = "analitico") =>
      (
        await client.get(`/preventivi/${computo.preventivo_bozza_id}/pdf`, {
          params: { dettaglio },
          responseType: "blob",
        })
      ).data,
    onSuccess: (blob, dettaglio) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${computo.preventivo_bozza_numero || "preventivo-bozza"}-${dettaglio || "analitico"}.pdf`;
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
  const gruppi = raggruppaVociPerFase(voci);
  const fasiDisponibili = computo.fasi_disponibili || [];
  const controlli = computo.controlli || [];
  const senzaFase = Number(computo.n_senza_fase || 0);
  const crono = computo.cronoprogramma || {};
  const superficieNumero = Number(cronoprogrammaDraft.superficie_mq);
  const superficieValida =
    cronoprogrammaDraft.superficie_mq !== "" &&
    Number.isFinite(superficieNumero) &&
    superficieNumero >= 5 &&
    superficieNumero <= 10000;
  const durateValide = Object.values(
    cronoprogrammaDraft.durate_fasi,
  ).every((giorni) => {
    if (String(giorni).trim() === "") return true;
    const value = Number(giorni);
    return Number.isInteger(value) && value >= 0 && value <= 730;
  });
  const fasiCronoprogramma = (crono.blocchi || []).filter(
    (blocco) => !blocco.continuativa && Number(blocco.fase_ordine) !== 99,
  );

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/dashboard/computi"
            onPointerEnter={() => void prefetchComputi(qc)}
            onFocus={() => void prefetchComputi(qc)}
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
            {crono.giorni_totali > 0 && (
              <span className="ml-2 text-fog">
                · Durata stimata {crono.giorni_totali} gg lavorativi (≈{" "}
                {crono.settimane} settimane)
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
          {!locked && senzaFase > 0 && (
            <button
              type="button"
              onClick={() => riclassifica.mutate(false)}
              disabled={riclassifica.isPending}
              className="rounded-xl border border-brand/40 px-3 py-2 text-xs font-display uppercase text-brand disabled:opacity-40"
            >
              {riclassifica.isPending
                ? "Classificazione…"
                : `Classifica ${senzaFase} voci`}
            </button>
          )}
          {!locked && computo.preventivo_bozza_id && (
            <>
              <button
                type="button"
                onClick={() => previewPdf.mutate("analitico")}
                disabled={previewPdf.isPending}
                className="inline-flex items-center gap-2 rounded-xl border border-brand/40 px-3 py-2 text-xs font-display uppercase text-brand disabled:opacity-40"
              >
                {previewPdf.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileDown className="h-4 w-4" />
                )}
                Anteprima analitica
              </button>
              <button
                type="button"
                onClick={() => previewPdf.mutate("sintetico")}
                disabled={previewPdf.isPending}
                className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 text-xs font-display uppercase text-ink disabled:opacity-40"
                title="Versione per il cliente: fasi e importi, senza quantità e prezzi unitari"
              >
                <FileDown className="h-4 w-4" /> Anteprima sintetica
              </button>
            </>
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

      <section className="rounded-2xl border border-stroke bg-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-display uppercase tracking-wider text-brand">
              Cronoprogramma lavori
            </p>
            <h2 className="mt-1 text-lg font-display uppercase text-ink">
              Superficie e durata delle fasi
            </h2>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-fog">
              Conferma i metri quadri effettivi. Lascia vuota una durata per
              usare il calcolo automatico oppure inserisci manualmente i giorni
              lavorativi della singola fase.
            </p>
          </div>
          <div className="text-right text-xs text-fog">
            <span className="block text-lg font-display text-ink">
              {crono.giorni_totali || 0} giorni
            </span>
            {crono.mesi > 0 && <span>circa {crono.mesi} mesi</span>}
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-[220px_1fr]">
          <label className="block">
            <span className="text-[10px] font-display uppercase tracking-wider text-fog">
              Superficie effettiva m²
            </span>
            <input
              aria-label="Superficie effettiva del cantiere"
              type="number"
              min="5"
              max="10000"
              step="0.01"
              value={cronoprogrammaDraft.superficie_mq}
              onChange={(event) =>
                setCronoprogrammaDraft((current) => ({
                  ...current,
                  superficie_mq: event.target.value,
                }))
              }
              placeholder={
                crono.superficie_stimata_mq
                  ? String(crono.superficie_stimata_mq)
                  : "es. 92"
              }
              className="mt-1 w-full rounded-xl border border-stroke bg-surface-2 px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
            />
          </label>
          <div className="rounded-xl border border-stroke/70 bg-surface-2 px-4 py-3 text-xs leading-5 text-fog">
            {crono.superficie_richiede_conferma ? (
              <>
                Il sistema propone <strong className="text-ink">{crono.superficie_stimata_mq} m²</strong>{" "}
                dalle quantità del computo. Confermali prima di generare il
                preventivo.
                <button
                  type="button"
                  onClick={() =>
                    setCronoprogrammaDraft((current) => ({
                      ...current,
                      superficie_mq: String(crono.superficie_stimata_mq || ""),
                    }))
                  }
                  className="ml-2 text-brand underline underline-offset-2"
                >
                  Usa questa superficie
                </button>
              </>
            ) : (
              <>
                Superficie confermata: il calcolo automatico non sommerà più
                posa, fornitura, sfridi e rivestimenti.
              </>
            )}
          </div>
        </div>

        {senzaFase > 0 && (
          <p className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-300">
            Restano {senzaFase} voci da classificare. Il preventivo non potrà
            essere generato finché non assegni una fase corretta.
          </p>
        )}

        <div className="mt-5 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {fasiCronoprogramma.map((blocco) => {
            const ordine = String(blocco.fase_ordine);
            const valore = cronoprogrammaDraft.durate_fasi[ordine] ?? "";
            return (
              <label
                key={`${ordine}-${blocco.fase}`}
                className="grid grid-cols-[1fr_92px] items-center gap-3 rounded-xl border border-stroke/70 bg-surface-2 px-3 py-2.5"
              >
                <span>
                  <span className="block text-xs text-ink">{blocco.fase}</span>
                  <span className="mt-0.5 block text-[10px] text-fog">
                    Automatico: {blocco.giorni_automatici ?? blocco.giorni} gg
                    {blocco.parallela ? " · in parallelo" : ""}
                  </span>
                </span>
                <input
                  aria-label={`Durata manuale ${blocco.fase}`}
                  type="number"
                  min="0"
                  max="730"
                  step="1"
                  value={valore}
                  placeholder={`${blocco.giorni} gg`}
                  onChange={(event) =>
                    setCronoprogrammaDraft((current) => ({
                      ...current,
                      durate_fasi: {
                        ...current.durate_fasi,
                        [ordine]: event.target.value,
                      },
                    }))
                  }
                  className="w-full rounded-lg border border-stroke bg-bg px-2 py-1.5 text-right text-sm text-ink focus:border-brand focus:outline-none"
                />
              </label>
            );
          })}
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={() =>
              setCronoprogrammaDraft((current) => ({
                ...current,
                durate_fasi: {},
              }))
            }
            className="rounded-xl border border-stroke px-4 py-2 text-xs font-display uppercase text-fog"
          >
            Ripristina durate automatiche
          </button>
          <button
            type="button"
            disabled={
              !superficieValida ||
              !durateValide ||
              salvaCronoprogramma.isPending
            }
            onClick={() => salvaCronoprogramma.mutate()}
            className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-xs font-display uppercase text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {salvaCronoprogramma.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Salva cronoprogramma
          </button>
        </div>
      </section>

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

      {controlli.length > 0 && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-5 py-4">
          <p className="text-xs font-display uppercase tracking-wider text-amber-400">
            Controlli di coerenza · {controlli.length}
          </p>
          <ul className="mt-2 space-y-1.5">
            {controlli.map((controllo) => (
              <li key={controllo.codice} className="text-xs leading-5 text-fog">
                <span className="text-ink">{controllo.messaggio}</span>{" "}
                <span className="text-fog/70">
                  (attesa: {controllo.fasi_attese.join(" o ")})
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-fog/70">
            Avvisi non bloccanti: servono a non dimenticare lavorazioni
            collegate.
          </p>
        </div>
      )}

      {computo.tipo === "variante" && <VarianteComparison computoId={id} />}

      {!locked && (
        <div className="rounded-2xl border border-stroke bg-surface p-4">
          <div className="mb-4 flex flex-wrap gap-2">
            {[
              ["prezzario", "Dal prezzario"],
              ["libera", "Voce libera"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setModalitaVoce(value)}
                className={`rounded-lg px-3 py-2 text-xs font-display uppercase ${modalitaVoce === value ? "bg-brand text-white" : "border border-stroke bg-surface-2 text-ink"}`}
              >
                {label}
              </button>
            ))}
          </div>

          {modalitaVoce === "prezzario" ? (
            <div className="grid items-end gap-2 md:grid-cols-12">
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
                <input
                  type="search"
                  value={prezzarioQuery}
                  onChange={(event) => {
                    setPrezzarioQuery(event.target.value);
                    setVoceId("");
                  }}
                  placeholder="Cerca codice o descrizione…"
                  className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
                />
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
          ) : (
            <div className="grid items-end gap-2 md:grid-cols-12">
              <div className="md:col-span-5">
                <label className="text-[10px] font-display uppercase tracking-wider text-fog">
                  Descrizione nuova voce
                </label>
                <input
                  type="text"
                  maxLength={500}
                  value={voceLibera.descrizione}
                  onChange={(event) =>
                    setVoceLibera((current) => ({
                      ...current,
                      descrizione: event.target.value,
                    }))
                  }
                  placeholder="Scrivi la lavorazione o il materiale…"
                  className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-[10px] font-display uppercase tracking-wider text-fog">
                  UM
                </label>
                <input
                  type="text"
                  maxLength={50}
                  value={voceLibera.um}
                  onChange={(event) =>
                    setVoceLibera((current) => ({
                      ...current,
                      um: event.target.value,
                    }))
                  }
                  placeholder="mq, mc, cad…"
                  className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
                />
              </div>
              <div className="md:col-span-1">
                <label className="text-[10px] font-display uppercase tracking-wider text-fog">
                  Q.tà
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.001"
                  value={voceLibera.qta}
                  onChange={(event) =>
                    setVoceLibera((current) => ({
                      ...current,
                      qta: event.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-[10px] font-display uppercase tracking-wider text-fog">
                  Prezzo unitario €
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={voceLibera.prezzo_unitario}
                  onChange={(event) =>
                    setVoceLibera((current) => ({
                      ...current,
                      prezzo_unitario: event.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-stroke bg-surface-2 px-2 py-2 text-sm text-ink"
                />
              </div>
              <div className="md:col-span-2">
                <button
                  type="button"
                  disabled={
                    !voceLibera.descrizione.trim() ||
                    !voceLibera.um.trim() ||
                    voceLibera.qta === "" ||
                    voceLibera.prezzo_unitario === "" ||
                    add.isPending
                  }
                  onClick={() => add.mutate()}
                  className="w-full rounded-xl border border-stroke bg-surface-2 px-3 py-2 text-xs font-display uppercase text-ink disabled:opacity-40"
                >
                  {add.isPending ? "Aggiunta…" : "Aggiungi voce libera"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-2xl border border-stroke">
        <table className="min-w-[1320px] text-sm">
          <thead className="bg-surface-2 text-[10px] font-display uppercase tracking-wider text-fog">
            <tr>
              <th className="px-3 py-2 text-left">N.</th>
              <th className="px-3 py-2 text-left">Descrizione</th>
              <th className="px-3 py-2 text-left">Fase / Area</th>
              <th className="px-3 py-2 text-left">UM</th>
              <th className="px-3 py-2 text-right">Q.tà</th>
              <th className="px-3 py-2 text-right">Prezzo</th>
              <th className="px-3 py-2 text-right">Totale</th>
              <th className="px-3 py-2 text-center">Origine</th>
              <th className="px-3 py-2 text-right">Azioni</th>
            </tr>
          </thead>
          {gruppi.map((gruppo, gruppoIndex) => (
            <tbody key={gruppo.fase}>
              <tr className="bg-surface-2/70">
                <td
                  colSpan={9}
                  className="border-t border-stroke px-3 py-2 text-xs font-display uppercase tracking-wider text-ink"
                >
                  <span className="text-brand">
                    {String(gruppoIndex + 1).padStart(2, "0")}
                  </span>{" "}
                  {gruppo.fase}
                  <span className="ml-3 normal-case tracking-normal text-fog">
                    {gruppo.voci.length} lavorazioni · {gruppo.incidenza}% ·{" "}
                    {euro(gruppo.totale)}
                  </span>
                </td>
              </tr>
              {gruppo.voci.map((voce) => (
                <VoceRow
                  key={voce.id}
                  voce={voce}
                  index={voce.__index}
                  numero={`${gruppoIndex + 1}.${voce.__posizione}`}
                  total={voci.length}
                  locked={locked}
                  fasi={fasiDisponibili}
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
                    reorder.mutate(moveVoceIds(voci, voce.__index, delta))
                  }
                />
              ))}
            </tbody>
          ))}
          {voci.length === 0 && (
            <tbody>
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-10 text-center text-sm text-fog"
                >
                  Nessuna voce nel computo.
                </td>
              </tr>
            </tbody>
          )}
        </table>
      </div>
    </div>
  );
}
