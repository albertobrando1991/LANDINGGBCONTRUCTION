import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  CirclePause,
  Flag,
  HardHat,
  Loader2,
  MapPin,
  Plus,
  Save,
  User,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro } from "@/lib/format";

const DEFAULT_FASI = [
  { nome: "Demolizioni", stato: "da_iniziare" },
  { nome: "Impianti", stato: "da_iniziare" },
  { nome: "Massetti", stato: "da_iniziare" },
  { nome: "Pavimenti", stato: "da_iniziare" },
  { nome: "Finiture", stato: "da_iniziare" },
  { nome: "Consegna", stato: "da_iniziare" },
];

const FASE_META = {
  completata: { label: "Completata", bar: "bg-emerald-500" },
  in_corso: { label: "In corso", bar: "bg-brand" },
  da_iniziare: { label: "Da iniziare", bar: "bg-stroke" },
};

const STATO_META = {
  attivo: {
    label: "Attivo",
    icon: HardHat,
    pill: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  in_pausa: {
    label: "In pausa",
    icon: CirclePause,
    pill: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  },
  completato: {
    label: "Completato",
    icon: CheckCircle2,
    pill: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  },
};

const FILTERS = [
  { value: "attivo", label: "Attivi" },
  { value: "in_pausa", label: "In pausa" },
  { value: "completato", label: "Completati" },
  { value: "tutti", label: "Tutti" },
];

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function initialForm(capocantiere = "") {
  return {
    lead_id: "",
    cliente: "",
    indirizzo: "",
    importo: "",
    avanzamento: 0,
    milestone: "Apertura cantiere",
    milestone_data: todayDate(),
    capocantiere,
    criticita: "",
    stato: "attivo",
    note: "",
  };
}

function clampProgress(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function numberValue(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function dateInputValue(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function formatDateLabel(value) {
  if (!value) return "-";
  const source = String(value).length === 10 ? `${value}T00:00:00` : value;
  const d = new Date(source);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function leadImporto(lead) {
  const basso = numberValue(lead?.range_basso);
  const alto = numberValue(lead?.range_alto);
  return basso || alto ? Math.round((basso + alto) / 2) : "";
}

function cantiereDraft(c) {
  return {
    lead_id: c.lead_id || "",
    cliente: c.cliente || "",
    indirizzo: c.indirizzo || "",
    importo: c.importo ?? "",
    avanzamento: clampProgress(c.avanzamento ?? 0),
    milestone: c.milestone || "",
    milestone_data: dateInputValue(c.milestone_data),
    capocantiere: c.capocantiere || "",
    criticita: c.criticita || "",
    stato: c.stato || "attivo",
    note: c.note || "",
    fasi: (c.fasi?.length ? c.fasi : DEFAULT_FASI).map((f) => ({
      nome: f.nome,
      stato: f.stato || "da_iniziare",
    })),
  };
}

function payloadFromDraft(draft) {
  return {
    lead_id: draft.lead_id || null,
    cliente: draft.cliente.trim(),
    indirizzo: draft.indirizzo.trim(),
    importo: numberValue(draft.importo),
    avanzamento: clampProgress(draft.avanzamento),
    milestone: draft.milestone.trim(),
    milestone_data: draft.milestone_data || null,
    capocantiere: draft.capocantiere.trim(),
    criticita: draft.criticita.trim() || null,
    stato: draft.stato || "attivo",
    note: draft.note?.trim() || "",
    fasi: (draft.fasi?.length ? draft.fasi : DEFAULT_FASI).map((f) => ({
      nome: f.nome,
      stato: f.stato,
    })),
  };
}

function CantiereCard({ cantiere, staffNames, onSave, onComplete, saving }) {
  const [draft, setDraft] = useState(() => cantiereDraft(cantiere));
  const StatoIcon = STATO_META[draft.stato]?.icon || HardHat;

  useEffect(() => {
    setDraft(cantiereDraft(cantiere));
  }, [cantiere]);

  const setField = (field, value) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const setFase = (index, stato) => {
    setDraft((current) => ({
      ...current,
      fasi: current.fasi.map((fase, i) => (i === index ? { ...fase, stato } : fase)),
    }));
  };

  const save = () => {
    const payload = payloadFromDraft(draft);
    if (!payload.cliente) {
      toast.error("Cliente obbligatorio");
      return;
    }
    onSave(cantiere.id, payload);
  };

  return (
    <article data-testid={`cantiere-${cantiere.id}`} className="bg-surface border border-stroke rounded-2xl p-5 space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <span className="w-10 h-10 rounded-xl bg-brand/15 text-brand inline-flex items-center justify-center shrink-0">
            <HardHat className="w-5 h-5" />
          </span>
          <div className="min-w-0">
            <input
              value={draft.cliente}
              onChange={(e) => setField("cliente", e.target.value)}
              className="w-full bg-transparent font-display font-bold uppercase text-ink text-sm focus:outline-none focus:text-brand"
              aria-label="Cliente cantiere"
            />
            <div className="font-body text-xs text-fog flex items-center gap-1 mt-1 min-w-0">
              <MapPin className="w-3 h-3 shrink-0" />
              <input
                value={draft.indirizzo}
                onChange={(e) => setField("indirizzo", e.target.value)}
                placeholder="Indirizzo"
                className="w-full bg-transparent text-fog placeholder:text-fog/60 focus:outline-none focus:text-ink"
                aria-label="Indirizzo cantiere"
              />
            </div>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-display uppercase text-[10px] ${STATO_META[draft.stato]?.pill}`}>
          <StatoIcon className="w-3 h-3" />
          {STATO_META[draft.stato]?.label || draft.stato}
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Importo</span>
          <input
            type="number"
            min="0"
            value={draft.importo}
            onChange={(e) => setField("importo", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          />
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Stato</span>
          <select
            value={draft.stato}
            onChange={(e) => setField("stato", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          >
            {Object.entries(STATO_META).map(([key, meta]) => (
              <option key={key} value={key}>{meta.label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Capocantiere</span>
          <select
            value={draft.capocantiere}
            onChange={(e) => setField("capocantiere", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          >
            <option value="">Da assegnare</option>
            {staffNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
            {draft.capocantiere && !staffNames.includes(draft.capocantiere) && (
              <option value={draft.capocantiere}>{draft.capocantiere}</option>
            )}
          </select>
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Data milestone</span>
          <input
            type="date"
            value={draft.milestone_data}
            onChange={(e) => setField("milestone_data", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          />
        </label>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <span className="font-display uppercase text-xs text-fog">Avanzamento</span>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="0"
              max="100"
              value={draft.avanzamento}
              onChange={(e) => setField("avanzamento", clampProgress(e.target.value))}
              className="w-16 bg-bg border border-stroke rounded-lg px-2 py-1 text-right text-ink text-sm focus:outline-none focus:border-brand"
            />
            <span className="font-display text-sm text-ink">%</span>
          </div>
        </div>
        <input
          type="range"
          min="0"
          max="100"
          value={draft.avanzamento}
          onChange={(e) => setField("avanzamento", clampProgress(e.target.value))}
          className="w-full accent-brand"
          aria-label="Avanzamento cantiere"
        />
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div className="h-full accent-gradient" style={{ width: `${clampProgress(draft.avanzamento)}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {draft.fasi.map((fase, index) => (
          <label key={`${fase.nome}-${index}`} className="bg-bg border border-stroke rounded-xl px-3 py-2 space-y-1">
            <span className="font-body text-[11px] text-fog truncate block">{fase.nome}</span>
            <div className={`h-1.5 rounded-full ${FASE_META[fase.stato]?.bar || "bg-stroke"}`} />
            <select
              value={fase.stato}
              onChange={(e) => setFase(index, e.target.value)}
              className="w-full bg-transparent font-display uppercase text-[10px] text-ink focus:outline-none"
              aria-label={`Stato fase ${fase.nome}`}
            >
              {Object.entries(FASE_META).map(([key, meta]) => (
                <option key={key} value={key}>{meta.label}</option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Milestone</span>
          <input
            value={draft.milestone}
            onChange={(e) => setField("milestone", e.target.value)}
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm focus:outline-none focus:border-brand"
          />
        </label>
        <label className="space-y-1">
          <span className="font-display uppercase text-[10px] text-fog">Criticita</span>
          <input
            value={draft.criticita}
            onChange={(e) => setField("criticita", e.target.value)}
            placeholder="Nessuna criticita"
            className="w-full bg-bg border border-stroke rounded-xl px-3 py-2 text-ink text-sm placeholder:text-fog focus:outline-none focus:border-brand"
          />
        </label>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="font-body text-xs text-fog flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="inline-flex items-center gap-1">
            <Flag className="w-3.5 h-3.5 text-brand" />
            {draft.milestone || "Milestone"}: {formatDateLabel(draft.milestone_data)}
          </span>
          <span className="inline-flex items-center gap-1">
            <User className="w-3.5 h-3.5 text-brand" />
            {draft.capocantiere || "Da assegnare"}
          </span>
          {draft.criticita && (
            <span className="inline-flex items-center gap-1 text-warning">
              <AlertTriangle className="w-3.5 h-3.5" />
              Criticita aperta
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {draft.stato !== "completato" && (
            <button
              type="button"
              onClick={() => onComplete(cantiere.id)}
              disabled={saving}
              className="bg-bg border border-stroke rounded-xl px-3 py-2 font-display uppercase text-[10px] text-fog hover:text-ink hover:border-brand disabled:opacity-60"
            >
              Completa
            </button>
          )}
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="bg-brand text-white rounded-xl px-4 py-2 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Salva
          </button>
        </div>
      </div>
    </article>
  );
}

export default function Cantieri() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("attivo");
  const [form, setForm] = useState(() => initialForm());

  const { data: list = [], isLoading, isError } = useQuery({
    queryKey: ["cantieri", filter],
    queryFn: async () => (await client.get("/cantieri", { params: { stato: filter } })).data,
    refetchInterval: 30000,
  });

  const { data: allCantieri = [] } = useQuery({
    queryKey: ["cantieri", "linked"],
    queryFn: async () => (await client.get("/cantieri", { params: { stato: "tutti" } })).data,
  });

  const { data: staff = [] } = useQuery({
    queryKey: ["staff"],
    queryFn: async () => (await client.get("/staff")).data,
  });

  const { data: wonLeads = [] } = useQuery({
    queryKey: ["leads", "chiuso_vinto"],
    queryFn: async () => (await client.get("/leads", { params: { status: "chiuso_vinto" } })).data,
  });

  const staffNames = useMemo(
    () => staff.map((u) => u.name).filter(Boolean),
    [staff],
  );
  const linkedLeadIds = useMemo(
    () => new Set(allCantieri.map((c) => c.lead_id).filter(Boolean)),
    [allCantieri],
  );
  const availableLeads = useMemo(
    () => wonLeads.filter((lead) => !linkedLeadIds.has(lead.id)),
    [wonLeads, linkedLeadIds],
  );

  useEffect(() => {
    if (!form.capocantiere && staffNames.length > 0) {
      setForm((current) => ({ ...current, capocantiere: staffNames[0] }));
    }
  }, [form.capocantiere, staffNames]);

  const createCantiere = useMutation({
    mutationFn: (body) => client.post("/cantieri", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cantieri"] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      setFilter("attivo");
      setForm(initialForm(staffNames[0] || ""));
      toast.success("Cantiere creato");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const updateCantiere = useMutation({
    mutationFn: ({ id, body }) => client.patch(`/cantieri/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cantieri"] });
      qc.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Cantiere aggiornato");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const stats = useMemo(() => {
    const total = list.length;
    const value = list.reduce((sum, c) => sum + numberValue(c.importo), 0);
    const avg = total
      ? Math.round(list.reduce((sum, c) => sum + numberValue(c.avanzamento), 0) / total)
      : 0;
    const critical = list.filter((c) => c.criticita).length;
    return { total, value, avg, critical };
  }, [list]);

  const selectLead = (leadId) => {
    const lead = availableLeads.find((l) => l.id === leadId);
    setForm((current) => ({
      ...current,
      lead_id: leadId,
      cliente: lead?.nome || current.cliente,
      indirizzo: lead?.indirizzo || lead?.citta || current.indirizzo,
      importo: lead ? leadImporto(lead) : current.importo,
      capocantiere: lead?.owner || current.capocantiere,
    }));
  };

  const submit = (e) => {
    e.preventDefault();
    const payload = payloadFromDraft({ ...form, fasi: DEFAULT_FASI });
    if (!payload.cliente) {
      toast.error("Cliente obbligatorio");
      return;
    }
    createCantiere.mutate(payload);
  };

  const savingId = updateCantiere.variables?.id;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-display font-bold uppercase text-3xl text-ink">Cantieri attivi</h1>
          <div className="flex flex-wrap gap-2 mt-3">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                className={`rounded-full border px-4 py-2 font-display uppercase text-[10px] transition-colors ${
                  filter === item.value
                    ? "bg-brand text-white border-brand"
                    : "bg-surface border-stroke text-fog hover:text-ink hover:border-brand"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <Metric label="Cantieri" value={stats.total} />
          <Metric label="Media" value={`${stats.avg}%`} />
          <Metric label="Criticita" value={stats.critical} warning={stats.critical > 0} />
          <Metric label="Valore" value={formatEuro(stats.value)} />
        </div>
      </div>

      <section className="bg-surface border border-stroke rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Plus className="w-5 h-5 text-brand" />
          <h2 className="font-display font-semibold uppercase text-sm text-ink">Nuovo cantiere</h2>
        </div>
        <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3 items-end">
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">Lead vinto</span>
            <select
              value={form.lead_id}
              onChange={(e) => selectLead(e.target.value)}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            >
              <option value="">Manuale</option>
              {availableLeads.map((lead) => (
                <option key={lead.id} value={lead.id}>
                  {lead.nome} - {lead.citta}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">Cliente</span>
            <input
              value={form.cliente}
              onChange={(e) => setForm((current) => ({ ...current, cliente: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1 xl:col-span-2">
            <span className="font-display uppercase text-[10px] text-fog">Indirizzo</span>
            <input
              value={form.indirizzo}
              onChange={(e) => setForm((current) => ({ ...current, indirizzo: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">Importo</span>
            <input
              type="number"
              min="0"
              value={form.importo}
              onChange={(e) => setForm((current) => ({ ...current, importo: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">Capocantiere</span>
            <select
              value={form.capocantiere}
              onChange={(e) => setForm((current) => ({ ...current, capocantiere: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            >
              <option value="">Da assegnare</option>
              {staffNames.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">Milestone</span>
            <input
              value={form.milestone}
              onChange={(e) => setForm((current) => ({ ...current, milestone: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">Data</span>
            <input
              type="date"
              value={form.milestone_data}
              onChange={(e) => setForm((current) => ({ ...current, milestone_data: e.target.value }))}
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm focus:outline-none focus:border-brand"
            />
          </label>
          <label className="space-y-1">
            <span className="font-display uppercase text-[10px] text-fog">Criticita</span>
            <input
              value={form.criticita}
              onChange={(e) => setForm((current) => ({ ...current, criticita: e.target.value }))}
              placeholder="Opzionale"
              className="w-full bg-bg border border-stroke rounded-xl px-3 py-2.5 text-ink text-sm placeholder:text-fog focus:outline-none focus:border-brand"
            />
          </label>
          <button
            type="submit"
            disabled={createCantiere.isPending}
            className="bg-brand text-white rounded-xl px-4 py-2.5 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {createCantiere.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Crea
          </button>
        </form>
      </section>

      {isLoading ? (
        <div className="text-fog font-display uppercase animate-pulse">Caricamento...</div>
      ) : isError ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-5 text-red-400 font-body">
          Impossibile caricare i cantieri.
        </div>
      ) : list.length === 0 ? (
        <div className="bg-surface border border-stroke rounded-2xl p-8 text-center font-body text-fog">
          Nessun cantiere in questa vista.
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {list.map((c) => (
            <CantiereCard
              key={c.id}
              cantiere={c}
              staffNames={staffNames}
              saving={updateCantiere.isPending && savingId === c.id}
              onSave={(id, body) => updateCantiere.mutate({ id, body })}
              onComplete={(id) => updateCantiere.mutate({ id, body: { stato: "completato", avanzamento: 100 } })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, warning = false }) {
  return (
    <div className="bg-surface border border-stroke rounded-xl px-4 py-3 min-w-28">
      <div className="font-display uppercase text-[10px] text-fog">{label}</div>
      <div className={`font-display font-bold text-lg truncate ${warning ? "text-warning" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}
