import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CalendarDays, Clock3 } from "lucide-react";
import { toast } from "sonner";
import client from "@/lib/api";
import { formatArrivalDateTime, formatEuro } from "@/lib/format";
import { LEAD_AUTO_REFRESH_MS, refreshLeadViews } from "@/lib/leadSync";
import { STATI, priority, initials, ageColor } from "@/dashboard/leadMeta";

const WEEKDAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
const MONTHS = [
  "gen",
  "feb",
  "mar",
  "apr",
  "mag",
  "giu",
  "lug",
  "ago",
  "set",
  "ott",
  "nov",
  "dic",
];

function formatApptDay(iso) {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

function appointmentLabel(lead) {
  const appt = lead?.sopralluogo;
  if (!appt?.date) return null;
  const day = formatApptDay(appt.date);
  const time = appt.start
    ? `${appt.start}${appt.end ? `–${appt.end}` : ""}`
    : "";
  return [day, time].filter(Boolean).join(" · ");
}

export default function Pipeline() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["pipeline"],
    queryFn: async () => (await client.get("/pipeline")).data,
    // Aggiornamento automatico: appuntamenti e spostamenti compaiono senza refresh manuale
    refetchInterval: LEAD_AUTO_REFRESH_MS,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });

  const move = useMutation({
    mutationFn: async ({ id, status }) =>
      (await client.patch(`/leads/${id}`, { status })).data,
    onSuccess: async (updatedLead) => {
      await refreshLeadViews(qc, {
        leadId: updatedLead.id,
        updatedLead,
        includeAppointments: true,
      });
      toast.success("Lead spostato");
    },
  });

  if (isLoading)
    return (
      <div className="text-fog font-display uppercase animate-pulse">
        Caricamento…
      </div>
    );

  const onDrop = (colKey) => {
    if (dragId) move.mutate({ id: dragId, status: colKey });
    setDragId(null);
    setOverCol(null);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display font-bold uppercase text-3xl text-ink">
            Pipeline
          </h1>
          <p className="font-body text-sm text-fog mt-1">
            Collegata ai sopralluoghi: le prenotazioni aggiornano
            automaticamente la colonna «Sopralluogo fissato».
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/dashboard/sopralluoghi")}
          className="inline-flex items-center gap-2 rounded-full border border-stroke bg-surface px-4 py-2 font-display text-xs uppercase tracking-wider text-ink hover:border-brand hover:text-brand transition-colors"
        >
          <CalendarDays className="w-4 h-4" />
          Apri calendario sopralluoghi
        </button>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar">
        {(data?.columns || []).map((col) => (
          <div
            key={col.key}
            role="group"
            aria-label={`${col.label}: ${col.count} lead`}
            onDragOver={(e) => {
              e.preventDefault();
              setOverCol(col.key);
            }}
            onDrop={() => onDrop(col.key)}
            className={`w-72 shrink-0 bg-surface border rounded-2xl p-3 transition-colors ${overCol === col.key ? "border-brand" : "border-stroke"}`}
          >
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${STATI[col.key]?.dot}`}
                />
                <span className="font-display uppercase text-xs text-ink">
                  {col.label}
                </span>
                <span className="font-display text-xs text-fog">
                  {col.count}
                </span>
              </div>
            </div>
            <div className="font-display text-[10px] uppercase text-fog px-1 mb-2">
              {formatEuro(col.valore)}
            </div>
            <div className="space-y-2 min-h-[60px]">
              {col.leads.map((l) => {
                const appt = appointmentLabel(l);
                return (
                  <div
                    key={l.id}
                    draggable
                    data-testid={`kanban-card-${l.id}`}
                    onDragStart={() => setDragId(l.id)}
                    className={`bg-bg border border-stroke border-l-4 ${ageColor(l.giorni_in_stato)} rounded-xl p-3 cursor-grab active:cursor-grabbing hover:border-brand transition-colors`}
                  >
                    <button
                      type="button"
                      onClick={() => navigate(`/dashboard/lead/${l.id}`)}
                      className="block w-full text-left"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-display uppercase text-xs text-ink truncate">
                          {l.nome}
                        </span>
                        <span
                          className={`w-2 h-2 rounded-full ${priority(l.score).dot}`}
                        />
                      </div>
                      <div className="font-body text-[11px] text-fog">
                        {l.citta}
                      </div>
                      <div className="mt-2 flex items-center gap-1.5 font-body text-[10px] text-fog">
                        <Clock3
                          className="h-3 w-3 shrink-0"
                          aria-hidden="true"
                        />
                        <span>
                          Arrivato il{" "}
                          {formatArrivalDateTime(l.data_arrivo || l.created_at)}
                        </span>
                      </div>
                      {appt && (
                        <div
                          className="mt-2 inline-flex max-w-full items-center gap-1.5 rounded-full bg-violet-500/15 px-2 py-1 font-display text-[10px] uppercase tracking-wide text-violet-300"
                          title="Appuntamento dal modulo Sopralluoghi"
                        >
                          <CalendarDays className="w-3 h-3 shrink-0" />
                          <span className="truncate">{appt}</span>
                        </div>
                      )}
                      <div className="flex items-center justify-between mt-2">
                        <span className="font-display text-xs text-brand">
                          {formatEuro(l.range_basso)}
                        </span>
                        {l.owner && (
                          <span className="w-6 h-6 rounded-full bg-brand/20 text-brand inline-flex items-center justify-center font-display text-[9px]">
                            {initials(l.owner)}
                          </span>
                        )}
                      </div>
                      <div className="font-body text-[10px] text-fog mt-1">
                        {l.giorni_in_stato}gg in stato
                      </div>
                    </button>
                    <label className="mt-3 block">
                      <span className="sr-only">
                        Sposta {l.nome} in un altro stato
                      </span>
                      <select
                        value={col.key}
                        disabled={move.isPending}
                        onPointerDown={(event) => event.stopPropagation()}
                        onChange={(event) => {
                          event.stopPropagation();
                          move.mutate({
                            id: l.id,
                            status: event.target.value,
                          });
                        }}
                        className="w-full rounded-lg border border-stroke bg-surface px-2 py-1.5 font-display text-[10px] uppercase text-fog outline-none focus:border-brand disabled:opacity-50"
                      >
                        {(data?.columns || []).map((target) => (
                          <option key={target.key} value={target.key}>
                            {target.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
