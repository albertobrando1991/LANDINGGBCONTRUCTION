import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapPin, Phone, Clock, CheckCircle2, User, CalendarPlus, Trash2, Loader2, Plus,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";

const WEEKDAYS = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"];
const MONTHS = [
  "gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic",
];

function formatDay(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export default function Sopralluoghi() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const today = new Date().toISOString().slice(0, 10);
  const [slot, setSlot] = useState({ date: today, start: "09:00", end: "10:00", tecnico: "" });

  const { data: slots = [], isLoading: loadingSlots } = useQuery({
    queryKey: ["sopralluogo-slots"],
    queryFn: async () => (await client.get("/sopralluoghi/slots")).data,
  });
  const { data: booked = [], isLoading: loadingBooked } = useQuery({
    queryKey: ["sopralluoghi"],
    queryFn: async () => (await client.get("/sopralluoghi")).data,
  });

  const createSlot = useMutation({
    mutationFn: (body) => client.post("/sopralluoghi/slots", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sopralluogo-slots"] });
      toast.success("Slot aggiunto");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const deleteSlot = useMutation({
    mutationFn: (id) => client.delete(`/sopralluoghi/slots/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sopralluogo-slots"] });
      toast.success("Slot rimosso");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const freeSlots = slots.filter((s) => s.status === "free");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display font-bold uppercase text-3xl text-ink">Sopralluoghi</h1>
        <p className="font-body text-sm text-fog mt-1">
          Inserisci gli slot liberi: i clienti prenotano direttamente dal calendario in landing.
        </p>
      </div>

      {/* Gestione disponibilità */}
      <section className="bg-surface border border-stroke rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <CalendarPlus className="w-5 h-5 text-brand" />
          <h2 className="font-display font-semibold uppercase text-sm text-ink">
            Aggiungi disponibilità
          </h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 items-end">
          <label className="flex flex-col gap-1">
            <span className="font-display uppercase text-[10px] text-fog">Giorno</span>
            <input type="date" value={slot.date} min={today}
              onChange={(e) => setSlot((s) => ({ ...s, date: e.target.value }))}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-display uppercase text-[10px] text-fog">Inizio</span>
            <input type="time" value={slot.start}
              onChange={(e) => setSlot((s) => ({ ...s, start: e.target.value }))}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-display uppercase text-[10px] text-fog">Fine</span>
            <input type="time" value={slot.end}
              onChange={(e) => setSlot((s) => ({ ...s, end: e.target.value }))}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-display uppercase text-[10px] text-fog">Tecnico (opz.)</span>
            <input type="text" value={slot.tecnico} placeholder="es. Giovanni"
              onChange={(e) => setSlot((s) => ({ ...s, tecnico: e.target.value }))}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm placeholder:text-fog focus:outline-none focus:border-brand" />
          </label>
          <button
            onClick={() => createSlot.mutate(slot)}
            disabled={createSlot.isPending}
            className="bg-brand text-white rounded-xl px-4 py-2.5 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {createSlot.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Aggiungi
          </button>
        </div>

        <div className="mt-5">
          <p className="font-display uppercase text-[10px] text-fog mb-2">
            Slot liberi ({freeSlots.length})
          </p>
          {loadingSlots ? (
            <p className="font-body text-sm text-fog animate-pulse">Caricamento…</p>
          ) : freeSlots.length === 0 ? (
            <p className="font-body text-sm text-fog">Nessuno slot libero. Aggiungine sopra.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {freeSlots.map((s) => (
                <span key={s.id} className="inline-flex items-center gap-2 bg-bg border border-stroke rounded-full pl-3 pr-2 py-1.5 text-xs text-ink">
                  <Clock className="w-3 h-3 text-brand" />
                  {formatDay(s.date)} · {s.start}–{s.end}
                  {s.tecnico ? ` · ${s.tecnico}` : ""}
                  <button onClick={() => deleteSlot.mutate(s.id)} className="text-fog hover:text-danger ml-1">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Appuntamenti prenotati */}
      <section>
        <h2 className="font-display font-semibold uppercase text-sm text-ink mb-3">
          Appuntamenti prenotati
        </h2>
        {loadingBooked ? (
          <p className="font-body text-fog animate-pulse">Caricamento…</p>
        ) : booked.length === 0 ? (
          <p className="font-body text-fog">Nessun sopralluogo prenotato.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {booked.map((s) => (
              <div key={s.id} data-testid={`sopralluogo-${s.id}`} className="bg-surface border border-stroke rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="font-display font-bold uppercase text-ink">{s.cliente || "Cliente"}</div>
                  {s.completato
                    ? <span className="font-display uppercase text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-full inline-flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Completato</span>
                    : <span className="font-display uppercase text-[10px] bg-violet-500/20 text-violet-400 px-2 py-1 rounded-full">Programmato</span>}
                </div>
                <div className="space-y-2 font-body text-sm text-fog">
                  <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-brand" /> {formatDay(s.data)} · {s.ora}{s.ora_fine ? `–${s.ora_fine}` : ""}</div>
                  {s.indirizzo && (
                    <a href={`https://maps.google.com/?q=${encodeURIComponent(s.indirizzo)}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 hover:text-ink"><MapPin className="w-4 h-4 text-brand" /> {s.indirizzo}</a>
                  )}
                  <div className="flex items-center gap-2 capitalize"><User className="w-4 h-4 text-brand" /> Tecnico: {s.tecnico}</div>
                  {s.tipo_immobile && <div className="capitalize">Progetto: {s.tipo_immobile}{s.mq ? ` · ${s.mq}mq` : ""}</div>}
                </div>
                <div className="flex gap-2 mt-4">
                  {s.telefono && (
                    <a href={`tel:${s.telefono}`} className="flex-1 bg-bg border border-stroke rounded-xl py-2 text-center font-display uppercase text-xs text-fog hover:text-ink hover:border-brand transition-colors inline-flex items-center justify-center gap-1"><Phone className="w-3 h-3" /> Chiama</a>
                  )}
                  {s.lead_id && (
                    <button onClick={() => navigate(`/dashboard/lead/${s.lead_id}`)} className="flex-1 bg-brand text-white rounded-xl py-2 font-display uppercase text-xs hover:scale-[1.02] transition-transform">
                      Apri lead
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
