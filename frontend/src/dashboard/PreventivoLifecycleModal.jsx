import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock3,
  FileText,
  History,
  Loader2,
  Mail,
  X,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";
import { refreshLeadViews } from "@/lib/leadSync";
import {
  azioniPerPreventivo,
  etichettaEventoPreventivo,
  PREVENTIVO_STATI,
} from "@/lib/preventivi";

const inputClass =
  "w-full rounded-xl border border-stroke bg-bg px-3 py-2 text-sm text-ink outline-none placeholder:text-fog focus:border-brand";

const ACTION_ICONS = {
  accettato: CheckCircle2,
  rifiutato: XCircle,
  scaduto: Clock3,
};

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function apiError(error, fallback) {
  return formatApiErrorDetail(error?.response?.data?.detail) || fallback;
}

export default function PreventivoLifecycleModal({ preventivo, onClose }) {
  const open = Boolean(preventivo);
  const queryClient = useQueryClient();
  const closeButtonRef = useRef(null);
  const previousFocusRef = useRef(null);
  const pendingRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const [destinatario, setDestinatario] = useState("");
  const [oggetto, setOggetto] = useState("");
  const [messaggio, setMessaggio] = useState("");
  const [azioneDaConfermare, setAzioneDaConfermare] = useState(null);

  const historyQuery = useQuery({
    queryKey: ["preventivo-eventi", preventivo?.id],
    queryFn: async () =>
      (await client.get(`/preventivi/${preventivo.id}/eventi`)).data,
    enabled: open && preventivo?.source === "edilos",
  });

  useEffect(() => {
    if (!open) return;
    setDestinatario(preventivo?.ultimo_destinatario || preventivo?.email || "");
    setOggetto("");
    setMessaggio("");
    setAzioneDaConfermare(null);
  }, [open, preventivo]);

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["preventivi"] }),
      queryClient.invalidateQueries({
        queryKey: ["preventivo-eventi", preventivo?.id],
      }),
      refreshLeadViews(queryClient),
    ]);
  };

  const sendMutation = useMutation({
    mutationFn: async () => {
      const payload = { destinatario: destinatario.trim() };
      if (oggetto.trim()) payload.oggetto = oggetto.trim();
      if (messaggio.trim()) payload.messaggio = messaggio.trim();
      return (await client.post(`/preventivi/${preventivo.id}/invia`, payload))
        .data;
    },
    onSuccess: async () => {
      await refresh();
      toast.success("Preventivo inviato con PDF allegato");
      onClose?.();
    },
    onError: (error) =>
      toast.error(apiError(error, "Invio del preventivo non riuscito.")),
  });

  const stateMutation = useMutation({
    mutationFn: async (stato) =>
      (
        await client.patch(`/preventivi/${preventivo.id}/stato`, {
          stato,
        })
      ).data,
    onSuccess: async (updated) => {
      await refresh();
      setAzioneDaConfermare(null);
      toast.success(
        `Preventivo ${PREVENTIVO_STATI[updated.stato]?.label?.toLowerCase() || "aggiornato"}`,
      );
      onClose?.();
    },
    onError: (error) => {
      setAzioneDaConfermare(null);
      toast.error(apiError(error, "Aggiornamento dello stato non riuscito."));
    },
  });

  const pending = sendMutation.isPending || stateMutation.isPending;
  pendingRef.current = pending;
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => closeButtonRef.current?.focus());
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !pendingRef.current) onCloseRef.current?.();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const stato = preventivo.stato_documento || "bozza";
  const statoMeta = PREVENTIVO_STATI[stato] || PREVENTIVO_STATI.bozza;
  const azioni = azioniPerPreventivo(stato);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={() => !pending && onClose?.()}
        aria-hidden="true"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="preventivo-lifecycle-title"
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-stroke bg-surface shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-stroke px-5 py-4">
          <div>
            <p className="font-display text-[10px] uppercase tracking-wider text-fog">
              Gestione preventivo
            </p>
            <h2
              id="preventivo-lifecycle-title"
              className="font-display text-lg font-bold uppercase text-ink"
            >
              {preventivo.numero || preventivo.cliente}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            aria-label="Chiudi gestione preventivo"
            onClick={() => !pending && onClose?.()}
            disabled={pending}
            className="text-fog hover:text-ink disabled:opacity-40"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="space-y-5 overflow-y-auto p-5">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stroke bg-bg/50 p-4">
            <div>
              <p className="font-body text-sm font-medium text-ink">
                {preventivo.cliente}
              </p>
              <p className="font-body text-xs text-fog">
                Totale documento: {formatEuro(preventivo.totale_documento)}
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 font-display text-[10px] uppercase ${statoMeta.tone}`}
            >
              {statoMeta.label}
            </span>
          </div>

          {stato === "bozza" && (
            <div className="space-y-4 rounded-xl border border-brand/30 bg-brand/5 p-4">
              <div className="flex items-start gap-3">
                <Mail className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
                <div>
                  <h3 className="font-display text-sm font-bold uppercase text-ink">
                    Invia il PDF al cliente
                  </h3>
                  <p className="font-body text-xs text-fog">
                    L’email parte dall’indirizzo ufficiale
                    info@gbconstruction.it e registra automaticamente invio,
                    destinatario e stato.
                  </p>
                </div>
              </div>
              <label className="block">
                <span className="mb-1 block font-display text-[10px] uppercase text-fog">
                  Destinatario
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  value={destinatario}
                  onChange={(event) => setDestinatario(event.target.value)}
                  className={inputClass}
                  placeholder="cliente@email.it"
                />
              </label>
              <label className="block">
                <span className="mb-1 block font-display text-[10px] uppercase text-fog">
                  Oggetto personalizzato (facoltativo)
                </span>
                <input
                  value={oggetto}
                  onChange={(event) => setOggetto(event.target.value)}
                  className={inputClass}
                  placeholder={`Preventivo ${preventivo.numero || ""} - GB Construction`}
                />
              </label>
              <label className="block">
                <span className="mb-1 block font-display text-[10px] uppercase text-fog">
                  Messaggio personalizzato (facoltativo)
                </span>
                <textarea
                  rows={5}
                  value={messaggio}
                  onChange={(event) => setMessaggio(event.target.value)}
                  className={`${inputClass} resize-y`}
                  placeholder="Lascia vuoto per usare il messaggio professionale predefinito."
                />
              </label>
              <button
                type="button"
                onClick={() => sendMutation.mutate()}
                disabled={pending || !destinatario.trim()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-xs uppercase text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sendMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="h-4 w-4" />
                )}
                {sendMutation.isPending
                  ? "Invio in corso…"
                  : "Invia preventivo PDF"}
              </button>
            </div>
          )}

          {azioni.length > 0 && (
            <div className="space-y-3 rounded-xl border border-stroke p-4">
              <div>
                <h3 className="font-display text-sm font-bold uppercase text-ink">
                  Esito del preventivo
                </h3>
                <p className="font-body text-xs text-fog">
                  Registra l’esito comunicato dal cliente. L’operazione aggiorna
                  anche lo stato del lead associato.
                </p>
              </div>
              {azioneDaConfermare ? (
                <div className="rounded-xl border border-warning/40 bg-warning/10 p-3">
                  <p className="font-body text-sm text-ink">
                    Confermi lo stato “
                    {PREVENTIVO_STATI[azioneDaConfermare]?.label}”? Non potrà
                    essere modificato dalla dashboard.
                  </p>
                  <div className="mt-3 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setAzioneDaConfermare(null)}
                      disabled={pending}
                      className="px-3 py-2 font-display text-xs uppercase text-fog hover:text-ink"
                    >
                      Annulla
                    </button>
                    <button
                      type="button"
                      onClick={() => stateMutation.mutate(azioneDaConfermare)}
                      disabled={pending}
                      className="inline-flex items-center gap-2 rounded-xl bg-brand px-3 py-2 font-display text-xs uppercase text-white disabled:opacity-50"
                    >
                      {stateMutation.isPending && (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      )}
                      Conferma
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid gap-2 sm:grid-cols-3">
                  {azioni.map((azione) => {
                    const Icon = ACTION_ICONS[azione.stato] || FileText;
                    return (
                      <button
                        key={azione.stato}
                        type="button"
                        onClick={() => setAzioneDaConfermare(azione.stato)}
                        disabled={pending}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-stroke bg-bg px-3 py-2 font-display text-[10px] uppercase text-ink hover:border-brand disabled:opacity-50"
                      >
                        <Icon className="h-4 w-4" /> {azione.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-brand" />
              <h3 className="font-display text-sm font-bold uppercase text-ink">
                Storico
              </h3>
            </div>
            {historyQuery.isLoading ? (
              <div className="flex items-center gap-2 text-xs text-fog">
                <Loader2 className="h-4 w-4 animate-spin" /> Caricamento
                storico…
              </div>
            ) : historyQuery.isError ? (
              <p className="font-body text-xs text-red-300">
                Storico momentaneamente non disponibile.
              </p>
            ) : historyQuery.data?.length ? (
              <ol className="space-y-2">
                {historyQuery.data.map((evento) => (
                  <li
                    key={evento.id}
                    className="rounded-xl border border-stroke bg-bg/40 p-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-display text-[10px] uppercase text-ink">
                        {etichettaEventoPreventivo(evento)}
                      </span>
                      <time className="font-body text-[10px] text-fog">
                        {formatDate(evento.created_at)}
                      </time>
                    </div>
                    <p className="mt-1 font-body text-xs text-fog">
                      {evento.dettaglio}
                    </p>
                    {(evento.destinatario || evento.autore) && (
                      <p className="mt-1 font-body text-[10px] text-fog/80">
                        {evento.destinatario
                          ? `Destinatario: ${evento.destinatario}`
                          : `Operatore: ${evento.autore}`}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="font-body text-xs text-fog">
                Nessun evento registrato.
              </p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
