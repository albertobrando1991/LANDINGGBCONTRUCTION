import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, GitCompareArrows } from "lucide-react";
import client from "@/lib/api";
import {
  filterRigheVariante,
  formatDelta,
  VARIANTE_CLASSI,
} from "@/lib/varianti";

const CLASS_STYLE = {
  invariata: "border-stroke text-fog",
  modificata: "border-brand/50 bg-brand/10 text-brand",
  nuova: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  soppressa: "border-red-500/40 bg-red-500/10 text-red-300",
};

function euro(value) {
  return Number(value || 0).toLocaleString("it-IT", {
    style: "currency",
    currency: "EUR",
  });
}

function Stat({ label, value, accent = false }) {
  return (
    <div className="border-l border-stroke px-4 first:border-l-0">
      <p className="text-[10px] font-display uppercase tracking-[0.16em] text-fog">
        {label}
      </p>
      <p className={`mt-1 text-xl font-display ${accent ? "text-brand" : "text-ink"}`}>
        {value}
      </p>
    </div>
  );
}

export default function VarianteComparison({ computoId }) {
  const [filtro, setFiltro] = useState("tutte");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["confronto-variante", computoId],
    queryFn: async () =>
      (await client.get(`/computi/${computoId}/confronto-variante`)).data,
  });

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-stroke bg-surface p-5 text-sm text-fog">
        Preparazione quadro di confronto…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-5 text-sm text-red-300">
        Quadro di confronto non disponibile.
      </div>
    );
  }

  const summary = data.riepilogo;
  const righe = filterRigheVariante(data.righe, filtro);
  const delta = Number(summary.delta_importo || 0);
  const DeltaIcon = delta >= 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <section aria-labelledby="variante-title" className="overflow-hidden rounded-2xl border border-stroke bg-surface">
      <div className="relative border-b border-stroke bg-surface-2 px-5 py-5">
        <div className="absolute bottom-0 left-0 top-0 w-1 bg-brand" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-[10px] font-display uppercase tracking-[0.2em] text-brand">
              <GitCompareArrows className="h-4 w-4" /> Registro economico
            </p>
            <h2 id="variante-title" className="mt-2 text-xl font-display uppercase text-ink">
              Quadro variante / contratto
            </h2>
            <p className="mt-1 text-xs text-fog">
              Base {data.base.numero || "senza numero"} · Variante {data.variante.numero || "in bozza"}
            </p>
          </div>
          <div className={`flex items-center gap-2 font-display text-2xl ${delta > 0 ? "text-brand" : delta < 0 ? "text-emerald-300" : "text-fog"}`}>
            <DeltaIcon className="h-5 w-5" />
            {formatDelta(delta)} €
            {summary.delta_percentuale !== null && (
              <span className="text-xs text-fog">({formatDelta(summary.delta_percentuale)}%)</span>
            )}
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-y-4 md:grid-cols-4">
          <Stat label="Contratto base" value={euro(summary.totale_base)} />
          <Stat label="Totale variante" value={euro(summary.totale_variante)} accent />
          <Stat label="Modificate" value={summary.conteggi.modificata} />
          <Stat label="Nuove / soppresse" value={`${summary.conteggi.nuova} / ${summary.conteggi.soppressa}`} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-stroke px-4 py-3" aria-label="Filtra voci variante">
        {VARIANTE_CLASSI.map((classe) => {
          const count = classe === "tutte" ? data.righe.length : summary.conteggi[classe];
          return (
            <button
              key={classe}
              type="button"
              aria-pressed={filtro === classe}
              onClick={() => setFiltro(classe)}
              className={`rounded-full border px-3 py-1 text-[10px] font-display uppercase tracking-wider transition-colors ${
                filtro === classe
                  ? "border-brand bg-brand text-white"
                  : `${CLASS_STYLE[classe] || "border-stroke text-fog"} hover:text-ink`
              }`}
            >
              {classe} · {count}
            </button>
          );
        })}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-[960px] w-full text-sm">
          <thead className="text-[10px] font-display uppercase tracking-wider text-fog">
            <tr>
              <th className="px-4 py-3 text-left">Classificazione</th>
              <th className="px-4 py-3 text-left">Voce</th>
              <th className="px-4 py-3 text-right">Base</th>
              <th className="px-4 py-3 text-right">Variante</th>
              <th className="px-4 py-3 text-right">Delta</th>
              <th className="px-4 py-3 text-right">% contratto</th>
            </tr>
          </thead>
          <tbody>
            {righe.map((riga) => (
              <tr key={riga.voce_variante_id || riga.voce_base_id} className="border-t border-stroke/60">
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-display uppercase tracking-wider ${CLASS_STYLE[riga.classificazione]}`}>
                    {riga.classificazione}
                  </span>
                </td>
                <td className="max-w-[380px] px-4 py-3 text-ink">
                  {riga.descrizione_variante || riga.descrizione_base}
                  {riga.descrizione_base && riga.descrizione_variante && riga.descrizione_base !== riga.descrizione_variante && (
                    <span className="mt-1 block text-xs text-fog line-through">{riga.descrizione_base}</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right text-fog">{euro(riga.importo_base)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right text-ink">{euro(riga.importo_variante)}</td>
                <td className={`whitespace-nowrap px-4 py-3 text-right font-medium ${Number(riga.delta_importo) > 0 ? "text-brand" : Number(riga.delta_importo) < 0 ? "text-emerald-300" : "text-fog"}`}>
                  {formatDelta(riga.delta_importo)} €
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right text-fog">
                  {riga.delta_percentuale_contratto === null ? "—" : `${formatDelta(riga.delta_percentuale_contratto)}%`}
                </td>
              </tr>
            ))}
            {righe.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-fog">Nessuna voce in questa categoria.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
