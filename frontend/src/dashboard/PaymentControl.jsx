import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BellRing,
  CheckCircle2,
  CircleDollarSign,
  FileSignature,
  Loader2,
  Plus,
} from "lucide-react";
import { toast } from "sonner";
import client from "@/lib/api";

const inputClass =
  "w-full rounded-lg border border-stroke bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function money(value) {
  return Number(value || 0).toLocaleString("it-IT", {
    style: "currency",
    currency: "EUR",
  });
}

function dateLabel(value) {
  return value
    ? new Date(`${value}T12:00:00`).toLocaleDateString("it-IT")
    : "—";
}

function Summary({ data }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {[
        ["Contratto", data.contratto],
        ["Extra approvati", data.extra_approvati],
        ["Totale commessa", data.totale_commessa],
        ["Incassato", data.incassato],
        ["Residuo", data.residuo],
      ].map(([label, value]) => (
        <div
          key={label}
          className="rounded-xl border border-stroke bg-surface p-4"
        >
          <p className="text-[10px] font-display uppercase tracking-wider text-fog">
            {label}
          </p>
          <p className="mt-2 font-display text-lg text-ink">{money(value)}</p>
        </div>
      ))}
    </div>
  );
}

function PlanSetup({ cantiereId, onCreated }) {
  const suggestion = useQuery({
    queryKey: ["payment-plan-suggestion", cantiereId],
    queryFn: async () =>
      (await client.get(`/cantieri/${cantiereId}/piano-pagamenti/suggerimento`))
        .data,
    enabled: Boolean(cantiereId),
    retry: false,
  });
  const [rates, setRates] = useState([]);
  const [email, setEmail] = useState(true);
  const [whatsapp, setWhatsapp] = useState(false);
  const [whatsappConsent, setWhatsappConsent] = useState(false);

  useEffect(() => {
    if (suggestion.data?.rate) setRates(suggestion.data.rate);
    if (suggestion.data?.rates) setRates(suggestion.data.rates);
  }, [suggestion.data]);

  const create = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/cantieri/${cantiereId}/piano-pagamenti`, {
          preventivo_id: suggestion.data.preventivo_id,
          rate: rates,
          email_automatica: email,
          whatsapp_automatico: whatsapp,
          whatsapp_consenso: whatsappConsent,
          giorni_preavviso: [7, 1, 0],
        })
      ).data,
    onSuccess: () => {
      toast.success("Piano pagamenti attivato");
      onCreated();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Piano non attivato"),
  });

  if (suggestion.isLoading)
    return <p className="py-10 text-center text-fog">Verifica contratto…</p>;
  if (suggestion.isError)
    return (
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-6">
        <h3 className="font-display uppercase text-ink">
          Piano non ancora attivabile
        </h3>
        <p className="mt-2 text-sm text-fog">
          {suggestion.error?.response?.data?.detail ||
            "Conferma computo e contratto, quindi torna qui per stabilire date e modalità delle rate."}
        </p>
      </div>
    );

  const total = rates.reduce((sum, item) => sum + Number(item.importo || 0), 0);
  return (
    <section className="space-y-5 rounded-2xl border border-brand/40 bg-surface p-5">
      <div>
        <p className="text-[10px] font-display uppercase tracking-wider text-brand">
          Contratto accettato
        </p>
        <h3 className="mt-1 font-display uppercase text-ink">
          {suggestion.data.contratto_numero} ·{" "}
          {money(suggestion.data.totale_contratto)}
        </h3>
        <p className="mt-1 text-xs text-fog">
          Controlla le date e la modalità di pagamento prima dell’attivazione.
        </p>
      </div>
      <div className="space-y-2">
        {rates.map((rate, index) => (
          <div
            key={rate.numero}
            className="grid gap-2 rounded-xl border border-stroke p-3 md:grid-cols-12"
          >
            <input
              value={rate.titolo}
              onChange={(event) =>
                setRates((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, titolo: event.target.value }
                      : item,
                  ),
                )
              }
              className={`${inputClass} md:col-span-4`}
            />
            <input
              type="date"
              value={rate.data_scadenza}
              onChange={(event) =>
                setRates((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, data_scadenza: event.target.value }
                      : item,
                  ),
                )
              }
              className={`${inputClass} md:col-span-2`}
            />
            <input
              value={rate.modalita_pagamento || ""}
              onChange={(event) =>
                setRates((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index
                      ? { ...item, modalita_pagamento: event.target.value }
                      : item,
                  ),
                )
              }
              className={`${inputClass} md:col-span-3`}
            />
            <div className="flex items-center justify-end font-display text-sm text-ink md:col-span-3">
              {rate.percentuale}% · {money(rate.importo)}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-4 text-xs text-fog">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={email}
              onChange={(e) => setEmail(e.target.checked)}
            />
            Promemoria email
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={whatsapp}
              onChange={(e) => setWhatsapp(e.target.checked)}
              disabled={!suggestion.data.cliente_telefono}
            />
            Promemoria WhatsApp
          </label>
          {whatsapp && (
            <label className="flex max-w-md items-start gap-2 text-[11px] leading-relaxed">
              <input
                type="checkbox"
                checked={whatsappConsent}
                onChange={(event) => setWhatsappConsent(event.target.checked)}
                className="mt-0.5"
              />
              Confermo che il cliente ha autorizzato i promemoria WhatsApp al
              numero indicato nel cantiere.
            </label>
          )}
        </div>
        <button
          type="button"
          disabled={
            create.isPending ||
            (whatsapp && !whatsappConsent) ||
            Math.abs(total - suggestion.data.totale_contratto) > 0.009
          }
          onClick={() => create.mutate()}
          className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-xs font-display uppercase text-white disabled:opacity-40"
        >
          {create.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Attiva piano
        </button>
      </div>
    </section>
  );
}

export default function PaymentControl({ cantiereId }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["payment-control", cantiereId],
    queryFn: async () =>
      (await client.get(`/cantieri/${cantiereId}/controllo-economico`)).data,
    enabled: Boolean(cantiereId),
  });
  const [payment, setPayment] = useState({
    id: "",
    importo: "",
    metodo: "Bonifico",
  });
  const [extra, setExtra] = useState({
    titolo: "",
    descrizione: "",
    imponibile: "",
    iva_percentuale: 10,
    data_scadenza: "",
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["payment-control", cantiereId] });
    qc.invalidateQueries({ queryKey: ["economics"] });
  };

  const pay = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/economics/incassi/${payment.id}/pagamenti`, {
          importo: Number(payment.importo),
          data_pagamento: new Date().toISOString().slice(0, 10),
          metodo: payment.metodo,
        })
      ).data,
    onSuccess: () => {
      toast.success("Pagamento registrato");
      setPayment({ id: "", importo: "", metodo: "Bonifico" });
      refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Pagamento non registrato"),
  });
  const addExtra = useMutation({
    mutationFn: async () =>
      (
        await client.post(`/cantieri/${cantiereId}/extra`, {
          ...extra,
          imponibile: Number(extra.imponibile),
          iva_percentuale: Number(extra.iva_percentuale),
          data_scadenza: extra.data_scadenza || null,
        })
      ).data,
    onSuccess: () => {
      toast.success("Extra registrato");
      setExtra({
        titolo: "",
        descrizione: "",
        imponibile: "",
        iva_percentuale: 10,
        data_scadenza: "",
      });
      refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Extra non registrato"),
  });
  const document = useMutation({
    mutationFn: async (item) =>
      (
        await client.post(`/cantieri/${cantiereId}/documenti-economici`, {
          tipo: "autorizzazione_extra",
          riferimento_id: item.id,
        })
      ).data,
    onSuccess: () => {
      toast.success("Nota extra pronta per la sottoscrizione");
      refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "Documento non generato"),
  });
  const linkSal = useMutation({
    mutationFn: async ({ incassoId, salId }) =>
      (
        await client.patch(`/economics/incassi/${incassoId}/sal`, {
          sal_id: salId || null,
        })
      ).data,
    onSuccess: () => {
      toast.success("SAL collegato alla rata");
      refresh();
    },
    onError: (error) =>
      toast.error(error?.response?.data?.detail || "SAL non collegato"),
  });
  const openDocument = async (item) => {
    try {
      const response = await client.get(`/documenti-economici/${item.id}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Documento non disponibile");
    }
  };

  if (!cantiereId)
    return (
      <p className="py-10 text-center text-fog">
        Seleziona un cantiere per aprire il controllo economico.
      </p>
    );
  if (query.isLoading)
    return (
      <p className="py-10 text-center text-fog">Caricamento piano economico…</p>
    );
  if (query.isError)
    return (
      <p className="py-10 text-center text-red-300">
        Controllo economico non disponibile.
      </p>
    );
  const data = query.data;
  if (!data.piano)
    return <PlanSetup cantiereId={cantiereId} onCreated={refresh} />;

  return (
    <div className="space-y-6">
      <Summary data={data.riepilogo} />
      {data.riepilogo.scaduto > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-500/5 p-4 text-sm text-red-300">
          <BellRing className="h-5 w-5" /> Scaduto da incassare:{" "}
          {money(data.riepilogo.scaduto)}
        </div>
      )}
      <section>
        <h3 className="font-display uppercase text-ink">Rate e pagamenti</h3>
        <div className="mt-3 space-y-2">
          {data.rate.map((rate) => (
            <article
              key={rate.id}
              className="rounded-xl border border-stroke bg-surface p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-display uppercase text-fog">
                    Rata {rate.numero_rata} · {rate.tipo_rata}
                  </p>
                  <h4 className="mt-1 font-display uppercase text-ink">
                    {rate.descrizione}
                  </h4>
                  <p className="mt-1 text-xs text-fog">
                    Scadenza {dateLabel(rate.data_prevista)} ·{" "}
                    {rate.modalita_pagamento || "Modalità da definire"}
                  </p>
                  <select
                    value={rate.sal_id || ""}
                    onChange={(event) =>
                      linkSal.mutate({
                        incassoId: rate.id,
                        salId: event.target.value,
                      })
                    }
                    className="mt-2 rounded-lg border border-stroke bg-surface-2 px-2 py-1.5 text-xs text-ink"
                  >
                    <option value="">Nessun SAL collegato</option>
                    {(data.sal_disponibili || []).map((sal) => (
                      <option key={sal.id} value={sal.id}>
                        SAL {sal.numero} · {money(sal.totale)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="text-right">
                  <p className="font-display text-brand">
                    {money(rate.importo)}
                  </p>
                  <p className="text-xs text-fog">
                    Pagato {money(rate.pagato)} · Residuo {money(rate.residuo)}
                  </p>
                </div>
              </div>
              {rate.stato !== "incassato" &&
                rate.stato !== "annullato" &&
                (payment.id === rate.id ? (
                  <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={payment.importo}
                      onChange={(e) =>
                        setPayment((current) => ({
                          ...current,
                          importo: e.target.value,
                        }))
                      }
                      placeholder={`Max ${rate.residuo}`}
                      className={inputClass}
                    />
                    <input
                      value={payment.metodo}
                      onChange={(e) =>
                        setPayment((current) => ({
                          ...current,
                          metodo: e.target.value,
                        }))
                      }
                      className={inputClass}
                    />
                    <button
                      type="button"
                      onClick={() => pay.mutate()}
                      disabled={!payment.importo || pay.isPending}
                      className="rounded-lg bg-brand px-4 py-2 text-xs font-display uppercase text-white disabled:opacity-40"
                    >
                      Registra
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() =>
                      setPayment({
                        id: rate.id,
                        importo: rate.residuo,
                        metodo: rate.modalita_pagamento || "Bonifico",
                      })
                    }
                    className="mt-3 inline-flex items-center gap-2 text-xs text-brand"
                  >
                    <CircleDollarSign className="h-4 w-4" /> Registra pagamento
                  </button>
                ))}
            </article>
          ))}
        </div>
      </section>
      <section className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addExtra.mutate();
          }}
          className="space-y-3 rounded-2xl border border-stroke bg-surface p-5"
        >
          <h3 className="font-display uppercase text-ink">Nuovo extra</h3>
          <input
            required
            value={extra.titolo}
            onChange={(e) =>
              setExtra((current) => ({ ...current, titolo: e.target.value }))
            }
            placeholder="Titolo lavorazione"
            className={inputClass}
          />
          <textarea
            required
            value={extra.descrizione}
            onChange={(e) =>
              setExtra((current) => ({
                ...current,
                descrizione: e.target.value,
              }))
            }
            placeholder="Descrizione completa"
            className={inputClass}
          />
          <div className="grid grid-cols-3 gap-2">
            <input
              required
              type="number"
              min="0.01"
              step="0.01"
              value={extra.imponibile}
              onChange={(e) =>
                setExtra((current) => ({
                  ...current,
                  imponibile: e.target.value,
                }))
              }
              placeholder="Imponibile"
              className={inputClass}
            />
            <input
              required
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={extra.iva_percentuale}
              onChange={(e) =>
                setExtra((current) => ({
                  ...current,
                  iva_percentuale: e.target.value,
                }))
              }
              className={inputClass}
            />
            <input
              type="date"
              value={extra.data_scadenza}
              onChange={(e) =>
                setExtra((current) => ({
                  ...current,
                  data_scadenza: e.target.value,
                }))
              }
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            disabled={addExtra.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-xs font-display uppercase text-white disabled:opacity-40"
          >
            <Plus className="h-4 w-4" /> Aggiungi extra
          </button>
        </form>
        <div className="space-y-2">
          {data.extra.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-stroke bg-surface p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase text-fog">
                    Extra {item.numero} · {item.stato}
                  </p>
                  <h4 className="mt-1 font-display uppercase text-ink">
                    {item.titolo}
                  </h4>
                  <p className="mt-1 text-xs text-fog">{item.descrizione}</p>
                </div>
                <p className="font-display text-brand">{money(item.totale)}</p>
              </div>
              {item.stato === "bozza" && (
                <button
                  type="button"
                  onClick={() => document.mutate(item)}
                  className="mt-3 inline-flex items-center gap-2 text-xs text-brand"
                >
                  <FileSignature className="h-4 w-4" /> Genera nota da
                  sottoscrivere
                </button>
              )}
            </article>
          ))}
          {!data.extra.length && (
            <p className="rounded-xl border border-dashed border-stroke p-8 text-center text-fog">
              Nessun extra.
            </p>
          )}
        </div>
      </section>
      <section>
        <h3 className="font-display uppercase text-ink">
          Documenti e sottoscrizioni
        </h3>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {data.documenti.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => openDocument(item)}
              className="flex items-center justify-between rounded-xl border border-stroke bg-surface p-4 text-sm text-ink"
            >
              <span>
                {item.tipo === "riepilogo_sal"
                  ? "Nota riepilogo SAL"
                  : "Autorizzazione extra"}
              </span>
              <span className="text-xs uppercase text-fog">
                {item.sottoscritto ? "sottoscritto" : item.stato}
              </span>
            </button>
          ))}
        </div>
      </section>
      <section>
        <h3 className="font-display uppercase text-ink">Registro promemoria</h3>
        <div className="mt-3 space-y-2">
          {(data.notifiche || []).slice(0, 20).map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stroke bg-surface px-4 py-3 text-xs"
            >
              <span className="text-ink">
                Rata {item.numero_rata} · {item.canale} · {item.tipo}
              </span>
              <span className="text-fog">
                {dateLabel(item.programmata_per)} · {item.stato}
              </span>
            </div>
          ))}
          {!data.notifiche?.length && (
            <p className="rounded-xl border border-dashed border-stroke p-6 text-center text-sm text-fog">
              Nessun promemoria pianificato.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
