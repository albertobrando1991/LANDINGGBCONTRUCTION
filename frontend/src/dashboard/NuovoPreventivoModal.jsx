import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { X, Loader2, FileText, AlertTriangle } from "lucide-react";
import client, { formatApiErrorDetail } from "@/lib/api";

const TIPI = ["appartamento", "villa", "ufficio", "negozio", "capannone"];
const LIVELLI = [
  { id: "essenziale", label: "Essenziale — Rinnovare" },
  { id: "premium", label: "Premium — Trasformare" },
  { id: "luxury", label: "Luxury — Tutto incluso" },
];
const STILI = ["Moderno minimal", "Classico elegante", "Industrial loft", "Contemporaneo caldo"];
const TEMPI = ["Subito", "Entro 3 mesi", "Entro 6 mesi", "Sto valutando"];

const EMPTY = {
  nome: "", email: "", telefono: "", citta: "",
  tipo_immobile: "appartamento", mq: 80, livello: "premium",
  bagni: 1, camere: 2, cucina: true,
  stile: "Moderno minimal", tempistiche: "Sto valutando",
};

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block font-display uppercase text-[10px] text-fog mb-1">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog outline-none focus:border-brand";

// Modal staff: crea un preventivo manuale (cliente da telefono/sportello).
export default function NuovoPreventivoModal({ open, onClose }) {
  const [f, setF] = useState(EMPTY);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const set = (patch) => setF((prev) => ({ ...prev, ...patch }));

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        nome: f.nome.trim(),
        email: f.email.trim(),
        telefono: f.telefono.trim(),
        citta: f.citta.trim(),
        config: {
          tipo_immobile: f.tipo_immobile,
          mq: Number(f.mq) || 0,
          livello: f.livello,
          bagni: Number(f.bagni) || 0,
          camere: Number(f.camere) || 0,
          cucina: Boolean(f.cucina),
          stile: f.stile,
          tempistiche: f.tempistiche,
        },
      };
      return (await client.post("/preventivi", payload)).data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["preventivi"] });
      toast.success("Preventivo creato");
      setF(EMPTY);
      onClose?.();
      if (data?.id) navigate(`/dashboard/lead/${data.id}`);
    },
    onError: (err) => {
      toast.error(formatApiErrorDetail(err?.response?.data?.detail) || "Creazione preventivo non riuscita.");
    },
  });

  if (!open) return null;

  const canSubmit =
    !mutation.isPending &&
    f.nome.trim() && f.email.trim() && f.telefono.trim() && f.citta.trim() &&
    Number(f.mq) > 0;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !mutation.isPending && onClose?.()} />
      <div className="relative w-full max-w-xl bg-surface border border-stroke rounded-2xl shadow-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 h-14 border-b border-stroke">
          <div className="flex items-center gap-2 font-display uppercase text-sm text-ink">
            <FileText className="w-4 h-4 text-brand" /> Nuovo preventivo
          </div>
          <button onClick={() => !mutation.isPending && onClose?.()} className="text-fog hover:text-ink disabled:opacity-40" disabled={mutation.isPending}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[72vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nome cliente">
              <input className={inputCls} value={f.nome} onChange={(e) => set({ nome: e.target.value })} placeholder="Mario Rossi" />
            </Field>
            <Field label="Email">
              <input type="email" className={inputCls} value={f.email} onChange={(e) => set({ email: e.target.value })} placeholder="mario@email.it" />
            </Field>
            <Field label="Telefono">
              <input className={inputCls} value={f.telefono} onChange={(e) => set({ telefono: e.target.value })} placeholder="333 1234567" />
            </Field>
            <Field label="Città">
              <input className={inputCls} value={f.citta} onChange={(e) => set({ citta: e.target.value })} placeholder="Napoli" />
            </Field>
          </div>

          <div className="border-t border-stroke pt-4 grid grid-cols-2 gap-3">
            <Field label="Tipo immobile">
              <select className={inputCls} value={f.tipo_immobile} onChange={(e) => set({ tipo_immobile: e.target.value })}>
                {TIPI.map((t) => <option key={t} value={t} className="capitalize bg-surface">{t}</option>)}
              </select>
            </Field>
            <Field label="Superficie (mq)">
              <input type="number" min="1" className={inputCls} value={f.mq} onChange={(e) => set({ mq: e.target.value })} />
            </Field>
            <Field label="Livello">
              <select className={inputCls} value={f.livello} onChange={(e) => set({ livello: e.target.value })}>
                {LIVELLI.map((l) => <option key={l.id} value={l.id} className="bg-surface">{l.label}</option>)}
              </select>
            </Field>
            <Field label="Stile">
              <select className={inputCls} value={f.stile} onChange={(e) => set({ stile: e.target.value })}>
                {STILI.map((s) => <option key={s} value={s} className="bg-surface">{s}</option>)}
              </select>
            </Field>
            <Field label="Bagni">
              <input type="number" min="0" className={inputCls} value={f.bagni} onChange={(e) => set({ bagni: e.target.value })} />
            </Field>
            <Field label="Camere">
              <input type="number" min="0" className={inputCls} value={f.camere} onChange={(e) => set({ camere: e.target.value })} />
            </Field>
            <Field label="Tempistiche">
              <select className={inputCls} value={f.tempistiche} onChange={(e) => set({ tempistiche: e.target.value })}>
                {TEMPI.map((t) => <option key={t} value={t} className="bg-surface">{t}</option>)}
              </select>
            </Field>
            <label className="flex items-center gap-2 mt-6">
              <input type="checkbox" checked={f.cucina} onChange={(e) => set({ cucina: e.target.checked })} className="accent-brand w-4 h-4" />
              <span className="font-display uppercase text-[10px] text-fog">Cucina</span>
            </label>
          </div>

          <div className="flex items-start gap-2 bg-warning/10 border border-warning/30 rounded-xl px-3 py-2 text-warning text-[11px] font-body">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            La stima è calcolata col motore predittivo. Nessuna email automatica al cliente: invia il preventivo manualmente dalla scheda lead.
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-stroke">
          <button onClick={() => !mutation.isPending && onClose?.()} disabled={mutation.isPending} className="font-display uppercase text-xs text-fog hover:text-ink px-4 py-2 disabled:opacity-40">
            Annulla
          </button>
          <button onClick={() => mutation.mutate()} disabled={!canSubmit} className="inline-flex items-center gap-2 font-display uppercase text-xs bg-brand text-white rounded-xl px-4 py-2 hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed">
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            {mutation.isPending ? "Calcolo…" : "Crea preventivo"}
          </button>
        </div>
      </div>
    </div>
  );
}
