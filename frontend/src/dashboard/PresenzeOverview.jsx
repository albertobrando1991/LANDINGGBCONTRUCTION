import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarDays, HardHat, Loader2, Users } from "lucide-react";
import client from "@/lib/api";

function today() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl border border-stroke bg-bg p-3">
      <p className="inline-flex items-center gap-1 text-[10px] uppercase text-fog">
        <Icon className="h-3.5 w-3.5 text-brand" /> {label}
      </p>
      <p className="mt-1 font-display text-xl text-ink">{value || 0}</p>
    </div>
  );
}

export default function PresenzeOverview({ data, onDataChange }) {
  const selected = data || today();
  const query = useQuery({
    queryKey: ["presenze-personale", selected],
    queryFn: async () =>
      (await client.get("/personale/presenze", { params: { data: selected } }))
        .data,
  });
  return (
    <section className="rounded-2xl border border-brand/30 bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-[10px] uppercase tracking-[0.2em] text-brand">
            Presenze giornaliere
          </p>
          <h2 className="mt-1 font-display text-xl uppercase text-ink">
            Chi sta lavorando oggi
          </h2>
        </div>
        <label className="inline-flex items-center gap-2 rounded-xl border border-stroke bg-bg px-3 py-2">
          <CalendarDays className="h-4 w-4 text-brand" />
          <input
            type="date"
            value={selected}
            onChange={(event) => onDataChange(event.target.value)}
            className="bg-transparent text-sm text-ink outline-none"
            aria-label="Data panoramica presenze"
          />
        </label>
      </div>
      {query.isLoading ? (
        <div className="mt-5 inline-flex items-center gap-2 text-xs text-fog">
          <Loader2 className="h-4 w-4 animate-spin" /> Caricamento presenze...
        </div>
      ) : query.isError ? (
        <p className="mt-5 text-xs text-red-400">Presenze non disponibili.</p>
      ) : (
        <>
          <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric
              icon={Users}
              label="Totale persone"
              value={query.data.totale_unita}
            />
            <Metric
              icon={HardHat}
              label="Interni"
              value={query.data.totale_interni}
            />
            <Metric
              icon={Users}
              label="Subappalto"
              value={query.data.totale_subappaltatori}
            />
            <Metric
              icon={Building2}
              label="Cantieri"
              value={query.data.cantieri_attivi}
            />
          </div>
          <div className="mt-4 grid gap-2 lg:grid-cols-2">
            {(query.data.righe || []).map((item) => (
              <article
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-stroke bg-bg px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs text-ink">
                    {item.personale_nome}
                  </p>
                  <p className="truncate text-[10px] text-fog">
                    {item.cantiere_cliente}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-brand/10 px-2 py-1 text-[9px] uppercase text-brand">
                  {item.unita_presenti} · {Number(item.ore_lavorate || 0)}h
                </span>
              </article>
            ))}
            {!query.data.righe?.length && (
              <p className="lg:col-span-2 py-4 text-center text-xs text-fog">
                Nessuna presenza registrata per questa giornata.
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
