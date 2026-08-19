import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";
import client from "@/lib/api";
import { formatArrivalDateTime, formatEuro } from "@/lib/format";
import { LEAD_AUTO_REFRESH_MS, refreshLeadViews } from "@/lib/leadSync";
import { STATI, priority, initials, ageColor } from "@/dashboard/leadMeta";
import {
  filterLeadsByName,
  normalizePipelineSearch,
  paginatePipelineLeads,
} from "@/dashboard/pipelineView";

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
  const [searchQuery, setSearchQuery] = useState("");
  const [pagesByColumn, setPagesByColumn] = useState({});

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
    onSuccess: (updatedLead) => {
      refreshLeadViews(qc, {
        leadId: updatedLead.id,
        updatedLead,
        includeAppointments: true,
      });
      toast.success("Lead spostato");
    },
  });

  const hasSearch = normalizePipelineSearch(searchQuery).length > 0;
  const visibleColumns = useMemo(
    () =>
      (data?.columns || []).map((column) => {
        const matchingLeads = filterLeadsByName(column.leads, searchQuery);
        const pagination = paginatePipelineLeads(
          matchingLeads,
          pagesByColumn[column.key],
        );
        const filteredValue = matchingLeads.reduce(
          (total, lead) =>
            total +
            ((Number(lead.range_alto) || 0) + (Number(lead.range_basso) || 0)) /
              2,
          0,
        );

        return {
          ...column,
          ...pagination,
          originalCount: column.count ?? column.leads?.length ?? 0,
          displayedValue: hasSearch ? Math.round(filteredValue) : column.valore,
        };
      }),
    [data?.columns, hasSearch, pagesByColumn, searchQuery],
  );
  const matchingLeadCount = visibleColumns.reduce(
    (total, column) => total + column.total,
    0,
  );

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

  const updateSearch = (value) => {
    setSearchQuery(value);
    setPagesByColumn({});
  };

  const goToPage = (columnKey, page) => {
    setPagesByColumn((current) => ({ ...current, [columnKey]: page }));
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
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-h-11 w-full max-w-md items-center gap-2 rounded-full border border-stroke bg-surface px-4 transition-colors focus-within:border-brand">
          <Search className="h-4 w-4 shrink-0 text-fog" aria-hidden="true" />
          <label htmlFor="pipeline-lead-search" className="sr-only">
            Cerca lead per nome
          </label>
          <input
            id="pipeline-lead-search"
            type="search"
            value={searchQuery}
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Cerca lead per nome..."
            className="min-w-0 flex-1 bg-transparent font-body text-sm text-ink outline-none placeholder:text-fog"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => updateSearch("")}
              aria-label="Cancella ricerca lead"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-fog transition-colors hover:bg-bg hover:text-ink"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
        <p className="font-body text-xs text-fog" aria-live="polite">
          {hasSearch
            ? `${matchingLeadCount} ${matchingLeadCount === 1 ? "lead trovato" : "lead trovati"}`
            : "Massimo 6 lead per colonna"}
        </p>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar">
        {visibleColumns.map((col) => (
          <div
            key={col.key}
            role="group"
            aria-label={`${col.label}: ${col.total} lead visibili`}
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
                  {hasSearch
                    ? `${col.total}/${col.originalCount}`
                    : col.originalCount}
                </span>
              </div>
            </div>
            <div className="font-display text-[10px] uppercase text-fog px-1 mb-2">
              {formatEuro(col.displayedValue)}
            </div>
            <div className="space-y-2 min-h-[60px]">
              {col.items.map((l) => {
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
              {col.total === 0 && (
                <div className="rounded-xl border border-dashed border-stroke px-3 py-5 text-center font-body text-xs text-fog">
                  {hasSearch
                    ? "Nessun lead corrispondente"
                    : "Nessun lead in questa fase"}
                </div>
              )}
            </div>
            {col.total > 0 && (
              <div className="mt-3 flex items-center justify-between gap-2 border-t border-stroke pt-3">
                <span className="font-body text-[10px] text-fog">
                  {col.start}-{col.end} di {col.total}
                </span>
                {col.totalPages > 1 && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={col.page === 1}
                      onClick={() => goToPage(col.key, col.page - 1)}
                      aria-label={`Pagina precedente per ${col.label}`}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-stroke text-fog transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-35"
                    >
                      <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <span className="min-w-12 text-center font-display text-[10px] text-fog">
                      {col.page}/{col.totalPages}
                    </span>
                    <button
                      type="button"
                      disabled={col.page === col.totalPages}
                      onClick={() => goToPage(col.key, col.page + 1)}
                      aria-label={`Pagina successiva per ${col.label}`}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-stroke text-fog transition-colors hover:border-brand hover:text-brand disabled:cursor-not-allowed disabled:opacity-35"
                    >
                      <ChevronRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
